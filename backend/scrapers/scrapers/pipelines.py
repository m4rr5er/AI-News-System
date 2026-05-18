# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import re
import redis
import pymongo
import pymysql
from datetime import datetime
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
import html


class DataCleaningPipeline:
    """Pipeline for cleaning scraped data"""

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Clean title
        if adapter.get('title'):
            adapter['title'] = self.clean_text(adapter['title'])
            # Limit title length
            if len(adapter['title']) > 500:
                adapter['title'] = adapter['title'][:497] + '...'

        # Clean content
        if adapter.get('content'):
            adapter['content'] = self.clean_text(adapter['content'])
            # Remove extra whitespace
            adapter['content'] = re.sub(r'\s+', ' ', adapter['content']).strip()

        # Standardize date format
        if adapter.get('publish_date'):
            adapter['publish_date'] = self.standardize_date(adapter['publish_date'])

        if adapter.get('crawl_date'):
            adapter['crawl_date'] = self.standardize_date(adapter['crawl_date'])

        # Validate required fields
        if not adapter.get('title') or not adapter.get('content'):
            raise DropItem(f"Missing required fields in {item}")

        # Ensure content has minimum length
        if len(adapter.get('content', '')) < 100:
            raise DropItem(f"Content too short in {item}")

        # Check if content starts with lowercase letter (incomplete content)
        content = adapter.get('content', '').strip()
        if content and content[0].islower():
            raise DropItem(f"Content starts with lowercase letter (incomplete): {item.get('title')}")

        return item

    def clean_text(self, text):
        """Remove HTML tags and clean text"""
        if not text:
            return ''

        # Decode HTML entities
        text = html.unescape(text)

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?;:\'"()-]', '', text)

        return text.strip()

    def standardize_date(self, date_value):
        """Standardize date format to datetime object"""
        if isinstance(date_value, datetime):
            return date_value

        if isinstance(date_value, str):
            try:
                # Try parsing ISO format
                return datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            except:
                try:
                    # Try common date formats
                    for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y']:
                        try:
                            return datetime.strptime(date_value, fmt)
                        except:
                            continue
                except:
                    pass

        # Default to current date if parsing fails
        return datetime.now()


