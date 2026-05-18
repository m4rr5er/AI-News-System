"""
Crawler API Routes
POST /api/crawler/trigger
GET  /api/crawler/status/{task_id}
"""
import uuid
import threading
import subprocess
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.db import DatabaseManager, get_db_connection
from utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/api/crawler", tags=["crawler"])

_tasks = {}

VALID_SOURCES = {'bbc', 'cnn', 'guardian', 'chinadaily'}
SPIDER_MAP = {
    'bbc': 'bbc',
    'cnn': 'cnn',
    'guardian': 'guardian',
    'chinadaily': 'chinadaily',
}


class CrawlerRequest(BaseModel):
    source: Optional[str] = None


def _run_spider(spider_name: str):
    """Run a single Scrapy spider in a subprocess."""
    scrapers_dir = os.path.join(os.path.dirname(__file__), '..', 'scrapers')
    scrapers_dir = os.path.abspath(scrapers_dir)

    try:
        result = subprocess.run(
            [sys.executable, '-m', 'scrapy', 'crawl', spider_name],
            cwd=scrapers_dir,
            capture_output=True,
            text=True,
            timeout=600
        )
        if result.returncode == 0:
            return spider_name, True, f"{spider_name}: completed successfully"
        return spider_name, False, f"{spider_name}: failed - {result.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return spider_name, False, f"{spider_name}: timed out after 600s"
    except Exception as e:
        return spider_name, False, f"{spider_name}: error - {str(e)}"


def _run_crawl_task(task_id: str, spiders: list):
    """Background thread: run all requested spiders concurrently."""
    task = _tasks[task_id]
    task['status'] = 'running'
    task['started_at'] = datetime.utcnow().isoformat()

    max_workers = max(1, min(len(spiders), int(os.getenv('CRAWLER_MAX_WORKERS', '4'))))
    task['max_workers'] = max_workers
    task['logs'].append(f"Running {len(spiders)} spiders with max_workers={max_workers}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_run_spider, spider_name) for spider_name in spiders]
        for future in as_completed(futures):
            spider_name, success, message = future.result()
            if success:
                task['completed_spiders'] += 1
            else:
                task['failed_spiders'] += 1
            task['logs'].append(message)

    # Count deduplicated items from MongoDB
    try:
        from pymongo import MongoClient
        from dotenv import load_dotenv
        load_dotenv()
        mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
        mongo_db_name = os.getenv('MONGO_DATABASE', 'ai_news')
        client = MongoClient(mongo_uri)
        db = client[mongo_db_name]
        task['total_crawled'] = db.news_raw.count_documents({})
        task['unprocessed'] = db.news_raw.count_documents({'is_processed': False})
        client.close()
    except Exception as e:
        logger.warning(f"Could not fetch MongoDB stats: {e}")

    task['status'] = 'completed' if task['failed_spiders'] == 0 else 'partial'
    task['finished_at'] = datetime.utcnow().isoformat()
    logger.info(f"Crawl task {task_id} finished with status: {task['status']}")


@router.post("/trigger", status_code=202)
def trigger_crawler(req: CrawlerRequest):
    source = (req.source or '').lower().strip()

    if source and source not in VALID_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source '{source}'. Valid options: {sorted(VALID_SOURCES)}"
        )

    spiders = [SPIDER_MAP[source]] if source else list(SPIDER_MAP.values())

    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        'task_id': task_id,
        'status': 'pending',
        'source': source or 'all',
        'spiders': spiders,
        'total_spiders': len(spiders),
        'completed_spiders': 0,
        'failed_spiders': 0,
        'max_workers': 0,
        'total_crawled': 0,
        'unprocessed': 0,
        'logs': [],
        'created_at': datetime.utcnow().isoformat(),
        'started_at': None,
        'finished_at': None,
    }

    thread = threading.Thread(
        target=_run_crawl_task,
        args=(task_id, spiders),
        daemon=True
    )
    thread.start()

    logger.info(f"Crawler task {task_id} triggered for: {source or 'all'}")
    return {
        'success': True,
        'task_id': task_id,
        'status': 'pending',
        'message': f"Crawl task started for: {source or 'all sources'}"
    }


@router.get("/status/{task_id}")
def get_crawler_status(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    return {'success': True, 'data': task}
