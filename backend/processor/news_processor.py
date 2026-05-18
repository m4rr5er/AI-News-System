import json
import os
import pymongo
import pymysql
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
from zai import ZhipuAiClient
from dotenv import load_dotenv

# Load environment variables from project root
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

class NewsProcessor:
    """Process unprocessed news from MongoDB using GLM-4 and save to MySQL"""

    def __init__(self):
        # Initialize GLM-4 client
        self.api_key = os.getenv("ZHIPU_AI_API_KEY", "")
        if not self.api_key:
            raise ValueError("ZHIPU_AI_API_KEY not found in environment variables")
        self.glm_client = ZhipuAiClient(api_key=self.api_key)

        # MongoDB configuration
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self.mongo_db_name = os.getenv("MONGO_DATABASE", "ai_news")
        self.mongo_client = None
        self.mongo_db = None

        # MySQL configuration
        self.mysql_config = {
            'host': os.getenv("MYSQL_HOST", "localhost"),
            'port': int(os.getenv("MYSQL_PORT", 3306)),
            'user': os.getenv("MYSQL_USER", "root"),
            'password': os.getenv("MYSQL_PASSWORD", "123456"),
            'database': os.getenv("MYSQL_DATABASE", "ai_news"),
            'charset': 'utf8mb4'
        }

    def connect_mongodb(self):
        """Connect to MongoDB"""
        try:
            self.mongo_client = pymongo.MongoClient(self.mongo_uri)
            self.mongo_db = self.mongo_client[self.mongo_db_name]
            print(f"Connected to MongoDB: {self.mongo_db_name}")
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise

    def close_mongodb(self):
        """Close MongoDB connection"""
        if self.mongo_client:
            self.mongo_client.close()

    def get_unprocessed_news(self, limit=10):
        """Get unprocessed news from MongoDB"""
        try:
            news_list = list(self.mongo_db.news_raw.find(
                {"is_processed": False}
            ).limit(limit))
            print(f"Found {len(news_list)} unprocessed news items")
            return news_list
        except Exception as e:
            print(f"Error fetching unprocessed news: {e}")
            return []

    def validate_ai_result(self, ai_result):
        """Validate AI processing result before saving to database"""
        if not ai_result:
            raise ValueError("AI result is None or empty")

        # Check required fields
        required_fields = ['en_summary', 'difficulty_score', 'tags']
        for field in required_fields:
            if not ai_result.get(field):
                raise ValueError(f"Missing required field: {field}")

        # Validate difficulty_score range
        difficulty = ai_result.get('difficulty_score')
        if not isinstance(difficulty, (int, float)) or difficulty < 1 or difficulty > 10:
            raise ValueError(f"Invalid difficulty_score: {difficulty}. Must be between 1-10")

        # Validate tags is a list
        if not isinstance(ai_result.get('tags'), list):
            raise ValueError("tags must be a list")

        # Validate optional arrays
        for field in ['background_info', 'viewpoint_analysis', 'entity_relation', 'qa_suggestions']:
            if field in ai_result and not isinstance(ai_result[field], list):
                raise ValueError(f"{field} must be a list")

        print(f"✓ AI result validation passed")
        return True

    def process_news_with_glm(self, news_data):
        """Process news using GLM-4 API"""
        system_prompt = """
        You are a professional News Data Architect. Your goal is to process complex news for English learners (A2-B1 level).

        IMPORTANT: This is for educational and language learning purposes only. Please process the content objectively.

        ## INSTRUCTIONS:
        1. "difficulty_score": Rate the reading difficulty from 1-10 (1=easiest, 10=hardest).
        2. "tags": Extract 3-5 relevant keywords or topics from the news.
        3. "qa_suggestions": Generate 3 engaging questions that learners can ask an AI to better understand this news.
        4. "background_info": Identify key entities (people, organizations, concepts) and provide brief English descriptions to help learners understand the context.
        5. "viewpoint_analysis": Analyze different perspectives or opinions mentioned in the news.
        6. "entity_relation": Extract relationships between key entities mentioned in the news.
        7. "en_summary": Write a concise English summary (60-80 words) of the main points.

        ## JSON SCHEMA:
        {
          "difficulty_score": number,
          "tags": ["string"],
          "en_summary": "string",
          "qa_suggestions": ["string"],
          "background_info": [{"entity_name": "string", "entity_type": "string", "description": "string", "is_web_searched": true}],
          "viewpoint_analysis": [{"entity_name": "string", "viewpoint": "string", "sentiment": "Positive/Negative/Neutral"}],
          "entity_relation": [{"subject_entity": "string", "relation": "string", "object_entity": "string"}]
        }
        """

        user_prompt = f"""
        ### INPUT DATA ###
        Title: {news_data.get('title')}
        Content: {news_data.get('content')}

        NOTE: This content is being processed for educational purposes to help English language learners.
        """

        try:
            response = self.glm_client.chat.completions.create(
                model="glm-4-air-250414",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            raw_content = response.choices[0].message.content
            return json.loads(raw_content)
        except Exception as e:
            error_msg = str(e)
            # Check if it's a content filter error
            if "1301" in error_msg or "contentFilter" in error_msg:
                print(f"⚠ Content filtered by GLM-4 (sensitive content detected), skipping this news")
                return None
            print(f"Error during GLM-4 API call: {e}")
            return None

    def save_to_mysql(self, news_data, ai_result):
        """Save processed news to MySQL"""
        mysql_conn = None
        try:
            # Validate AI result before saving
            self.validate_ai_result(ai_result)

            # Connect to MySQL
            mysql_conn = pymysql.connect(**self.mysql_config)
            cursor = mysql_conn.cursor()

            # Check if news already exists by original_url
            check_sql = "SELECT id FROM news WHERE original_url = %s"
            cursor.execute(check_sql, (news_data.get('original_url'),))
            existing = cursor.fetchone()

            if existing:
                news_id = existing[0]
                print(f"News already exists in MySQL (id={news_id}), skipping insert")
            else:
                # Insert into news table
                news_sql = """
                INSERT INTO news (
                    title, category, cover_image, original_url, source,
                    publish_date, content, en_summary, difficulty_score,
                    tags, qa_suggestions
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

                news_values = (
                    news_data.get('title'),
                    news_data.get('category'),
                    news_data.get('cover_image'),
                    news_data.get('original_url'),
                    news_data.get('source'),
                    news_data.get('publish_date'),
                    news_data.get('content'),
                    ai_result.get('en_summary'),
                    ai_result.get('difficulty_score'),
                    json.dumps(ai_result.get('tags', []), ensure_ascii=False),
                    json.dumps(ai_result.get('qa_suggestions', []), ensure_ascii=False)
                )

                cursor.execute(news_sql, news_values)
                news_id = cursor.lastrowid

            # Insert background_info
            bg_sql = """
            INSERT INTO background_info (
                news_id, entity_name, entity_type, description, is_web_searched
            ) VALUES (%s, %s, %s, %s, %s)
            """

            for bg in ai_result.get('background_info', []):
                bg_values = (
                    news_id,
                    bg.get('entity_name'),
                    bg.get('entity_type'),
                    bg.get('description'),
                    bg.get('is_web_searched', True)
                )
                cursor.execute(bg_sql, bg_values)

            # Insert viewpoint_analysis
            viewpoint_sql = """
            INSERT INTO viewpoint_analysis (
                news_id, entity_name, viewpoint, sentiment
            ) VALUES (%s, %s, %s, %s)
            """

            for vp in ai_result.get('viewpoint_analysis', []):
                vp_values = (
                    news_id,
                    vp.get('entity_name'),
                    vp.get('viewpoint'),
                    vp.get('sentiment')
                )
                cursor.execute(viewpoint_sql, vp_values)

            # Insert entity_relation
            relation_sql = """
            INSERT INTO entity_relation (
                news_id, subject_entity, relation, object_entity
            ) VALUES (%s, %s, %s, %s)
            """

            for rel in ai_result.get('entity_relation', []):
                rel_values = (
                    news_id,
                    rel.get('subject_entity'),
                    rel.get('relation'),
                    rel.get('object_entity')
                )
                cursor.execute(relation_sql, rel_values)

            # Commit transaction
            mysql_conn.commit()
            cursor.close()

            print(f"Successfully saved news to MySQL: {news_data.get('title')}")
            return news_id

        except Exception as e:
            if mysql_conn:
                mysql_conn.rollback()
            print(f"Error saving to MySQL: {e}")
            raise
        finally:
            if mysql_conn:
                mysql_conn.close()

    def mark_as_processed(self, news_id):
        """Mark news as processed in MongoDB"""
        try:
            result = self.mongo_db.news_raw.update_one(
                {"_id": news_id},
                {"$set": {"is_processed": True}}
            )
            if result.modified_count > 0:
                print(f"Marked news as processed in MongoDB: {news_id}")
            return result.modified_count > 0
        except Exception as e:
            print(f"Error marking news as processed: {e}")
            return False

    def update_news_view_count(self, news_id):
        """Update view count for a news article"""
        mysql_conn = None
        try:
            mysql_conn = pymysql.connect(**self.mysql_config)
            cursor = mysql_conn.cursor()

            update_sql = "UPDATE news SET view_count = view_count + 1 WHERE id = %s"
            cursor.execute(update_sql, (news_id,))
            mysql_conn.commit()
            cursor.close()

            print(f"Updated view count for news_id: {news_id}")
            return True

        except Exception as e:
            if mysql_conn:
                mysql_conn.rollback()
            print(f"Error updating view count: {e}")
            return False
        finally:
            if mysql_conn:
                mysql_conn.close()

    def refresh_hot_scores(self):
        """Refresh hot scores for all news using formula: Hot = (Total_Views) / (Age_in_Hours + 2)^1.5"""
        mysql_conn = None
        try:
            mysql_conn = pymysql.connect(**self.mysql_config)
            cursor = mysql_conn.cursor()

            # Calculate hot score using the formula
            update_sql = """
                UPDATE news
                SET hot_score = view_count / POWER(
                    TIMESTAMPDIFF(HOUR, publish_date, NOW()) + 2,
                    1.5
                )
                WHERE publish_date IS NOT NULL
            """

            cursor.execute(update_sql)
            affected_rows = cursor.rowcount
            mysql_conn.commit()
            cursor.close()

            print(f"✓ Refreshed hot scores for {affected_rows} news articles")
            return affected_rows

        except Exception as e:
            if mysql_conn:
                mysql_conn.rollback()
            print(f"Error refreshing hot scores: {e}")
            return 0
        finally:
            if mysql_conn:
                mysql_conn.close()

    def process_single_news(self, news_item):
        """Process a single news item"""
        try:
            print(f"\nProcessing: {news_item.get('title')}")

            # Ensure MongoDB is connected
            if not self.mongo_client:
                self.connect_mongodb()

            # Process with GLM-4
            ai_result = self.process_news_with_glm(news_item)

            if not ai_result:
                print(f"⚠ Skipping news (GLM-4 returned None): {news_item.get('title')}")
                # Mark as processed even if GLM-4 filtered it, to avoid retry loop
                self.mark_as_processed(news_item['_id'])
                return None

            # Save to MySQL
            news_id = self.save_to_mysql(news_item, ai_result)

            # Mark as processed in MongoDB
            self.mark_as_processed(news_item['_id'])

            print(f"Successfully processed: {news_item.get('title')}")
            return news_id

        except Exception as e:
            print(f"Error processing news {news_item.get('title')}: {e}")
            # Mark as processed even on error to avoid infinite retry loop
            if not self.mongo_client:
                self.connect_mongodb()
            self.mark_as_processed(news_item['_id'])
            print(f"⚠ Marked failed news as processed to avoid retry loop")
            raise

    def process_batch(self, batch_size=10, max_workers=50):
        """Process a batch of unprocessed news with multithreading."""
        try:
            self.connect_mongodb()

            # Get unprocessed news
            news_list = self.get_unprocessed_news(limit=batch_size)

            if not news_list:
                print("No unprocessed news found")
                return

            success_count = 0
            fail_count = 0

            workers = max(1, min(max_workers, len(news_list)))
            print(f"Using max_workers={workers} for batch processing")

            def process_one(news):
                processor = NewsProcessor()
                try:
                    processor.process_single_news(news)
                    return True, None
                except Exception as e:
                    return False, str(e)
                finally:
                    processor.close_mongodb()

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(process_one, news) for news in news_list]
                for future in as_completed(futures):
                    success, error = future.result()
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                        print(f"Error processing news: {error}")

            print(f"\n=== Processing Complete ===")
            print(f"Success: {success_count}")
            print(f"Failed: {fail_count}")
            print(f"Total: {len(news_list)}")

        except Exception as e:
            print(f"Error in batch processing: {e}")
        finally:
            self.close_mongodb()


if __name__ == "__main__":
    processor = NewsProcessor()
    processor.process_batch(batch_size=10)
