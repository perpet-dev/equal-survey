from typing import Optional
from fastapi import Query
from pymongo import MongoClient

from config import MONGODB, MONGODB_DBNAME
mongodb_connection_string = MONGODB
database_name = MONGODB_DBNAME 
client = MongoClient(mongodb_connection_string)
mongo_db = client[database_name]

automaton_collection = mongo_db.automatons
session_collection = mongo_db.automaton_sessions




def get_health_scan_deviation(user_id: Optional[int] = Query(None)):
    # Prepare the query
    query = {
        "questionnaire_id": "Back_Questionnaire",
        "insertDate": { "$gt": "2024-05-17T00:00:00.000000+0000" },
        "$or": [
            { "session_complete": { "$exists": False } },
            { "session_complete": False }
        ]
    }
    
    # Add user_id to the query if provided
    if user_id is not None:
        query["user_id"] = user_id
    
    # Perform the query
    results = session_collection.find(query)

    # Convert the results to a list of dictionaries with only the required fields
    results_list = []
    
    for doc in results:
        petname = doc["variables"].get("@petname")
        pet_id = pet_db.get_pet_profile(doc["user_id"], petname)
        if pet_id is not None:
            result = {
                "user_id": doc["user_id"],
                "petname": doc["variables"].get("@petname"),
                "pet_id": pet_id,
                "pet_type": doc["variables"].get("@pet_type"),
                "gender": doc["variables"].get("@gender"),
                "insertDate": doc["insertDate"]
            }
            results_list.append(result)
        else:
            # Delete the document if pet_id is None
            session_collection.delete_one({"_id": doc["_id"]})
    
    return results_list

