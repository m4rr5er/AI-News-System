"""
FastAPI Application Entry Point
AI News Platform Backend API
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import Config
from routes import register_routers
from utils.scheduler import init_scheduler, start_continuous_processing
from utils.logger import setup_logger

logger = setup_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="AI News API")

    # Enable CORS for WeChat mini-program
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register all routers
    register_routers(app)

    # Initialize scheduler for background tasks
    init_scheduler(app)

    # Start continuous processing of unprocessed news
    start_continuous_processing()

    logger.info("FastAPI application initialized successfully")
    return app


app = create_app()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
