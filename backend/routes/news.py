"""
News Data API Routes
GET /api/news/list
GET /api/news/categories
GET /api/news/{news_id}
GET /api/news/{news_id}/sentiments
"""
import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from utils.db import get_db_connection
from utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/list")
def get_news_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    category: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    conditions = []
    params = []

    if category:
        conditions.append('category = %s')
        params.append(category)
    if source:
        conditions.append('source = %s')
        params.append(source)
    if date_from:
        conditions.append('publish_date >= %s')
        params.append(date_from)
    if date_to:
        conditions.append('publish_date <= %s')
        params.append(date_to)

    where_clause = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
    offset = (page - 1) * page_size

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f'SELECT COUNT(*) AS total FROM news {where_clause}',
                    params
                )
                total = cursor.fetchone()['total']

                cursor.execute(
                    f'''SELECT id, title, category, source,
                               cover_image, en_summary, difficulty_score,
                               tags, publish_date, view_count, hot_score
                        FROM news {where_clause}
                        ORDER BY hot_score DESC, publish_date DESC
                        LIMIT %s OFFSET %s''',
                    params + [page_size, offset]
                )
                rows = cursor.fetchall()

        for row in rows:
            if isinstance(row.get('tags'), str):
                try:
                    row['tags'] = json.loads(row['tags'])
                except Exception:
                    row['tags'] = []
            if row.get('publish_date'):
                row['publish_date'] = str(row['publish_date'])

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
        logger.error(f"get_news_list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
def get_categories():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''SELECT category, COUNT(*) AS count
                       FROM news
                       GROUP BY category
                       ORDER BY count DESC'''
                )
                rows = cursor.fetchall()
        return {'success': True, 'data': rows}
    except Exception as e:
        logger.error(f"get_categories error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
def search_news(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    keyword = f"%{q}%"
    offset = (page - 1) * page_size

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''SELECT COUNT(*) AS total FROM news
                       WHERE title LIKE %s OR en_summary LIKE %s OR tags LIKE %s''',
                    [keyword, keyword, keyword]
                )
                total = cursor.fetchone()['total']

                cursor.execute(
                    '''SELECT id, title, category, source,
                              cover_image, en_summary, difficulty_score,
                              tags, publish_date, view_count, hot_score
                       FROM news
                       WHERE title LIKE %s OR en_summary LIKE %s OR tags LIKE %s
                       ORDER BY hot_score DESC, publish_date DESC
                       LIMIT %s OFFSET %s''',
                    [keyword, keyword, keyword, page_size, offset]
                )
                rows = cursor.fetchall()

        for row in rows:
            if isinstance(row.get('tags'), str):
                try:
                    row['tags'] = json.loads(row['tags'])
                except Exception:
                    row['tags'] = []
            if row.get('publish_date'):
                row['publish_date'] = str(row['publish_date'])

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
        logger.error(f"search_news error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{news_id}")
def get_news_detail(news_id: int):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM news WHERE id = %s', (news_id,))
                news = cursor.fetchone()
                if not news:
                    raise HTTPException(status_code=404, detail='News not found')

                cursor.execute(
                    'UPDATE news SET view_count = view_count + 1 WHERE id = %s',
                    (news_id,)
                )

                cursor.execute(
                    'SELECT * FROM background_info WHERE news_id = %s',
                    (news_id,)
                )
                news['background_info'] = cursor.fetchall()

                cursor.execute(
                    'SELECT * FROM viewpoint_analysis WHERE news_id = %s',
                    (news_id,)
                )
                news['viewpoint_analysis'] = cursor.fetchall()

        for field in ('tags', 'qa_suggestions'):
            if isinstance(news.get(field), str):
                try:
                    news[field] = json.loads(news[field])
                except Exception:
                    news[field] = []
        for field in ('publish_date', 'created_at', 'updated_at'):
            if news.get(field):
                news[field] = str(news[field])

        return {'success': True, 'data': news}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_news_detail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{news_id}/sentiments")
def get_news_sentiments(news_id: int):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''SELECT id, entity_name, viewpoint, sentiment
                       FROM viewpoint_analysis WHERE news_id = %s''',
                    (news_id,)
                )
                sentiments = cursor.fetchall()
        return {'success': True, 'data': sentiments}
    except Exception as e:
        logger.error(f"get_news_sentiments error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
