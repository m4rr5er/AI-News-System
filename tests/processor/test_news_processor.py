"""
Test script for news processor
Tests the complete flow: MongoDB -> GLM-4 -> MySQL
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from processor.news_processor import NewsProcessor

def test_processor():
    """Test the news processor with a small batch"""
    print("=" * 60)
    print("Testing News Processor")
    print("=" * 60)

    try:
        # Initialize processor
        processor = NewsProcessor()
        print("✓ NewsProcessor initialized successfully")

        # Test MongoDB connection
        processor.connect_mongodb()
        print("✓ Connected to MongoDB")

        # Check for unprocessed news
        unprocessed = processor.get_unprocessed_news(limit=1)

        if not unprocessed:
            print("\n⚠ No unprocessed news found in MongoDB")
            print("Please run a crawler first to populate MongoDB with news data")
            processor.close_mongodb()
            return

        print(f"✓ Found {len(unprocessed)} unprocessed news item(s)")

        # Process one news item as a test
        news = unprocessed[0]
        print(f"\nProcessing test news: {news.get('title')[:50]}...")

        # Test GLM-4 processing
        print("\nCalling GLM-4 API...")
        ai_result = processor.process_news_with_glm(news)

        if not ai_result:
            print("✗ GLM-4 processing failed")
            processor.close_mongodb()
            return

        print("✓ GLM-4 processing successful")
        print(f"  - Simple title: {ai_result.get('simple_title')}")
        print(f"  - Difficulty score: {ai_result.get('difficulty_score')}")
        print(f"  - Vocabulary count: {len(ai_result.get('vocabulary', []))}")
        print(f"  - Tags: {ai_result.get('tags')}")

        # Test MySQL saving
        print("\nSaving to MySQL...")
        news_id = processor.save_to_mysql(news, ai_result)
        print(f"✓ Saved to MySQL with news_id: {news_id}")

        # Test marking as processed
        print("\nMarking as processed in MongoDB...")
        marked = processor.mark_as_processed(news['_id'])

        if marked:
            print("✓ Marked as processed in MongoDB")
        else:
            print("✗ Failed to mark as processed")

        processor.close_mongodb()

        print("\n" + "=" * 60)
        print("✓ All tests passed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_processor()
