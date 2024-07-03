from typing import Optional
from fastapi import Query
from pymongo import MongoClient

import mysql.connector
from mysql.connector import Error

def getpetprofile(user_id=None, petname=None):
    connection = None  # Initialize the connection variable
    try:
        # Establish the connection
        connection = mysql.connector.connect(
            host='127.0.0.1',
            port='3307',
            database='perpet',
            user='perpetapi',
            password='O7dOQFXQ1PYY'
        )
        if connection is not None and connection.is_connected():
            cursor = connection.cursor()
            # Define the SQL query with placeholders
            sql = "SELECT * FROM `pet` WHERE `user_id` = %s AND `name` = %s AND `use_yn` = 'Y';"
            # Execute the query with parameters
            cursor.execute(sql, (user_id, petname))
            
            # Fetch the results
            results = cursor.fetchall()
            
            # Check if there are any results
            if not results:
                print("No results foundfor user_id: %s and petname: %s" % (user_id, petname))
                return False
            else:
                # print("results: ", results)
                return True
            
    except Error as e:
        print(f"Error: {e}")

    finally:
        if connection is not None and connection.is_connected():
            cursor.close()
            connection.close()
            #print("MariaDB connection is closed")

# from config import MONGODB, MONGODB_DBNAME

mongodb_connection_string = 'mongodb+srv://perpetcloud:NsIgvcQ5E7OQ2JSW@equalpet.tt45urw.mongodb.net/'
database_name = 'perpet_healthcheck' 
client = MongoClient(mongodb_connection_string)
mongo_db = client[database_name]

automaton_collection = mongo_db.automatons
session_collection = mongo_db.automaton_sessions

# def test():
#     query = {
# #         #"questionnaire_id": "Back_Questionnaire",
#         "insertDate": { "$gt": "2024-05-17T00:00:00.000000+0000" },
#     }
    
#     results = session_collection.find(query)
#     count = session_collection.count_documents(query)
#     print(f"count: {count}")
#     results_list = []
#     deleteddocs = 0
#     for doc in results:
#         petname = doc["variables"].get("@petname")
#         user_id = doc["user_id"]
#         questionnaire_id = doc["questionnaire_id"]
        
#         insertDate = doc["insertDate"]
#         # print(f"user_id: {user_id} petname: {petname} / {questionnaire_id}/ insertDate: {insertDate}")
#         hasResults = getpetprofile(user_id, petname)
#         if not hasResults:
#             deleteddocs += 1
#             print(f"delete this document: for user_id: {user_id} petname: {petname} / {questionnaire_id}/ insertDate: {insertDate} (deleteddocs: {deleteddocs})")
#             session_collection.delete_one({"_id": doc["_id"]})
    
# test()
def breakBackQuestionnaire():
    query = {
            "questionnaire_id": "Back_Questionnaire",
            "insertDate": { "$gt": "2024-05-17T00:00:00.000000+0000" },
            "goto": { "$ne": "62" }
        }
    results = session_collection.find(query)
    #     count = session_collection.count_documents(query)
    #     print(f"count: {count}")
    for doc in results:
        petname = doc["variables"].get("@petname")
        user_id = doc["user_id"]
        questionnaire_id = doc["questionnaire_id"]
        
        insertDate = doc["insertDate"]
        hasResults = getpetprofile(user_id, petname)
        if not hasResults:
            print(f"delete this document: for user_id: {user_id} petname: {petname} / {questionnaire_id}/ insertDate: {insertDate}")
            # session_collection.delete_one({"_id": doc["_id"]})
        print(f"user_id: {user_id} petname: {petname} / {questionnaire_id}/ insertDate: {insertDate}")
        
breakBackQuestionnaire()

def breakRegisterPet():
    query = {
            "questionnaire_id": "PerpetHealthCheckIntro",
            "insertDate": { "$gt": "2024-05-17T00:00:00.000000+0000" },
            "goto": { "$ne": "24" }
        }
    results = session_collection.find(query)
    #     count = session_collection.count_documents(query)
    #     print(f"count: {count}")
    for doc in results:
        petname = doc["variables"].get("@petname")
        user_id = doc["user_id"]
        questionnaire_id = doc["questionnaire_id"]
        
        insertDate = doc["insertDate"]
        hasResults = getpetprofile(user_id, petname)
        if not hasResults:
            print(f"user: {user_id} has not finished register petname: {petname} / {questionnaire_id}/ insertDate: {insertDate}")
            # session_collection.delete_one({"_id": doc["_id"]})
        else:
            print(f"user: {user_id} registered petname: {petname} / {questionnaire_id}/ insertDate: {insertDate}")
        print(f"user_id: {user_id} petname: {petname} / {questionnaire_id}/ insertDate: {insertDate}")
        
breakRegisterPet()

# def get_health_scan_deviation(user_id: Optional[int] = Query(None)):
#     # Prepare the query
#     query = {
#         #"questionnaire_id": "Back_Questionnaire",
#         "insertDate": { "$gt": "2024-05-17T00:00:00.000000+0000" },
#         # "$or": [
#         #     { "session_complete": { "$exists": False } },
#         #     { "session_complete": False }
#         # ]
#     }
    
#     # Add user_id to the query if provided
#     if user_id is not None:
#         query["user_id"] = user_id
    
#     # Perform the query
#     results = session_collection.find(query)

#     # Convert the results to a list of dictionaries with only the required fields
#     results_list = []
    
#     for doc in results:
#         petname = doc["variables"].get("@petname")
#         pet_id = pet_db.get_pet_profile(doc["user_id"], petname)
#         if pet_id is not None:
#             result = {
#                 "user_id": doc["user_id"],
#                 "petname": doc["variables"].get("@petname"),
#                 "pet_id": pet_id,
#                 "pet_type": doc["variables"].get("@pet_type"),
#                 "gender": doc["variables"].get("@gender"),
#                 "insertDate": doc["insertDate"]
#             }
#             results_list.append(result)
#         else:
#             # Delete the document if pet_id is None
#             session_collection.delete_one({"_id": doc["_id"]})
    
#     return results_list

