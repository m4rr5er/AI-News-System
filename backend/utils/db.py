"""
Database connection utilities
"""
import pymysql
from pymongo import MongoClient
import redis
from contextlib import contextmanager
from config import Config

class DatabaseManager:
    """Singleton database manager"""
    _mysql_pool = None
    _mongo_client = None
    _redis_client = None

    @classmethod
    def get_mysql_connection(cls):
        """Get MySQL connection from pool"""
        return pymysql.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

    @classmethod
    def get_mongo_db(cls):
        """Get MongoDB database instance"""
        if cls._mongo_client is None:
            cls._mongo_client = MongoClient(Config.MONGO_URI)
        return cls._mongo_client[Config.MONGO_DATABASE]

    @classmethod
    def get_redis_client(cls):
        """Get Redis client instance"""
        if cls._redis_client is None:
            cls._redis_client = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
                decode_responses=True
            )
        return cls._redis_client

@contextmanager
def get_db_connection():
    """Context manager for MySQL connection"""
    conn = DatabaseManager.get_mysql_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
