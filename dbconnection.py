import mysql.connector
from mysql.connector import pooling
import time
from mysql.connector import Error
import logging
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_DATABASE

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
        # try:
        #     pool = pooling.MySQLConnectionPool(
        #         pool_name="surveys_pool",
        #         pool_reset_session=True,
        #         pool_size=5,
        #         host=DB_HOST,
        #         port=DB_PORT,
        #         user=DB_USER,
        #         password=DB_PASSWORD,
        #         database=DB_DATABASE,
        #         charset='utf8mb4',
        #         collation='utf8mb4_general_ci'
        #     )
        #     logger.info("Database connection pool successfully established.")
        #     return pool
        # except Error as e:
        #     logger.error(f"Error connecting to the database platform: {e}")
        #     return None
        # Retry configuration
        MAX_RETRIES = 5
        RETRY_DELAY = 5  # in seconds
        retries = 0
        connection_pool = None

        while retries < MAX_RETRIES:
            try:
                connection_pool = mysql.connector.pooling.MySQLConnectionPool(
                    pool_name="surveys_pool",
                    pool_size=5,  # Adjust pool size as needed
                    pool_reset_session=True,
                    host=DB_HOST,
                    database=DB_DATABASE,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    port=DB_PORT,
                    charset='utf8mb4',
                    collation='utf8mb4_general_ci'
                )
                logger.info("Connection pool created successfully.")
                break  # Exit the loop if the connection pool is created successfully
            except Error as e:
                retries += 1
                logger.error(f"Error creating connection pool: {e}")
                if retries < MAX_RETRIES:
                    logger.info(f"Retrying to create connection pool in {RETRY_DELAY} seconds... (Attempt {retries}/{MAX_RETRIES})")
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error("Max retries reached. Failed to create connection pool.")
                    break

        return connection_pool

    def get_connection(self):
        try:
            if self.pool:
                return self.pool.get_connection()
            else:
                logger.error("Connection pool not initialized.")
                return None
        except Error as e:
            logger.error(f"Error getting connection from pool: {e}")
            return None
        
    def close_connection(self, connection):
        if connection:
            try:
                # Check if connection is not None and is connected
                if connection and hasattr(connection, 'is_connected') and connection.is_connected():
                    connection.close()
                    logger.info("Connection returned to pool.")
                else:
                    logger.warning("Connection is None or not connected, cannot return to pool.")
            except AttributeError as e:
                logger.error(f"AttributeError returning connection to pool: {e}")
            except Error as e:
                logger.error(f"Error closing connection: {e}")
        else:
            logger.warning("Connection is None, nothing to close.")