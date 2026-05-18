"""
Configuration for Flask Application
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # MySQL Configuration
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '123456')
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'ai_news')

    # MongoDB Configuration
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
    MONGO_DATABASE = os.getenv('MONGO_DATABASE', 'ai_news')

    # Redis Configuration
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))

    # API Keys
    ZHIPU_AI_API_KEY = os.getenv('ZHIPU_AI_API_KEY')
    INWORLD_API_KEY = os.getenv('INWORLD_API_KEY')

    # Tencent COS
    TENCENT_COS_SECRET_ID = os.getenv('TENCENT_COS_SECRET_ID')
    TENCENT_COS_SECRET_KEY = os.getenv('TENCENT_COS_SECRET_KEY')

    # Scrapy Settings
    SCRAPY_PROJECT_PATH = os.path.join(os.path.dirname(__file__), 'scrapers')

    # Processor Settings
    PROCESSOR_BATCH_SIZE = 10

    # WeChat Mini-Program
    WX_APPID = os.getenv('WX_APPID', 'wxdfb0b03f34f11887')
    WX_SECRET = os.getenv('WX_SECRET', '')

    # Testing
    TESTING = False
