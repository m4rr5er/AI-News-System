"""
Test script for CNN News crawler
Tests the ability to crawl CNN News and extract content, saving results to JSON file
"""

import sys
import os
import json
from datetime import datetime
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

# Add the scrapers directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'scrapers'))

from scrapers.spiders.cnn_spider import CNNSpider


class CNNTestPipeline:
    """Custom pipeline to save crawled items to JSON file"""

    def __init__(self):
        self.items = []
        self.output_file = os.path.join(
            os.path.dirname(__file__),
            f'cnn_test_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )

    def open_spider(self, spider):
        """Called when spider is opened"""
        print(f"\n{'='*60}")
        print(f"CNN News Crawler Test Started")
        print(f"{'='*60}\n")

    def process_item(self, item, spider):
        """Process each crawled item"""
        # Convert item to dict and handle datetime serialization
        item_dict = dict(item)

        # Convert datetime objects to ISO format strings
        if 'publish_date' in item_dict and isinstance(item_dict['publish_date'], datetime):
            item_dict['publish_date'] = item_dict['publish_date'].isoformat()
        if 'crawl_date' in item_dict and isinstance(item_dict['crawl_date'], datetime):
            item_dict['crawl_date'] = item_dict['crawl_date'].isoformat()

        self.items.append(item_dict)

        # Print progress
        print(f"\n[Item {len(self.items)}] Crawled:")
        print(f"  Title: {item_dict.get('title', 'N/A')[:80]}...")
        print(f"  URL: {item_dict.get('url', 'N/A')}")
        print(f"  Category: {item_dict.get('category', 'N/A')}")
        print(f"  Content Length: {len(item_dict.get('content', ''))} characters")
        print(f"  Has Cover Image: {'Yes' if item_dict.get('cover_image') else 'No'}")

        return item

    def close_spider(self, spider):
        """Called when spider is closed - save results to JSON"""
        print(f"\n{'='*60}")
        print(f"CNN News Crawler Test Completed")
        print(f"{'='*60}")
        print(f"\nTotal articles crawled: {len(self.items)}")

        if self.items:
            # Save to JSON file
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.items, f, ensure_ascii=False, indent=2)

            print(f"\nResults saved to: {self.output_file}")

            # Print summary statistics
            print(f"\n{'='*60}")
            print("Summary Statistics:")
            print(f"{'='*60}")

            categories = {}
            total_content_length = 0
            items_with_images = 0

            for item in self.items:
                # Count categories
                category = item.get('category', 'unknown')
                categories[category] = categories.get(category, 0) + 1

                # Calculate content length
                total_content_length += len(item.get('content', ''))

                # Count items with images
                if item.get('cover_image'):
                    items_with_images += 1

            print(f"\nArticles by Category:")
            for category, count in sorted(categories.items()):
                print(f"  {category}: {count}")

            print(f"\nContent Statistics:")
            print(f"  Average content length: {total_content_length // len(self.items)} characters")
            print(f"  Articles with cover images: {items_with_images}/{len(self.items)} ({items_with_images*100//len(self.items)}%)")

            print(f"\n{'='*60}")
            print("Sample Article:")
            print(f"{'='*60}")
            sample = self.items[0]
            print(f"Title: {sample.get('title', 'N/A')}")
            print(f"URL: {sample.get('url', 'N/A')}")
            print(f"Category: {sample.get('category', 'N/A')}")
            print(f"Source: {sample.get('source', 'N/A')}")
            print(f"Publish Date: {sample.get('publish_date', 'N/A')}")
            print(f"Cover Image: {sample.get('cover_image', 'N/A')}")
            print(f"\nContent Preview (first 300 chars):")
            print(f"{sample.get('content', 'N/A')[:300]}...")
            print(f"\n{'='*60}\n")
        else:
            print("\nWarning: No articles were crawled!")
            print("This might be due to:")
            print("  1. Network connectivity issues")
            print("  2. CNN website structure changes")
            print("  3. Anti-crawling measures blocking the requests")
            print("\nPlease check the crawler logs above for more details.")


def run_test():
    """Run the CNN crawler test"""

    # Get Scrapy settings
    settings = get_project_settings()

    # Override settings for testing - only change pipeline and log level
    settings.update({
        'ITEM_PIPELINES': {
            '__main__.CNNTestPipeline': 300,
        },
        'LOG_LEVEL': 'INFO',
    })

    # Create crawler process
    process = CrawlerProcess(settings)

    # Add spider to process
    process.crawl(CNNSpider)

    # Start crawling (blocking)
    print("\nStarting CNN crawler test...")
    print("This will crawl all articles from the following categories:")
    print("  - Politics")
    print("  - Business")
    print("  - Health")
    print("  - Entertainment")
    print("  - Travel")
    print("  - Sport")
    print("  - Science")
    print("\nPlease wait...\n")

    process.start()


if __name__ == '__main__':
    run_test()
