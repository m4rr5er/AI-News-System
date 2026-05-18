"""
Admin/System API Routes
GET  /api/admin/stats
POST /api/admin/cleanup
GET  /api/admin/health
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from utils.db import DatabaseManager, get_db_connection
from utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


class CleanupRequest(BaseModel):
    days: int = Field(default=30, ge=1)


@router.get("/stats")
def get_system_stats():
    try:
        stats = {}

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) AS total FROM news')
                stats['total_news'] = cursor.fetchone()['total']

                cursor.execute(
                    '''SELECT COUNT(*) AS today_count FROM news
                       WHERE DATE(created_at) = CURDATE()'''
                )
                stats['today_news'] = cursor.fetchone()['today_count']

                cursor.execute(
                    '''SELECT category, COUNT(*) AS count
                       FROM news
                       GROUP BY category
                       ORDER BY count DESC'''
                )
                stats['category_distribution'] = cursor.fetchall()

                cursor.execute(
                    '''SELECT source, COUNT(*) AS count
                       FROM news
                       GROUP BY source
                       ORDER BY count DESC'''
                )
                stats['source_distribution'] = cursor.fetchall()

                cursor.execute('SELECT COUNT(*) AS total FROM vocabulary')
                stats['total_vocabulary'] = cursor.fetchone()['total']

                cursor.execute('SELECT COUNT(*) AS total FROM podcasts')
                stats['total_podcasts'] = cursor.fetchone()['total']

        mongo_db = DatabaseManager.get_mongo_db()
        stats['mongo_raw_news'] = mongo_db.news_raw.count_documents({})
        stats['mongo_unprocessed'] = mongo_db.news_raw.count_documents({'is_processed': False})
        stats['mongo_processed'] = mongo_db.news_raw.count_documents({'is_processed': True})

        redis_client = DatabaseManager.get_redis_client()
        stats['redis_url_count'] = redis_client.scard('news:urls')

        return {'success': True, 'data': stats}

    except Exception as e:
        logger.error(f"get_system_stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
def cleanup_old_data(req: CleanupRequest):
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=req.days)

        mongo_db = DatabaseManager.get_mongo_db()
        result = mongo_db.news_raw.delete_many({
            'is_processed': True,
            'crawl_date': {'$lt': cutoff_date}
        })
        deleted_count = result.deleted_count

        logger.info(f"Cleaned up {deleted_count} processed news older than {req.days} days")
        return {
            'success': True,
            'message': f'Deleted {deleted_count} processed news items older than {req.days} days',
            'deleted_count': deleted_count
        }

    except Exception as e:
        logger.error(f"cleanup_old_data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
def health_check(response: Response):
    health = {
        'mysql': False,
        'mongodb': False,
        'redis': False,
        'glm_api': False
    }

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT 1')
                health['mysql'] = True
    except Exception as e:
        logger.error(f"MySQL health check failed: {e}")

    try:
        mongo_db = DatabaseManager.get_mongo_db()
        mongo_db.command('ping')
        health['mongodb'] = True
    except Exception as e:
        logger.error(f"MongoDB health check failed: {e}")

    try:
        redis_client = DatabaseManager.get_redis_client()
        redis_client.ping()
        health['redis'] = True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")

    try:
        import os
        from zhipuai import ZhipuAI
        api_key = os.getenv('ZHIPU_AI_API_KEY')
        if api_key:
            client = ZhipuAI(api_key=api_key)
            resp = client.chat.completions.create(
                model="glm-4-air",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=10
            )
            if resp.choices:
                health['glm_api'] = True
    except Exception as e:
        logger.error(f"GLM API health check failed: {e}")

    all_healthy = all(health.values())
    response.status_code = 200 if all_healthy else 503

    return {
        'success': all_healthy,
        'services': health,
        'timestamp': datetime.utcnow().isoformat()
    }
