"""
APScheduler configuration for scheduled tasks
"""
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from utils.logger import setup_logger

logger = setup_logger(__name__)


def init_scheduler(app):
    """Initialize APScheduler with scheduled tasks"""
    scheduler = BackgroundScheduler()

    # Task 1: Daily crawler - runs at 2 AM every day
    scheduler.add_job(
        func=run_daily_crawler,
        trigger=CronTrigger(hour=2, minute=0),
        id='daily_crawler',
        name='Daily news crawler',
        replace_existing=True
    )

    # Task 2: AI processing - runs every 30 minutes
    scheduler.add_job(
        func=run_ai_processing,
        trigger=CronTrigger(minute='*/30'),
        id='ai_processing',
        name='Process unprocessed news',
        replace_existing=True
    )

    # Task 3: Daily podcast generation - runs at 6 AM every day
    scheduler.add_job(
        func=run_daily_podcast,
        trigger=CronTrigger(hour=6, minute=0),
        id='daily_podcast',
        name='Generate daily podcast',
        replace_existing=True
    )

    # Task 4: Hot score update - runs every 30 minutes
    scheduler.add_job(
        func=update_hot_scores,
        trigger=CronTrigger(minute='*/30'),
        id='hot_score_update',
        name='Update news hot scores',
        replace_existing=True
    )

    scheduler.start()
    logger.info("APScheduler started with 4 scheduled tasks")

    # Shutdown scheduler when app exits
    import atexit
    atexit.register(lambda: scheduler.shutdown())


def run_daily_crawler():
    """Scheduled task: Run all crawlers daily"""
    logger.info("Starting scheduled daily crawler task")
    try:
        import subprocess
        scrapers_dir = os.path.join(os.path.dirname(__file__), '..', 'scrapers')
        scrapers_dir = os.path.abspath(scrapers_dir)

        spiders = ['bbc', 'cnn', 'guardian', 'chinadaily']
        max_workers = max(1, min(len(spiders), int(os.getenv('CRAWLER_MAX_WORKERS', '4'))))

        def run_one_spider(spider):
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'scrapy', 'crawl', spider],
                    cwd=scrapers_dir,
                    capture_output=True,
                    text=True,
                    timeout=600
                )
                if result.returncode == 0:
                    return spider, True, "completed successfully"
                return spider, False, f"failed - {result.stderr[:200]}"
            except Exception as e:
                return spider, False, f"error - {str(e)}"

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(run_one_spider, spider) for spider in spiders]
            for future in as_completed(futures):
                spider, success, message = future.result()
                if success:
                    logger.info(f"Scheduled crawler: {spider} {message}")
                else:
                    logger.error(f"Scheduled crawler: {spider} {message}")

    except Exception as e:
        logger.error(f"Daily crawler task failed: {e}")


def run_ai_processing():
    """Scheduled task: Process unprocessed news every 30 minutes"""
    logger.info("Starting scheduled AI processing task")
    try:
        from utils.db import DatabaseManager

        # Check if there are unprocessed news
        mongo_db = DatabaseManager.get_mongo_db()
        unprocessed_count = mongo_db.news_raw.count_documents({'is_processed': False})

        if unprocessed_count == 0:
            logger.info("No unprocessed news found, skipping AI processing")
            return

        logger.info(f"Found {unprocessed_count} unprocessed news items")

        # Import processor
        processor_path = os.path.join(os.path.dirname(__file__), '..', 'processor')
        sys.path.insert(0, processor_path)
        from news_processor import NewsProcessor

        unprocessed_news = list(mongo_db.news_raw.find({'is_processed': False}))
        max_workers = max(1, min(len(unprocessed_news), int(os.getenv('AI_MAX_WORKERS', '10'))))
        processed_count = 0
        failed_count = 0

        def process_one_news(news_item):
            processor = NewsProcessor()
            try:
                processor.process_single_news(news_item)
                return True, None
            except Exception as e:
                return False, str(e)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_one_news, news_item) for news_item in unprocessed_news]
            for future in as_completed(futures):
                success, error = future.result()
                if success:
                    processed_count += 1
                else:
                    failed_count += 1
                    logger.error(f"Failed to process news: {error}")

        logger.info(f"Scheduled AI processing completed: {processed_count} processed, {failed_count} failed")

    except Exception as e:
        logger.error(f"AI processing task failed: {e}")


