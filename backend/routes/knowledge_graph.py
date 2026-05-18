"""
Knowledge Graph API Routes
GET /api/knowledge-graph/entities
GET /api/knowledge-graph/trends
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from utils.db import get_db_connection
from utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/api/knowledge-graph", tags=["knowledge_graph"])


@router.get("/entities")
def get_entity_graph(
    news_id: Optional[str] = None,
    topic: Optional[str] = None,
):
    if not news_id and not topic:
        raise HTTPException(status_code=400, detail='news_id or topic is required')

    try:
        nodes = []
        edges = []

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                if news_id:
                    cursor.execute(
                        '''SELECT DISTINCT subject_entity, object_entity, relation
                           FROM entity_relation WHERE news_id = %s''',
                        (news_id,)
                    )
                    relations = cursor.fetchall()

                    entity_set = set()
                    for rel in relations:
                        entity_set.add(rel['subject_entity'])
                        entity_set.add(rel['object_entity'])
                        edges.append({
                            'source': rel['subject_entity'],
                            'target': rel['object_entity'],
                            'relation': rel['relation']
                        })

                    if entity_set:
                        placeholders = ','.join(['%s'] * len(entity_set))
                        cursor.execute(
                            f'''SELECT entity_name, entity_type, description
                               FROM background_info
                               WHERE news_id = %s AND entity_name IN ({placeholders})''',
                            [news_id] + list(entity_set)
                        )
                        entity_details = {row['entity_name']: row for row in cursor.fetchall()}
                        cursor.execute(
                            f'''SELECT entity_name, COUNT(DISTINCT news_id) AS article_count
                               FROM (
                                   SELECT subject_entity AS entity_name, news_id FROM entity_relation
                                   WHERE subject_entity IN ({placeholders})
                                   UNION ALL
                                   SELECT object_entity AS entity_name, news_id FROM entity_relation
                                   WHERE object_entity IN ({placeholders})
                               ) t
                               GROUP BY entity_name''',
                            list(entity_set) + list(entity_set)
                        )
                        entity_counts = {row['entity_name']: row['article_count'] for row in cursor.fetchall()}

                        for entity in entity_set:
                            detail = entity_details.get(entity, {})
                            nodes.append({
                                'id': entity,
                                'label': entity,
                                'type': detail.get('entity_type', 'Unknown'),
                                'description': detail.get('description', ''),
                                'article_count': entity_counts.get(entity, 0)
                            })

                elif topic:
                    cursor.execute(
                        '''SELECT er.subject_entity, er.object_entity, er.relation,
                                  MAX(bi.entity_type) AS entity_type,
                                  MAX(bi.description) AS description,
                                  COUNT(DISTINCT er.news_id) AS relation_count
                           FROM entity_relation er
                           LEFT JOIN background_info bi ON er.subject_entity = bi.entity_name
                           JOIN news n ON er.news_id = n.id
                           WHERE er.subject_entity LIKE %s OR er.object_entity LIKE %s
                           GROUP BY er.subject_entity, er.object_entity, er.relation
                           ORDER BY relation_count DESC, MAX(n.publish_date) DESC
                           LIMIT 80''',
                        (f'%{topic}%', f'%{topic}%')
                    )
                    relations = cursor.fetchall()

                    entity_details = {}
                    entity_set = set()
                    for rel in relations:
                        entity_set.add(rel['subject_entity'])
                        entity_set.add(rel['object_entity'])
                        edges.append({
                            'source': rel['subject_entity'],
                            'target': rel['object_entity'],
                            'relation': rel['relation']
                        })
                        # Collect description from the LEFT JOIN on subject_entity
                        if rel['subject_entity'] not in entity_details and rel.get('description'):
                            entity_details[rel['subject_entity']] = {
                                'entity_type': rel.get('entity_type', 'Unknown'),
                                'description': rel.get('description', '')
                            }

                    # For object_entities not covered by the JOIN, do a second lookup
                    missing = entity_set - set(entity_details.keys())
                    if missing:
                        placeholders = ','.join(['%s'] * len(missing))
                        cursor.execute(
                            f'''SELECT entity_name, entity_type, description
                               FROM background_info
                               WHERE entity_name IN ({placeholders})
                               ORDER BY id DESC''',
                            list(missing)
                        )
                        for row in cursor.fetchall():
                            if row['entity_name'] not in entity_details:
                                entity_details[row['entity_name']] = {
                                    'entity_type': row['entity_type'],
                                    'description': row['description']
                                }

                    entity_counts = {}
                    if entity_set:
                        placeholders = ','.join(['%s'] * len(entity_set))
                        cursor.execute(
                            f'''SELECT entity_name, COUNT(DISTINCT news_id) AS article_count
                               FROM (
                                   SELECT subject_entity AS entity_name, news_id FROM entity_relation
                                   WHERE subject_entity IN ({placeholders})
                                   UNION ALL
                                   SELECT object_entity AS entity_name, news_id FROM entity_relation
                                   WHERE object_entity IN ({placeholders})
                               ) t
                               GROUP BY entity_name''',
                            list(entity_set) + list(entity_set)
                        )
                        entity_counts = {row['entity_name']: row['article_count'] for row in cursor.fetchall()}

                    for entity in entity_set:
                        detail = entity_details.get(entity, {})
                        nodes.append({
                            'id': entity,
                            'label': entity,
                            'type': detail.get('entity_type', 'Unknown'),
                            'description': detail.get('description', ''),
                            'article_count': entity_counts.get(entity, 0)
                        })

        return {
            'success': True,
            'data': {
                'nodes': nodes,
                'edges': edges
            }
        }

    except Exception as e:
        logger.error(f"get_entity_graph error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends")
def get_topic_trends(
    topic: str = Query(...),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                conditions = ['(title LIKE %s OR content LIKE %s OR tags LIKE %s)']
                params = [f'%{topic}%', f'%{topic}%', f'%{topic}%']

                if date_from:
                    conditions.append('publish_date >= %s')
                    params.append(date_from)
                if date_to:
                    conditions.append('publish_date <= %s')
                    params.append(date_to)

                where_clause = 'WHERE ' + ' AND '.join(conditions)

                cursor.execute(
                    f'''SELECT DATE(publish_date) AS date, COUNT(*) AS count
                       FROM news {where_clause}
                       GROUP BY DATE(publish_date)
                       ORDER BY date ASC''',
                    params
                )
                trends = cursor.fetchall()

        for row in trends:
            if row.get('date'):
                row['date'] = str(row['date'])

        return {
            'success': True,
            'data': {
                'topic': topic,
                'trends': trends
            }
        }

    except Exception as e:
        logger.error(f"get_topic_trends error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending-entities")
def get_trending_entities(
    days: int = Query(7, description="Number of days to look back"),
    limit: int = Query(10, description="Maximum number of entities to return")
):
    """
    Get trending entities ranked by article count in the past N days
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''SELECT
                        er.subject_entity AS entity_name,
                        MAX(bi.entity_type) AS entity_type,
                        COUNT(DISTINCT er.news_id) AS article_count
                    FROM entity_relation er
                    LEFT JOIN background_info bi ON er.subject_entity = bi.entity_name
                    JOIN news n ON er.news_id = n.id
                    WHERE n.publish_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
                    GROUP BY er.subject_entity
                    ORDER BY article_count DESC
                    LIMIT %s''',
                    (days, limit)
                )
                entities = cursor.fetchall()

        return {
            'success': True,
            'data': {
                'entities': entities,
                'days': days
            }
        }

    except Exception as e:
        logger.error(f"get_trending_entities error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity-articles")
def get_entity_articles(
    entity: str = Query(..., description="Entity name to search for"),
    limit: int = Query(5, description="Maximum number of articles to return")
):
    """
    Get news articles related to a specific entity
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''SELECT DISTINCT n.id, n.title, n.en_summary, n.publish_date, n.source, n.cover_image
                       FROM news n
                       JOIN entity_relation er ON n.id = er.news_id
                       WHERE er.subject_entity = %s OR er.object_entity = %s
                       ORDER BY n.publish_date DESC
                       LIMIT %s''',
                    (entity, entity, limit)
                )
                articles = cursor.fetchall()

        for row in articles:
            if row.get('publish_date'):
                row['publish_date'] = str(row['publish_date'])

        return {
            'success': True,
            'data': {
                'entity': entity,
                'list': articles
            }
        }

    except Exception as e:
        logger.error(f"get_entity_articles error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
