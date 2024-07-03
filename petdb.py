from mysql.connector import Error
from dbconnection import DatabaseConnectionPool
import logging
from config import LOGGING_LEVEL

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)  # Adjust the logging level accordingly

class PetInfo:
    def __init__(self):
        logger.info('Initializing PetInfo database connection pool')
        self.pool = DatabaseConnectionPool.get_instance()
        if not self.pool:
            logger.error("Failed to create a connection pool.")

    def get_pet_profile(self, user_id, petname):
        connection = self.get_connection()
        if connection is None:
            logger.error("Failed to obtain database connection.")
            return None

        cursor = None
        try:
            cursor = connection.cursor()
            sql = "SELECT `id` FROM `pet` WHERE `user_id` = %s AND `name` = %s AND `use_yn` = 'Y';"
            logger.debug("Executing SQL query: %s with parameters: %s, %s", sql, user_id, petname)
            cursor.execute(sql, (user_id, petname))
            results = cursor.fetchall()  # Fetch all results instead of fetchone
            if results:
                logger.debug("Pet profile successfully retrieved: %s", results[0][0])
                return results[0][0]  # Return the first ID from the first result
            else:
                logger.debug("No pet with name %s found for user_id: %s", petname, user_id)
                return None
        except Error as e:
            logger.error("Failed to execute query: %s", e)
            self.reconnect()  # Attempt to reconnect
            return None
        finally:
            if cursor:
                cursor.close()
            if connection:
                self.close_connection(connection)
    
    def get_pet_profile_deleted(self, user_id, petname):
        connection = self.get_connection()
        if connection is None:
            logger.error("Failed to obtain database connection.")
            return None

        cursor = None
        try:
            cursor = connection.cursor()
            sql = "SELECT `id` FROM `pet` WHERE `user_id` = %s AND `name` = %s AND `use_yn` = 'N';"
            logger.debug("Executing SQL query: %s with parameters: %s, %s", sql, user_id, petname)
            cursor.execute(sql, (user_id, petname))
            results = cursor.fetchall()  # Fetch all results instead of fetchone
            if results:
                logger.debug("Deleted Pet profile successfully retrieved: %s", results[0][0])
                return results[0][0]  # Return the first ID from the first result
            else:
                logger.debug("No deleted pet with name %s found for user_id: %s", petname, user_id)
                return None
        except Error as e:
            logger.error("Failed to execute query: %s", e)
            self.reconnect()  # Attempt to reconnect
            return None
        finally:
            if cursor:
                cursor.close()
            if connection:
                self.close_connection(connection)

    def get_connection(self):
        try:
            return self.pool.get_connection()
        except Error as e:
            logger.error(f"Error getting connection from pool: {e}")
            return None

    def close_connection(self, connection):
        """Safely close the connection"""
        if connection:
            try:
                connection.close()
                logger.info("Connection successfully closed.")
            except Error as e:
                logger.error(f"Error closing connection: {e}")
        else:
            logger.warning("Attempted to close a null connection.")
            
    def reconnect(self):
        """Reconnect to the database if the connection is lost."""
        self.connection = self.get_connection()
        if self.connection:
            self.cursor = self.connection.cursor()
            logger.info("Reconnected and cursor created successfully.")
        else:
            self.cursor = None
            logger.error("Failed to re-establish database connection.")