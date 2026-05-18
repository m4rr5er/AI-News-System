"""
AI Processing API Routes
POST /api/ai/process
GET  /api/ai/status/{task_id}
POST /api/ai/retry
"""
import uuid
import threading
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from utils.db import DatabaseManager
from utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai"])


class ProcessRequest(BaseModel):
    batch_size: int = Field(default=10, ge=1, le=50)
    max_workers: int = Field(default=50, ge=1, le=50)

class RetryRequest(BaseModel):
    news_ids: List[str] = []

# In-memory task store
_ai_tasks = {}


def _run_ai_processing(task_id: str, batch_size: int, max_workers: int):
    """Background thread: process unprocessed news from MongoDB."""
    task = _ai_tasks[task_id]
    task['status'] = 'running'
    task['started_at'] = datetime.utcnow().isoformat()

    try:
        # Import processor
        import sys
        processor_path = os.path.join(os.path.dirname(__file__), '..', 'processor')
        sys.path.insert(0, processor_path)
        from news_processor import NewsProcessor

        # Get unprocessed count
        mongo_db = DatabaseManager.get_mongo_db()
        unprocessed_news = list(mongo_db.news_raw.find({'is_processed': False}))
        total_unprocessed = len(unprocessed_news)
        task['total_to_process'] = total_unprocessed

        if total_unprocessed == 0:
            task['status'] = 'completed'
            task['finished_at'] = datetime.utcnow().isoformat()
            logger.info(f"AI task {task_id} completed: no unprocessed news")
            return

        effective_workers = max(
            1,
            min(total_unprocessed, max_workers, int(os.getenv('AI_MAX_WORKERS', str(max_workers))))
        )
        task['max_workers'] = effective_workers

        # Process all items once, chunked by batch_size and executed concurrently per chunk
        processed_count = 0
        failed_count = 0

        def process_one(news_item):
            processor = NewsProcessor()
            try:
                processor.process_single_news(news_item)
                return True, None, news_item.get('title', '')
            except Exception as e:
                return False, str(e), news_item.get('title', '')
            finally:
                try:
                    processor.close_mongodb()
                except Exception:
                    pass

        for start in range(0, total_unprocessed, batch_size):
            chunk = unprocessed_news[start:start + batch_size]
            workers = max(1, min(effective_workers, len(chunk)))

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(process_one, news_item) for news_item in chunk]
                for future in as_completed(futures):
                    success, error, title = future.result()
                    if success:
                        processed_count += 1
                        task['processed_count'] = processed_count
                    else:
                        failed_count += 1
                        task['failed_count'] = failed_count
                        task['logs'].append(f"Failed to process {title}: {error[:100]}")
                        logger.error(f"AI processing error: {error}")

        task['processed_count'] = processed_count
        task['failed_count'] = failed_count
        task['status'] = 'completed'
        task['finished_at'] = datetime.utcnow().isoformat()
        logger.info(f"AI task {task_id} completed: {processed_count} processed, {failed_count} failed")

    except Exception as e:
        task['status'] = 'failed'
        task['error'] = str(e)
        task['finished_at'] = datetime.utcnow().isoformat()
        logger.error(f"AI task {task_id} failed: {e}")


@router.post("/process", status_code=202)
def trigger_ai_processing(req: ProcessRequest):
    batch_size = req.batch_size
    max_workers = req.max_workers

    task_id = str(uuid.uuid4())
    _ai_tasks[task_id] = {
        'task_id': task_id,
        'status': 'pending',
        'batch_size': batch_size,
        'max_workers': max_workers,
        'total_to_process': 0,
        'processed_count': 0,
        'failed_count': 0,
        'logs': [],
        'created_at': datetime.utcnow().isoformat(),
        'started_at': None,
        'finished_at': None,
        'error': None
    }

    thread = threading.Thread(
        target=_run_ai_processing,
        args=(task_id, batch_size, max_workers),
        daemon=True
    )
    thread.start()

    logger.info(
        f"AI processing task {task_id} triggered with batch_size={batch_size}, max_workers={max_workers}"
    )
    return {
        'success': True,
        'task_id': task_id,
        'status': 'pending',
        'message': 'AI processing task started'
    }


@router.get("/status/{task_id}")
def get_ai_status(task_id: str):
    task = _ai_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    return {'success': True, 'data': task}


@router.post("/retry")
def retry_failed_news(req: RetryRequest):
    news_ids = req.news_ids

    try:
        mongo_db = DatabaseManager.get_mongo_db()

        if news_ids:
            from bson import ObjectId
            result = mongo_db.news_raw.update_many(
                {'_id': {'$in': [ObjectId(nid) for nid in news_ids]}},
                {'$set': {'is_processed': False}}
            )
            count = result.modified_count
        else:
            result = mongo_db.news_raw.update_many(
                {'is_processed': True},
                {'$set': {'is_processed': False}}
            )
            count = result.modified_count

        logger.info(f"Reset {count} news items for retry")
        return {
            'success': True,
            'message': f'{count} news items marked for retry',
            'count': count
        }

    except Exception as e:
        logger.error(f"retry_failed_news error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
