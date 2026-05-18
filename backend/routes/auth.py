"""
Auth API Routes
POST /api/auth/login   - WeChat login via code
POST /api/auth/history - Record reading history
GET  /api/auth/history - Get user reading history
"""
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from config import Config
from utils.db import get_db_connection
from utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    code: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None


class HistoryRequest(BaseModel):
    user_id: str
    news_id: int


@router.post("/login")
async def wechat_login(body: LoginRequest):
    """Exchange WeChat code for openid, upsert user, return openid."""
    url = (
        f"https://api.weixin.qq.com/sns/jscode2session"
        f"?appid={Config.WX_APPID}"
        f"&secret={Config.WX_SECRET}"
        f"&js_code={body.code}"
        f"&grant_type=authorization_code"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
        wx_data = resp.json()
    except Exception as e:
        logger.error(f"WeChat API error: {e}")
        raise HTTPException(status_code=502, detail="WeChat API unreachable")

    if "errcode" in wx_data and wx_data["errcode"] != 0:
        logger.error(f"WeChat login failed: {wx_data}")
        raise HTTPException(status_code=400, detail=wx_data.get("errmsg", "WeChat login failed"))

    openid = wx_data.get("openid")
    if not openid:
        raise HTTPException(status_code=400, detail="No openid returned")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO users (openid, nickname, avatar_url)
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE
                         last_login = CURRENT_TIMESTAMP,
                         nickname = COALESCE(%s, nickname),
                         avatar_url = COALESCE(%s, avatar_url)""",
                    (openid, body.nickname, body.avatar_url, body.nickname, body.avatar_url)
                )
                cursor.execute("SELECT * FROM users WHERE openid = %s", (openid,))
                user = cursor.fetchone()
                for field in ("created_at", "last_login"):
                    if user.get(field):
                        user[field] = str(user[field])
    except Exception as e:
        logger.error(f"DB error on login: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"success": True, "data": {"openid": openid, "user": user}}


@router.post("/history")
def record_history(body: HistoryRequest):
    """Record or refresh a reading history entry (upsert)."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO reading_history (user_id, news_id, read_at)
                       VALUES (%s, %s, CURRENT_TIMESTAMP)
                       ON DUPLICATE KEY UPDATE read_at = CURRENT_TIMESTAMP""",
                    (body.user_id, body.news_id)
                )
    except Exception as e:
        logger.error(f"record_history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"success": True}


@router.get("/history")
def get_history(user_id: str, page: int = 1, page_size: int = 20):
    """Return paginated reading history for a user."""
    offset = (page - 1) * page_size
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) AS total FROM reading_history WHERE user_id = %s",
                    (user_id,)
                )
                total = cursor.fetchone()["total"]

                cursor.execute(
                    """SELECT rh.read_at,
                              n.id, n.title, n.category, n.cover_image,
                              n.en_summary, n.difficulty_score, n.source,
                              n.publish_date, n.hot_score
                       FROM reading_history rh
                       JOIN news n ON n.id = rh.news_id
                       WHERE rh.user_id = %s
                       ORDER BY rh.read_at DESC
                       LIMIT %s OFFSET %s""",
                    (user_id, page_size, offset)
                )
                rows = cursor.fetchall()

        for row in rows:
            for field in ("read_at", "publish_date"):
                if row.get(field):
                    row[field] = str(row[field])

        return {
            "success": True,
            "data": {
                "list": rows,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size
                }
            }
        }
    except Exception as e:
        logger.error(f"get_history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
