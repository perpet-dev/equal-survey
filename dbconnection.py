from mysql.connector import pooling
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_DATABASE
import logging

logger = logging.getLogger(__name__)

class DatabaseConnectionPool:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if DatabaseConnectionPool._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            self.pool = self.create_pool()

    def create_pool(self):
        try:
            pool = pooling.MySQLConnectionPool(
                pool_name="app_pool",
                pool_size=3,
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_DATABASE
            )
            print('Database connection pool successfully established.')
            return pool
        except Exception as e:
            logger.error(f"Error connecting to the database platform: {e}")
            return None

    def get_connection(self):
        try:
            return self.pool.get_connection()
        except Exception as e:
            logger.error(f"Error getting connection from pool: {e}")
            return None
