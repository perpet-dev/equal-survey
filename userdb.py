from mysql.connector import Error
from dbconnection import DatabaseConnectionPool
import logging
from config import LOGGING_LEVEL
# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)  # Adjust the logging level accordingly

class UserInfo:
    def __init__(self):
        logger.info('Initializing UserInfo database connection pool')
        self.pool = DatabaseConnectionPool.get_instance()
        if not self.pool:
            logger.error("Failed to create or retrieve a connection pool.")

    def get_user_profile(self, user_id):
        connection = self.get_connection()
        if not connection:
            return None

        try:
            return self.fetch_user_profile(connection, user_id)
        finally:
            self.close_connection(connection)

    def get_connection(self):
        """Safely attempt to retrieve a connection from the pool."""
        try:
            return self.pool.get_connection()
        except Error as e:
            logger.error(f"Error getting connection from pool: {e}")
            return None

    def fetch_user_profile(self, connection, user_id):
        """Fetch user profile using the provided connection and user_id."""
        try:
            with connection.cursor() as cursor:
                sql = "SELECT `provider_id` FROM `user` WHERE `id` = %s;"
                cursor.execute(sql, (user_id,))
                result = cursor.fetchone()
                if result:
                    logger.info(f"User profile retrieved successfully for user_id {user_id}: {result}")
                    return {'provider_id': result[0]}
                else:
                    logger.warning(f"No profile found for user_id: {user_id}")
                    return {"error": "User profile not found"}
        except Error as e:
            logger.error(f"Failed to execute query: {e}")
            return {"error": str(e)}

    def close_connection(self, connection):
        """Safely close the connection."""
        try:
            if connection.is_connected():
                connection.close()
        except Error as e:
            logger.error(f"Error closing connection: {e}")

    def close(self):
        """Close all connections in the pool if this method is necessary."""
        try:
            self.pool.closeall()
            logger.info("Successfully closed all database connections.")
        except Exception as e:
            logger.error(f"Failed to close database connections: {e}")
