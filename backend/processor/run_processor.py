"""
Batch processing script for news processor
Run this script to process all unprocessed news from MongoDB
"""

import sys
import os
import argparse

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from processor.news_processor import NewsProcessor

def main():
    parser = argparse.ArgumentParser(description='Process unprocessed news from MongoDB')
    parser.add_argument('--batch-size', type=int, default=10,
                        help='Number of news items to process in one batch (default: 10)')
    parser.add_argument('--max-workers', type=int, default=50,
                        help='Maximum concurrent worker threads for AI processing (default: 50)')
    parser.add_argument('--continuous', action='store_true',
                        help='Keep processing until no unprocessed news remains')

    args = parser.parse_args()

    print("=" * 60)
    print("News Processor - Batch Processing")
    print("=" * 60)
    print(f"Batch size: {args.batch_size}")
    print(f"Continuous mode: {args.continuous}")
    print("=" * 60)

    processor = NewsProcessor()

    if args.continuous:
        print("\nRunning in continuous mode...")
        total_processed = 0
        batch_num = 1

        while True:
            print(f"\n--- Batch {batch_num} ---")
            processor.connect_mongodb()

            # Check if there are unprocessed news
            unprocessed_count = processor.mongo_db.news_raw.count_documents({"is_processed": False})
            processor.close_mongodb()

            if unprocessed_count == 0:
                print("\nNo more unprocessed news found. Stopping.")
                break

            print(f"Remaining unprocessed news: {unprocessed_count}")

            # Process batch
            processor.process_batch(batch_size=args.batch_size, max_workers=args.max_workers)
            total_processed += min(args.batch_size, unprocessed_count)
            batch_num += 1

        print("\n" + "=" * 60)
        print(f"Continuous processing complete!")
        print(f"Total processed: {total_processed}")
        print("=" * 60)
    else:
        # Single batch processing
        processor.process_batch(batch_size=args.batch_size, max_workers=args.max_workers)

if __name__ == "__main__":
    main()
