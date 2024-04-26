from mysql.connector import connect, Error
from mysql.connector.pooling import MySQLConnectionPool
from config import LOGGING_LEVEL, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_DATABASE
import logging

logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)

class UserInfo:
    def __init__(self, db_host=DB_HOST, db_port=DB_PORT, db_user=DB_USER, db_password=DB_PASSWORD, db_database=DB_DATABASE):
        print('Initializing UserDB')
        self.pool = self.create_pool(host=db_host, port=db_port, user=db_user, password=db_password, database=db_database)

    @staticmethod
    def create_pool(host, port, user, password, database):
        try:
            pool = MySQLConnectionPool(
                pool_name = "mypool",
                pool_size = 32,
                host=host,
                port=port,
                user=user,
                password=password,
                database=database
            )
            print('Database connection pool successfully established.')
            return pool
        except Error as e:
            logger.error(f"Error connecting to MariaDB Platform: {e}")
            return None

    def get_connection(self):
        try:
            return self.pool.get_connection()
        except Error as e:
            logger.error(f"Error getting connection from pool: {e}")
            return None

    def get_user_profile(self, user_id):
        connection = self.get_connection()
        if not connection:
            logger.error("Failed to obtain database connection.")
            return None

        try:
            cursor = connection.cursor()
            sql = "SELECT `provider_id` FROM `user` WHERE `id` = %s;"
            cursor.execute(sql, (user_id,))
            result = cursor.fetchone()
            if result:
                logger.debug(f"User profile retrieved successfully: {result}")
                return self.process_user_profile(result)
            else:
                logger.error(f"No profile found for user_id: {user_id}")
                return {"error": "User profile not found"}
        except Error as e:
            logger.error(f"Failed to execute query: {e}")
            return {"error": str(e)}
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def process_user_profile(user_data):
        # Placeholder for actual processing logic
        return {'provider_id': user_data[0]}

    def close(self):
        logger.info("Closing all database connections.")
        self.pool.closeall()

