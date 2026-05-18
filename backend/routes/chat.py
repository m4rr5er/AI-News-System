"""
Chat/QA API Routes
POST /api/chat/question
"""
import os
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.db import get_db_connection
from utils.logger import setup_logger
from zai import ZhipuAiClient

logger = setup_logger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

# Keywords that suggest the question is about the news article
NEWS_RELATED_KEYWORDS = [
    'article', 'news', 'this', 'story', 'report', 'author', 'said', 'according',
    'mentioned', 'content', 'title', 'summary', 'what does', 'what did', 'who is',
    'why did', 'how did', 'when did', 'where did', 'explain', 'mean', 'context',
    '文章', '新闻', '这篇', '报道', '作者', '说', '提到', '内容', '标题', '摘要',
    '解释', '意思', '背景', '为什么', '怎么', '什么时候', '在哪'
]


def _is_news_related(question: str) -> bool:
    """Heuristic: check if the question is likely about the news article."""
    q_lower = question.lower()
    return any(kw in q_lower for kw in NEWS_RELATED_KEYWORDS)


class Message(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class QuestionRequest(BaseModel):
    news_id: int
    question: str
    history: Optional[List[Message]] = None   # previous turns


@router.post("/question")
def ask_question(req: QuestionRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail='question is required')

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT title, content, en_summary FROM news WHERE id = %s',
                    (req.news_id,)
                )
                news = cursor.fetchone()
                if not news:
                    raise HTTPException(status_code=404, detail='News not found')

        api_key = os.getenv('ZHIPU_AI_API_KEY')
        if not api_key:
            raise HTTPException(status_code=500, detail='GLM API key not configured')

        client = ZhipuAiClient(api_key=api_key)

        # Build system prompt
        system_content = (
            "You are a helpful AI assistant embedded in a news reading app. "
            "Always respond in English unless the user explicitly asks you to use another language. "
            "Be concise and accurate."
        )

        # Decide whether to inject news context
        include_news = _is_news_related(req.question) or not (req.history and len(req.history) > 0)

        if include_news:
            news_context = (
                f"[News Article]\n"
                f"Title: {news['title']}\n"
                f"Summary: {news['en_summary']}\n"
                f"Full Content:\n{news['content']}\n"
                f"[End of Article]\n\n"
            )
            first_user_content = news_context + f"User question: {req.question}"
        else:
            first_user_content = req.question

        # Build messages list: system + history + current question
        messages = [{"role": "system", "content": system_content}]

        history = req.history or []
        if history:
            # Inject news context into the very first user message of history
            first_hist = history[0]
            if first_hist.role == "user" and include_news:
                # Already injected above; just append history as-is
                pass
            for msg in history:
                messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": first_user_content})

        # Web search tool (always enabled)
        tools = [{
            "type": "web_search",
            "web_search": {
                "enable": "True",
                "search_engine": "search_pro",
                "search_result": "True",
                "search_prompt": (
                    "你是一位新闻分析师。请用简洁的语言总结网络搜索{search_result}中的关键信息，"
                    "按重要性排序并引用来源。"
                ),
                "count": "5",
                "search_recency_filter": "noLimit",
                "content_size": "medium"
            }
        }]

        response = client.chat.completions.create(
            model="glm-4-air",
            messages=messages,
            tools=tools,
            temperature=0.7,
            max_tokens=800
        )

        answer = response.choices[0].message.content
        logger.info(f"QA news={req.news_id} q={req.question[:50]!r}")

        return {
            'success': True,
            'data': {
                'answer': answer,
                'news_id': req.news_id,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ask_question error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