class RedisDeduplicationPipeline:
    """Pipeline for deduplicating news using Redis.
    Warm-up: loads URLs from MySQL (final) + MongoDB (pending).
    Online check: SISMEMBER before crawling, SADD after saving to MongoDB.
    """

    REDIS_KEY = 'news:seen:urls'

    def __init__(self, redis_host, redis_port, redis_db, mysql_host, mysql_port, mysql_user, mysql_password, mysql_db, mongo_uri, mongo_db):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.mysql_host = mysql_host
        self.mysql_port = mysql_port
        self.mysql_user = mysql_user
        self.mysql_password = mysql_password
        self.mysql_db = mysql_db
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.redis_client = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            redis_host=crawler.settings.get('REDIS_HOST', 'localhost'),
            redis_port=crawler.settings.get('REDIS_PORT', 6379),
            redis_db=crawler.settings.get('REDIS_DB', 0),
            mysql_host=crawler.settings.get('MYSQL_HOST', 'localhost'),
            mysql_port=crawler.settings.get('MYSQL_PORT', 3306),
            mysql_user=crawler.settings.get('MYSQL_USER', 'root'),
            mysql_password=crawler.settings.get('MYSQL_PASSWORD', ''),
            mysql_db=crawler.settings.get('MYSQL_DATABASE', 'ai_news'),
            mongo_uri=crawler.settings.get('MONGO_URI', 'mongodb://localhost:27017/'),
            mongo_db=crawler.settings.get('MONGO_DATABASE', 'ai_news'),
        )

    def open_spider(self, spider):
        self.redis_client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            db=self.redis_db,
            decode_responses=True
        )
        spider.logger.info(f"Connected to Redis at {self.redis_host}:{self.redis_port}")
        self._warmup(spider)

    def _warmup(self, spider):
        """Load URLs from MySQL and MongoDB into Redis on startup."""
        total = 0

        # MySQL: final published news
        mysql_conn = None
        try:
            mysql_conn = pymysql.connect(
                host=self.mysql_host,
                port=self.mysql_port,
                user=self.mysql_user,
                password=self.mysql_password,
                database=self.mysql_db,
                charset='utf8mb4'
            )
            cursor = mysql_conn.cursor()
            cursor.execute("SELECT original_url FROM news WHERE original_url IS NOT NULL")
            urls = [row[0] for row in cursor.fetchall() if row[0]]
            if urls:
                self.redis_client.sadd(self.REDIS_KEY, *urls)
                total += len(urls)
                spider.logger.info(f"Warm-up: loaded {len(urls)} URLs from MySQL")
            cursor.close()
        except Exception as e:
            spider.logger.warning(f"Warm-up MySQL failed: {e}")
        finally:
            if mysql_conn:
                mysql_conn.close()

        # MongoDB: pending (not yet AI-processed) news
        try:
            mongo_client = pymongo.MongoClient(self.mongo_uri)
            collection = mongo_client[self.mongo_db]['news_raw']
            urls = [doc['original_url'] for doc in collection.find(
                {'original_url': {'$exists': True, '$ne': None}},
                {'original_url': 1}
            )]
            if urls:
                self.redis_client.sadd(self.REDIS_KEY, *urls)
                total += len(urls)
                spider.logger.info(f"Warm-up: loaded {len(urls)} URLs from MongoDB")
            mongo_client.close()
        except Exception as e:
            spider.logger.warning(f"Warm-up MongoDB failed: {e}")

        spider.logger.info(f"Warm-up complete: {total} URLs loaded into Redis")

    def close_spider(self, spider):
        if self.redis_client:
            self.redis_client.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        url = adapter.get('url')

        if not url:
            raise DropItem("Missing URL in item")

        if self.redis_client.sismember(self.REDIS_KEY, url):
            raise DropItem(f"Duplicate: {url}")

        # Add to Redis after passing dedup check; MongoDB pipeline saves it next
        self.redis_client.sadd(self.REDIS_KEY, url)

        return item


class MongoDBPipeline:
    """Pipeline for storing raw news data in MongoDB"""

    def __init__(self, mongo_uri, mongo_db):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.client = None
        self.db = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mongo_uri=crawler.settings.get('MONGO_URI', 'mongodb://localhost:27017/'),
            mongo_db=crawler.settings.get('MONGO_DATABASE', 'ai_news')
        )

    def open_spider(self, spider):
        """Connect to MongoDB when spider opens"""
        try:
            self.client = pymongo.MongoClient(self.mongo_uri)
            self.db = self.client[self.mongo_db]
            spider.logger.info(f"Connected to MongoDB: {self.mongo_db}")
        except Exception as e:
            spider.logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def close_spider(self, spider):
        """Close MongoDB connection when spider closes"""
        if self.client:
            self.client.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Prepare document for MongoDB
        document = {
            'title': adapter.get('title'),
            'content': adapter.get('content'),
            'cover_image': adapter.get('cover_image'),
            'original_url': adapter.get('url'),
            'source': adapter.get('source'),
            'publish_date': adapter.get('publish_date'),
            'crawl_date': adapter.get('crawl_date'),
            'category': adapter.get('category'),
            'is_processed': False  # Mark as unprocessed for GLM-4 processing
        }

        try:
            # Insert into news_raw collection
            self.db.news_raw.insert_one(document)
            spider.logger.info(f"Saved to MongoDB: {document['title']}")
        except Exception as e:
            spider.logger.error(f"Error saving to MongoDB: {e}")
            raise DropItem(f"Failed to save item to MongoDB: {e}")

        return item
