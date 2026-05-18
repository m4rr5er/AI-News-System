// MongoDB Initialization Script
// Database: ai_news

db = db.getSiblingDB('ai_news');

// Create news_raw collection for storing raw crawled news
db.createCollection('news_raw');

// Create indexes for news_raw collection
db.news_raw.createIndex({ "original_url": 1 }, { unique: true });
db.news_raw.createIndex({ "source": 1 });
db.news_raw.createIndex({ "category": 1 });
db.news_raw.createIndex({ "publish_date": -1 });
db.news_raw.createIndex({ "crawl_date": -1 });
db.news_raw.createIndex({ "is_processed": 1 });

// Compound index for querying unprocessed news
db.news_raw.createIndex({ "is_processed": 1, "crawl_date": -1 });

print("MongoDB initialization completed successfully");
print("Collection 'news_raw' created with indexes");

// Sample document structure for reference:
// {
//     "title": "News title",
//     "content": "Full news content",
//     "cover_image": "Image URL or null",
//     "original_url": "News URL",
//     "source": "Source website (BBC, CNN, The Guardian, China Daily)",
//     "publish_date": ISODate or string,
//     "crawl_date": ISODate or string,
//     "category": "Category name",
//     "is_processed": false  // Default value when crawler saves news, changed to true after GLM-4 processing
// }
