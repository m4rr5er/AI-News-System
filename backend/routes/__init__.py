"""
Router registration
"""
from fastapi import FastAPI


def register_routers(app: FastAPI):
    """Register all routers"""
    from routes.crawler import router as crawler_router
    from routes.news import router as news_router
    from routes.ai import router as ai_router
    from routes.chat import router as chat_router
    from routes.podcast import router as podcast_router
    from routes.admin import router as admin_router
    from routes.knowledge_graph import router as kg_router
    from routes.dict import router as dict_router
    from routes.auth import router as auth_router

    app.include_router(crawler_router)
    app.include_router(news_router)
    app.include_router(ai_router)
    app.include_router(chat_router)
    app.include_router(podcast_router)
    app.include_router(admin_router)
    app.include_router(kg_router)
    app.include_router(dict_router)
    app.include_router(auth_router)