def run_daily_podcast():
    """Scheduled task: Generate daily podcast at 6 AM"""
    logger.info("Starting scheduled daily podcast generation")
    try:
        from datetime import date

        # Import TTS module
        tts_path = os.path.join(os.path.dirname(__file__), '..', 'tts')
        sys.path.insert(0, tts_path)
        from podcast_generator import generate_daily_podcast

        # Generate podcast for today
        target_date = str(date.today())
        result = generate_daily_podcast(target_date)

        logger.info(f"Scheduled podcast generation completed: podcast_id={result.get('podcast_id')}")

    except Exception as e:
        logger.error(f"Daily podcast task failed: {e}")


def update_hot_scores():
    """Scheduled task: Update hot scores for all news"""
    logger.info("Starting scheduled hot score update")
    try:
        from utils.db import get_db_connection

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Update hot scores using the formula:
                # hot_score = view_count / POWER(TIMESTAMPDIFF(HOUR, publish_date, NOW()) + 2, 1.5)
                cursor.execute(
                    '''UPDATE news
                       SET hot_score = view_count / POWER(TIMESTAMPDIFF(HOUR, publish_date, NOW()) + 2, 1.5)
                       WHERE publish_date IS NOT NULL'''
                )
                affected_rows = cursor.rowcount

        logger.info(f"Hot score update completed: {affected_rows} news items updated")

    except Exception as e:
        logger.error(f"Hot score update task failed: {e}")


def continuous_news_processing():
    """Background thread: Continuously process unprocessed news until none remain"""
    logger.info("Starting continuous news processing thread")

    try:
        from utils.db import DatabaseManager

        # Wait a bit for the server to fully start
        time.sleep(5)

        while True:
            try:
                # Check if there are unprocessed news
                mongo_db = DatabaseManager.get_mongo_db()
                unprocessed_count = mongo_db.news_raw.count_documents({'is_processed': False})

                if unprocessed_count == 0:
                    logger.info("No unprocessed news found. Continuous processing will check again in 5 minutes.")
                    time.sleep(300)  # Wait 5 minutes before checking again
                    continue

                logger.info(f"Found {unprocessed_count} unprocessed news items, starting processing...")

                # Import processor
                processor_path = os.path.join(os.path.dirname(__file__), '..', 'processor')
                sys.path.insert(0, processor_path)
                from news_processor import NewsProcessor

                # Get all unprocessed news
                unprocessed_news = list(mongo_db.news_raw.find({'is_processed': False}))
                max_workers = max(1, min(len(unprocessed_news), int(os.getenv('AI_MAX_WORKERS', '10'))))
                processed_count = 0
                failed_count = 0

                def process_one_news(news_item):
                    processor = NewsProcessor()
                    try:
                        processor.process_single_news(news_item)
                        return True, None
                    except Exception as e:
                        return False, str(e)

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [executor.submit(process_one_news, news_item) for news_item in unprocessed_news]
                    for future in as_completed(futures):
                        success, error = future.result()
                        if success:
                            processed_count += 1
                        else:
                            failed_count += 1
                            logger.error(f"Failed to process news: {error}")

                logger.info(f"Continuous processing batch completed: {processed_count} processed, {failed_count} failed")

                # Small delay before checking again
                time.sleep(10)

            except Exception as e:
                logger.error(f"Error in continuous processing loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying on error

    except Exception as e:
        logger.error(f"Fatal error in continuous news processing thread: {e}")


def start_continuous_processing():
    """Start the continuous news processing in a background thread"""
    processing_thread = threading.Thread(
        target=continuous_news_processing,
        daemon=True,
        name="ContinuousNewsProcessing"
    )
    processing_thread.start()
    logger.info("Continuous news processing thread started")
