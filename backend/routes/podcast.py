"""
Podcast API Routes
POST /api/podcast/generate
POST /api/podcast/tts
GET  /api/podcast/list
GET  /api/podcast/{podcast_id}
GET  /api/podcast/{podcast_id}/audio  — stream audio via proxy
"""
import os
import sys
import uuid
import threading
import httpx
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from utils.db import get_db_connection
from utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/api/podcast", tags=["podcast"])

_podcast_tasks = {}


class PodcastGenerateRequest(BaseModel):
    date: Optional[str] = None


def _run_podcast_generation(task_id: str, target_date: str):
    """Background thread: generate podcast script and audio."""
    task = _podcast_tasks[task_id]
    task['status'] = 'running'
    task['started_at'] = datetime.utcnow().isoformat()

    try:
        # Import TTS module
        tts_path = os.path.join(os.path.dirname(__file__), '..', 'tts')
        sys.path.insert(0, tts_path)
        from daily_podcast_generator import generate_daily_podcast

        # Generate podcast (existing function generates for current day)
        podcast_id = generate_daily_podcast()

        # Fetch the generated podcast from database
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT id, audio_url, duration FROM podcasts WHERE id = %s',
                    (podcast_id,)
                )
                result = cursor.fetchone()

        if result:
            task['status'] = 'completed'
            task['podcast_id'] = result['id']
            task['audio_url'] = result['audio_url']
            task['duration'] = result['duration']
        else:
            raise Exception("Podcast generated but not found in database")

        task['finished_at'] = datetime.utcnow().isoformat()
        logger.info(f"Podcast task {task_id} completed: podcast_id={podcast_id}")

    except Exception as e:
        task['status'] = 'failed'
        task['error'] = str(e)
        task['finished_at'] = datetime.utcnow().isoformat()
        logger.error(f"Podcast task {task_id} failed: {e}")


@router.post("/generate", status_code=202)
def generate_podcast(req: PodcastGenerateRequest):
    target_date = req.date or str(date.today())

    try:
        datetime.strptime(target_date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid date format. Use YYYY-MM-DD')

    task_id = str(uuid.uuid4())
    _podcast_tasks[task_id] = {
        'task_id': task_id,
        'status': 'pending',
        'date': target_date,
        'podcast_id': None,
        'audio_url': None,
        'duration': None,
        'created_at': datetime.utcnow().isoformat(),
        'started_at': None,
        'finished_at': None,
        'error': None
    }

    thread = threading.Thread(
        target=_run_podcast_generation,
        args=(task_id, target_date),
        daemon=True
    )
    thread.start()

    logger.info(f"Podcast generation task {task_id} triggered for date={target_date}")
    return {
        'success': True,
        'task_id': task_id,
        'status': 'pending',
        'message': f'Podcast generation started for {target_date}'
    }


@router.post("/tts", status_code=202)
def generate_podcast_tts(req: PodcastGenerateRequest):
    return generate_podcast(req)


@router.get("/list")
def get_podcast_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    offset = (page - 1) * page_size

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) AS total FROM podcasts')
                total = cursor.fetchone()['total']

                cursor.execute(
                    '''SELECT id, title, audio_url, duration, created_at
                       FROM podcasts
                       ORDER BY created_at DESC
                       LIMIT %s OFFSET %s''',
                    (page_size, offset)
                )
                rows = cursor.fetchall()

        for row in rows:
            if row.get('created_at'):
                row['created_at'] = str(row['created_at'])

        return {
            'success': True,
            'data': {
                'list': rows,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                    'total_pages': (total + page_size - 1) // page_size
                }
            }
        }
    except Exception as e:
        logger.error(f"get_podcast_list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{podcast_id}")
def get_podcast_detail(podcast_id: int):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM podcasts WHERE id = %s', (podcast_id,))
                podcast = cursor.fetchone()
                if not podcast:
                    raise HTTPException(status_code=404, detail='Podcast not found')

                podcast['vocabulary'] = []

                cursor.execute(
                    '''SELECT n.id, n.title, n.category, n.cover_image
                       FROM news n
                       JOIN podcast_news_mapping pnm ON n.id = pnm.news_id
                       WHERE pnm.podcast_id = %s''',
                    (podcast_id,)
                )
                podcast['news'] = cursor.fetchall()

        if podcast.get('created_at'):
            podcast['created_at'] = str(podcast['created_at'])

        return {'success': True, 'data': podcast}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_podcast_detail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{podcast_id}/audio")
async def proxy_podcast_audio(podcast_id: int):
    """Stream podcast audio from COS via proxy, so InnerAudioContext works on real devices."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT audio_url FROM podcasts WHERE id = %s', (podcast_id,))
                row = cursor.fetchone()
        if not row or not row.get('audio_url'):
            raise HTTPException(status_code=404, detail='Audio not found')

        audio_url = row['audio_url']
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(audio_url)
            resp.raise_for_status()
            content_type = resp.headers.get('content-type', 'audio/mpeg')
            return StreamingResponse(
                iter([resp.content]),
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"proxy_podcast_audio error: {e}")
        raise HTTPException(status_code=502, detail=str(e))
