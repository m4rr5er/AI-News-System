"""
Vocabulary API Routes
GET  /api/user/vocabulary
POST /api/user/vocabulary/toggle
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from utils.db import get_db_connection
from utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/api/user", tags=["vocabulary"])


class ToggleVocabularyRequest(BaseModel):
    user_id: str
    word: str
    news_id: int


@router.get("/vocabulary")
def get_user_vocabulary(
    user_id: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    offset = (page - 1) * page_size

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT COUNT(*) AS total FROM user_vocabulary WHERE user_id = %s',
                    (user_id,)
                )
                total = cursor.fetchone()['total']

                cursor.execute(
                    '''SELECT uv.id, uv.word, uv.news_id, uv.collected_at,
                              v.phonetic, v.translation, v.explanation, v.example_sentence
                       FROM user_vocabulary uv
                       LEFT JOIN vocabulary v ON uv.word = v.word AND uv.news_id = v.news_id
                       WHERE uv.user_id = %s
                       ORDER BY uv.collected_at DESC
                       LIMIT %s OFFSET %s''',
                    (user_id, page_size, offset)
                )
                rows = cursor.fetchall()

        for row in rows:
            if row.get('collected_at'):
                row['collected_at'] = str(row['collected_at'])

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
        logger.error(f"get_user_vocabulary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vocabulary/toggle")
def toggle_vocabulary(req: ToggleVocabularyRequest):
    if not req.user_id or not req.word:
        raise HTTPException(status_code=400, detail='user_id and word are required')

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''SELECT id FROM user_vocabulary
                       WHERE user_id = %s AND word = %s AND news_id = %s''',
                    (req.user_id, req.word, req.news_id)
                )
                existing = cursor.fetchone()

                if existing:
                    cursor.execute(
                        'DELETE FROM user_vocabulary WHERE id = %s',
                        (existing['id'],)
                    )
                    action = 'removed'
                else:
                    cursor.execute(
                        '''INSERT INTO user_vocabulary (user_id, word, news_id, collected_at)
                           VALUES (%s, %s, %s, NOW())''',
                        (req.user_id, req.word, req.news_id)
                    )
                    action = 'added'

        logger.info(f"User {req.user_id} {action} word '{req.word}' from news {req.news_id}")
        return {
            'success': True,
            'action': action,
            'message': f'Word {action} successfully'
        }

    except Exception as e:
        logger.error(f"toggle_vocabulary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
