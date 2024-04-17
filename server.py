# server.py
from math import log
from fastapi import FastAPI, Body, Form, Header, HTTPException, Depends, Response, Request, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Tuple, List, Dict
import os
from automaton import Automaton
#import firebase_admin
#from firebase_admin import credentials, firestore
import uvicorn
import requests
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import re
import uuid
from pymongo import MongoClient, UpdateOne, ASCENDING
from bson.objectid import ObjectId
import json
from config import LOGGING_CONFIG, MONGODB
import logging
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

class AnswerSubmission(BaseModel):
    question_id: str
    user_answer: str

class SingleAnswer(BaseModel):
    variable_name: str
    value: str
class AnswersSubmission(BaseModel):
    question_id: str
    answers: List[SingleAnswer]  # List of answers

client = MongoClient(MONGODB)
mongo_db = client.perpet_healthcheck
automaton_collection = mongo_db.automatons
session_collection = mongo_db.automaton_sessions

app = FastAPI()

# Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# static files directory for web app
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

breedid_map = {}
allergyid_map = {} 
diseaseid_map = {} 
# Set the URL for the POST request
# serverip = "http://localhost:10075"
serverip = "http://dev.promptinsight.ai:10002"

def registerUser(session_id: str):
    url = f"{serverip}/user-service/v1/auth/social"
    # Define the data payload for the POST request
    data = {
        "id": f"WEB_ANONYMOUS_{session_id}",
        "type": "KAKAO",
        "service_agree": "Y", 
        "privacy_agree": "Y"
    }

    # Make the POST request
    response = requests.post(url, json=data)

    # Check if the request was successful
    if response.status_code == 200:
        logger.debug("Success registering user:", response.json())  # Print the JSON response from the server
    else:
        logger.error(f"Failed to register user: Status Code:{response.status_code} Response Text:{response.text}")
    signup_json = response.json()
    
    return signup_json

async def get_automaton_for_user(session_id: str, questionnaire_id: str) -> Tuple[Automaton, str]:
    """
    Retrieves or creates an Automaton instance for a specific session and questionnaire.
    Creates a unique session for each questionnaire_id and session_id combination.
    """
    logger.debug(f"Retrieving Automaton for session_id: {session_id}, questionnaire_id: {questionnaire_id}")
    automaton = Automaton()

    # Find or create the automaton data
    automaton_data = automaton_collection.find_one({"name": questionnaire_id})
    if not automaton_data:
        logger.debug(f"No existing automaton for questionnaire_id: {questionnaire_id}, creating new.")
        automaton.load_from_excel(f"{questionnaire_id}.xlsx")
        automaton_data = automaton.serialized_states()
        automaton_collection.insert_one(automaton_data)
        automaton_id = automaton_data['_id']
    else:
        automaton_id = automaton_data['_id']
        automaton.deserialize_states(automaton_data)

    # Create a unique composite key for session and questionnaire
    session_key = f"{session_id}_{questionnaire_id}"
    
    # Find or create the session
    session_data = session_collection.find_one({"session_key": session_key})
    if not session_data:
        logger.debug(f"No session data for session_key: {session_key}, creating new session.")
        signup_json = registerUser(session_id)
        user_id = signup_json.get('data', {}).get('id', None)
        accessToken = signup_json.get('data', {}).get('accessToken', None)
        logger.debug(f"FastAPI: for session_id: {session_id} => User Signup JSON: {signup_json} \
                    \n=> signup_json_id: {user_id}") 
        new_session_data = {
            "session_key": session_key,
            "session_id": session_id,
            "questionnaire_id": questionnaire_id,
            "automaton_id": automaton_id,
            "user_id": user_id,
            "accessToken": accessToken
        }
        session_collection.insert_one(new_session_data)
    else:
        logger.debug(f"Found existing session data for session_key: {session_key}")
        automaton.deserialize_data(session_data)

    return automaton, session_id

@app.get("/questionnaire/{questionnaire_id}/{session_id}/restore")
async def restore_session(questionnaire_id: str, session_id: str):
    """
    Restores a session for a given automaton ID and session ID by retrieving or creating an Automaton instance.
    This endpoint ensures that each session related to a specific questionnaire is correctly handled.
    """
    # Retrieve or create the Automaton and the session using the unique session_key
    automaton, _ = await get_automaton_for_user(session_id, questionnaire_id)

    # Create a unique composite key for session and questionnaire
    session_key = f"{session_id}_{questionnaire_id}"

    # Retrieve the session data using the session_key
    session_data = session_collection.find_one({"session_key": session_key})

    if not session_data:
        logger.info(f"No session data found for session_key: {session_key}, initializing new session.")
        session_data = {
            "session_key": session_key,
            "session_id": session_id,
            "questionnaire_id": questionnaire_id,
            "automaton_id": automaton.name,
            "questions_history": {},
            "user_answers": {}
        }
        session_collection.insert_one(session_data)

    # Proceed with session restoration logic
    questions_history = session_data.get("questions_history", {})
    current_question_id = automaton.goto  # or some default value
    restored_session_data = {
        "session_id": session_id,
        "questionnaire_id": questionnaire_id,
        "current_question_id": current_question_id,
        "questions_history": questions_history,
        "variables": automaton.variables,  # Include other automaton states if needed
        "user_answers": session_data.get("user_answers", {})
    }

    logger.info(f"Restored session data: {restored_session_data}")
    return restored_session_data

@app.post("/get_question/{questionnaire_id}/{question_id}")
async def get_question(response: Response, request: Request, questionnaire_id: str, question_id: str, query_params: Optional[dict] = Body(default=None)):
    global session_collection  # Add this line to use the global session_collection
    session_id = request.headers.get('session_id', None) or request.cookies.get('session_id', None)

    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info(f"Generated new session_id: {session_id}")
        # Set the cookie for the session
        response.set_cookie(key="session_id", value=session_id)

    logger.info(f"Session ID: {session_id}, Questionnaire ID: {questionnaire_id}, Question ID: {question_id}")
    
    automaton, _ = await get_automaton_for_user(session_id, questionnaire_id)
    logger.info(f"Loaded automaton for Session ID: {session_id}, Questionnaire ID: {questionnaire_id}")

    #if question_id == "1" and query_params:
    if query_params:
        logger.debug(f"Query Parameters: {query_params}")
        actual_params = query_params.get('queryParams', {})
        for key, value in actual_params.items():
            formatted_key = f"@{key}"
            logger.debug(f"Setting variable: {formatted_key} => {value}")
            automaton.set_variable_value(formatted_key, value)
    
    # Check if the pet type is already known and skip the first question if it is.
    if question_id == "1" and query_params:
        pet_type = actual_params.get('pet_type', None)
        if pet_type:
            # Assuming you have a mapping of pet types to the next question ID
            next_question_id_map = {
                'cat': '2',  # If pet type is cat, go to question ID 2
                'dog': '2',  # If pet type is dog, go to question ID 2
                # Add other pet types and corresponding question IDs if needed
            }
            next_question_id = next_question_id_map.get(pet_type.lower(), '1')  # Default to question ID 1 if pet type is unknown

            # Serialize and save the automaton's current state before moving to the next question
            automaton_data = automaton.serialize_data()
            session_collection.update_one({"session_key": f"{session_id}_{questionnaire_id}"}, {"$set": automaton_data}, upsert=True)

            # If the next question ID is different from the current, fetch the next question data
            if next_question_id != question_id:
                return await get_question(response, request, questionnaire_id, next_question_id, query_params)
    ##############################


    node = automaton.states.get(question_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Question not found")

    question = automaton.substitute_placeholders(node['Question'])
    answer_choices = node.get("AnswerChoices", "")

    if "APICALL" in answer_choices:
        api_call = answer_choices.split("APICALL(")[1].split(")")[0]
        api_call = automaton.substitute_placeholders(api_call)
        response = make_api_call(api_call)
        # if "EXTRACT(" in answer_choices:
        #     extract_key = extract_from_function(answer_choices)
        #     answer_choices = extract_data(response, extract_key)
        # else:
        #     answer_choices = response
            
        if "EXTRACT(" in answer_choices:
            extract_key = extract_from_function(answer_choices)
            aggregated_data = []
            for single_response in response:
                extracted_data = extract_data(single_response, extract_key)
                logger.debug(f"Extracted data: {extracted_data}")
                aggregated_data.append(extracted_data)
            answer_choices = aggregated_data  
            logger.debug(f"EXTRACT answer_choices: {answer_choices}")
        else:
            # This assumes that if not extracting, you're handling raw responses
            answer_choices = [resp for resp in response]  # Just a placeholder, customize as needed
            logger.debug(f"NNEXTRACT answer_choices: {answer_choices}")

    if " - " in answer_choices:
        parsed_choices = parse_answer_choices(answer_choices, automaton)
    else:
        parsed_choices = answer_choices

    question_data = {
        "question_id": question_id,
        "question": question,
        "answer_type": node.get("AnswerType"),
        "answer_choices": parsed_choices,
        "page_number": node.get("Page"),
        "why_we_asked": node.get("WhyWeAsk"),
        "updated_questions": [],
        "redo_questions": [],
        "remove_questions": []
    }

    logger.debug(f"Next question: {question_data}")
    
    # Serialize and save the automaton's current state
    automaton_data = automaton.serialize_data()
    logger.debug(f"Automaton data: {automaton_data}")
    session_collection = mongo_db.automaton_sessions
    session_collection.update_one({"session_key": f"{session_id}_{questionnaire_id}"}, {"$set": automaton_data}, upsert=True)
    
    update_history_query = {"$set": {f"questions_history.{question_id}": question_data}}
    session_collection.update_one({"session_key": f"{session_id}_{questionnaire_id}"}, update_history_query, upsert=True)

    return question_data

# @app.post("/get_question/{questionaire_id}/{question_id}")
# async def get_question(response: Response, request: Request, questionaire_id: str, question_id: str, query_params: Optional[dict] = Body(default=None)):
#     session_id = request.headers.get('session_id', None) or request.cookies.get('session_id', None)

#     if not session_id:
#         session_id = str(uuid.uuid4())
#         logger.info(f"FastAPI generated new session_id: {session_id}")
#         # Set the cookie
#         response.set_cookie(key="session_id", value=session_id)

#     logger.info(f"FastAPI session_id: {session_id} => Question ID: {question_id}")
#     logger.info(f"Query Parameters: {query_params}")

#     automaton, session_id = await get_automaton_for_user(session_id, questionaire_id)
#     logger.info(f"Found automaton for session_id: {session_id}, questionaire_id: {questionaire_id}, automaton: {automaton.serialize_data()}")
    
#     if question_id == "1" and query_params:
#         for key, inner_dict in query_params.items():
#             if isinstance(inner_dict, dict):
#                 for inner_key, value in inner_dict.items():
#                     formatted_key = f"@{inner_key}"
#                     if len(formatted_key) > 1:
#                         automaton.set_variable_value(formatted_key, value)

#         # Serialize and save the state to 
#         # Firestore
#         # db.collection("automaton_sessions").document(session_id).set(automaton.serialize())
#         # MongoDB: Serialize and save or update the state
#         automaton_data = automaton.serialize_data()
#         automaton_sessions_collection = mongo_db.automaton_sessions
#         automaton_sessions_collection.update_one({"_id": session_id}, {"$set": automaton_data}, upsert=True)

#     node = automaton.states.get(question_id)
#     if node is None:
#         raise HTTPException(status_code=404, detail="Question not found")

#     question = automaton.substitute_placeholders(node['Question'])
#     answer_choices = node.get("AnswerChoices")
#     logger.debug(f"FastAPI: => Answer choices: {answer_choices}")
#     if "APICALL" in answer_choices:
#         logger.debug("Should make API CALL")
#         api_call = answer_choices.split("APICALL(")[1].split(")")[0]
#         api_call = automaton.substitute_placeholders(api_call)
#         logger.debug(f"API CALL: {api_call}")
#         if "EXTRACT" in answer_choices:
#             logger.debug(f"get_question - answer_choices: {answer_choices}")
#             extract_key = extract_from_function(answer_choices)
#             response = make_api_call(api_call)
#             logger.debug(f"get_question - Should Extract data: {extract_key}")
#             answer_choices = extract_data(response, extract_key)
#         else:
#             response = make_api_call(api_call)
#             answer_choices = response
            
#     if " - " in answer_choices:
#         #case of images answer choices
#         parsed_choices = parse_answer_choices(answer_choices, automaton)
#         logger.debug(f"FastAPI: => Parsed choices: {parsed_choices}")
#     else:
#         parsed_choices = answer_choices
        
#     question_data = { 
#         "question_id": question_id,
#         "question": question,
#         "answer_type": node.get("AnswerType"),
#         "answer_choices": parsed_choices,
#         "page_number": node.get("Page"),
#         "why_we_asked": node.get("WhyWeAsk"),
#         #"design": node.get("Design"),
#         "updated_questions": [],
#         "redo_questions": [],
#         "remove_questions": []
#     }
    
#     logger.debug(f"FastAPI:/get_question/{questionaire_id}/{question_id} => Next question: {question_data}")
#     # MongoDB: Serialize and save or update the state
#     automaton.update_questions_path(question_id)
#     automaton_data = automaton.serialize_data()
#     automaton_sessions_collection = mongo_db.automaton_sessions
#     automaton_sessions_collection.update_one({"_id": session_id}, {"$set": automaton_data}, upsert=True)
#     # Add the current question data to `questions_history`
#     update_history_query = {"$set": {f"questions_history.{question_id}": question_data}}
#     automaton_sessions_collection.update_one({"_id": session_id}, update_history_query, upsert=True)
#     return question_data

# @app.post("/submit_answer/{questionnaireId}")
# async def submit_answer(request: Request, questionnaireId: str, submission: AnswerSubmission, response: Response):
#     session_id = request.headers.get('session_id', None)  or request.cookies.get('session_id', None)
#     if not session_id:
#         # Generate a new session_id if not present
#         session_id = str(uuid.uuid4())
#         # Set the cookie
#         response.set_cookie(key="session_id", value=session_id)

#     automaton, session_id = await get_automaton_for_user(session_id, questionnaireId)
    
#     question_id = submission.question_id
#     answer = submission.user_answer
#     logger.debug(f"FastAPI session_id: {session_id} => Question ID: {question_id}, Answer: {answer}")
#     next_step, updated_affected_questions, redo_questions, remove_questions = automaton.process(question_id, answer)
    
#     logger.debug(f"FastAPI: => current question:{question_id} => next_step: {next_step} => affected_questions: {updated_affected_questions}")
    
#     # First, update the user's answer for the current question in the questions_history
#     automaton_sessions_collection = mongo_db.automaton_sessions
#     update_fields = {
#         f"questions_history.{question_id}.update_questions": updated_affected_questions,
#         f"questions_history.{question_id}.redo_questions": redo_questions,
#         f"questions_history.{question_id}.remove_questions": remove_questions,
#         f"questions_history.{question_id}.user_answer": answer
#     }
#     update_history_query = {"$set": update_fields}
#     automaton_sessions_collection.update_one({"_id": session_id}, update_history_query, upsert=True)
    
#     if next_step is None:
#         logger.info("FastAPI: No further action required")
#         return {"message": "No further action required"}
    
#     node = automaton.states.get(str(next_step))
#     if node is None:
#         raise HTTPException(status_code=404, detail="Question not found")

#     question = automaton.substitute_placeholders(node['Question'])
#     answer_choices = node.get("AnswerChoices")
#     logger.debug(f"FastAPI: => Answer choices: {answer_choices}")

#     'Start Next Phase'
    
#     if "APICALL" in answer_choices:
#         logger.debug("Should make API CALL")
#         api_call = answer_choices.split("APICALL(")[1].split(")")[0]
#         api_call = automaton.substitute_placeholders(api_call)
#         logger.debug(f"API CALL: {api_call}")
#         if "EXTRACT" in answer_choices:
#             extract_key = extract_from_function(answer_choices)
#             response = make_api_call(api_call)
#             #logger.info(f"API Call response: {response}")
#             logger.debug(f"submit_answer - Should Extract data: {extract_key}")
#             answer_choices = extract_data(response, extract_key)
#             logger.info(f"answer_choices: {answer_choices}")
#         else:
#             response = make_api_call(api_call)
#             answer_choices = response

#     if " - " in answer_choices:
#         #case of images answer choices
#         parsed_choices = parse_answer_choices(answer_choices, automaton)
#         logger.debug(f"FastAPI: => Parsed choices: {parsed_choices}")
#     else:
#         parsed_choices = answer_choices
    
#     question_data = {
#         "question_id": node.get("ID"),
#         "question": question,
#         "answer_type": node.get("AnswerType"),
#         "answer_choices": parsed_choices,
#         "why_we_asked": node.get("WhyWeAsk"),
#         #"design": node.get("Design"),
#         #"page_number": node.get("Page"),
#         "updated_questions": updated_affected_questions, 
#         "redo_questions": redo_questions,
#         "remove_questions": remove_questions
#     }
#     next_question_id = node.get("ID")
#     # MongoDB: Serialize and save or update the state
#     automaton_sessions_collection = mongo_db.automaton_sessions
#     automaton.update_questions_path(next_question_id)
#     automaton_data = automaton.serialize_data()
#     automaton_sessions_collection.update_one({"_id": session_id}, {"$set": automaton_data}, upsert=True)
#     bulk_operations = []

#     # Handle updates to affected questions
#     for q_id, new_question_text in updated_affected_questions.items():
#         update_field = {
#             f"questions_history.{q_id}.question": new_question_text
#         }
#         bulk_operations.append(UpdateOne({'_id': session_id}, {'$set': update_field}))

#     # Execute bulk operations
#     if bulk_operations:
#         result = automaton_sessions_collection.bulk_write(bulk_operations)
#         print(f"Bulk operation results: {result.bulk_api_result}")
    
#     update_history_query = {"$set": {f"questions_history.{next_question_id}": question_data}}
#     automaton_sessions_collection.update_one({"_id": session_id}, update_history_query, upsert=True)
    
#     logger.debug(f"FastAPI:submit_answer => next_step: {next_step}, Next question: {question_data}")
    
#     return question_data

@app.post("/submit_answer/{questionnaireId}")
async def submit_answer(request: Request, questionnaireId: str, submission: AnswerSubmission, response: Response):
    session_id = request.headers.get('session_id', None) or request.cookies.get('session_id', None)
    if not session_id:
        session_id = str(uuid.uuid4())
        response.set_cookie(key="session_id", value=session_id)
        logger.info(f"Generated new session_id: {session_id}")

    automaton, _ = await get_automaton_for_user(session_id, questionnaireId)
    question_id = submission.question_id
    user_answer = submission.user_answer

    logger.debug(f"Session ID: {session_id}, Question ID: {question_id}, User Answer: {user_answer}")
    
    # Process the answer and determine next steps in the questionnaire
    next_step, affected_questions, redo_questions, remove_questions = automaton.process(question_id, user_answer)
    session_key = f"{session_id}_{questionnaireId}"
    
    # Update session data with the current answers
    update_fields = {
        f"questions_history.{question_id}.user_answer": user_answer,
        f"questions_history.{question_id}.update_questions": affected_questions,
        f"questions_history.{question_id}.redo_questions": redo_questions,
        f"questions_history.{question_id}.remove_questions": remove_questions
    }
    automaton_sessions_collection = mongo_db.automaton_sessions
    automaton_sessions_collection.update_one({"session_key": session_key}, {"$set": update_fields}, upsert=True)
    
    if next_step is None:
        return {"message": "No further action required"}

    # Load the next question node
    node = automaton.states.get(str(next_step))
    if node is None:
        raise HTTPException(status_code=404, detail="Next question not found")
    
    question = automaton.substitute_placeholders(node['Question'])
    answer_choices = node.get("AnswerChoices")

    if "APICALL" in answer_choices:
        logger.debug("Should make API CALL")
        api_call = answer_choices.split("APICALL(")[1].split(")")[0]
        api_call = automaton.substitute_placeholders(api_call)
        logger.debug(f"API CALL: {api_call}")
        if "EXTRACT" in answer_choices:
            extract_key = extract_from_function(answer_choices)
            response = make_api_call(api_call)
            #logger.info(f"API Call response: {response}")
            logger.debug(f"submit_answers - Should Extract data: {extract_key}")
            # for single_response in response:
            #     answer_choices = extract_data(single_response, extract_key)
            #     logger.info(f"answer_choices: {answer_choices}")
            answer_choices = extract_data(response, extract_key)
            logger.info(f"answer_choices: {answer_choices}")
        else:
            response = make_api_call(api_call)
            answer_choices = response

    if " - " in answer_choices:
        #case of images answer choices
        parsed_choices = parse_answer_choices(answer_choices, automaton)
        logger.debug(f"FastAPI: => Parsed choices: {parsed_choices}")
    else:
        parsed_choices = answer_choices

    question_data = {
        "question_id": next_step,
        "question": question,
        "answer_type": node.get("AnswerType"),
        "answer_choices": parsed_choices,
        "why_we_asked": node.get("WhyWeAsk"),
        "updated_questions": affected_questions, 
        "redo_questions": redo_questions,
        "remove_questions": remove_questions
    }
    
    # Serialize and update the automaton's state
    automaton.update_questions_path(next_step)
    automaton_data = automaton.serialize_data()
    automaton_sessions_collection.update_one({"session_key": session_key}, {"$set": automaton_data}, upsert=True)
    
    # Handle updates to affected questions
    bulk_operations = [UpdateOne({"session_key": session_key}, {'$set': {f"questions_history.{q_id}.question": text}}) for q_id, text in affected_questions.items()]
    if bulk_operations:
        automaton_sessions_collection.bulk_write(bulk_operations)

    # Update the history for the next question
    automaton_sessions_collection.update_one({"session_key": session_key}, {"$set": {f"questions_history.{next_step}": question_data}}, upsert=True)
    
    logger.debug(f"Next question details: {question_data}")
    return question_data

# #Endpoint to process in case of multiple answers for multiple variables
# @app.post("/submit_answers/{questionnaireId}")
# async def submit_answers(request: Request, questionnaireId: str, submission: AnswersSubmission, response: Response):
#     session_id = request.headers.get('session_id', None)  or request.cookies.get('session_id', None)
#     if not session_id:
#         # Generate a new session_id if not present
#         session_id = str(uuid.uuid4())
#         # Set the cookie
#         response.set_cookie(key="session_id", value=session_id)

#     automaton, session_id = await get_automaton_for_user(session_id, questionnaireId)
#     question_id = submission.question_id
#     answers = submission.answers
#     for answer in answers:
#         logger.debug(f"FastAPI session_id: {session_id} => Question ID: {question_id}, Variable:{answer.variable_name} Value: {answer.value}")
#         automaton.set_variable_value(answer.variable_name, answer.value)

#     # Process the user's answer
#     next_step, affected_questions, redo_questions, remove_questions = automaton.process(question_id, answer)

#     # Serialize and save the state to Firestore
#     # db.collection("automaton_sessions").document(session_id).set(automaton.serialize())
#     # MongoDB: Serialize and save or update the state
#     automaton_data = automaton.serialize_data()
#     #logger.debug(f"FastAPI: => {automaton_data}")
#     automaton_sessions_collection = mongo_db.automaton_sessions
#     automaton_sessions_collection.update_one({"_id": session_id}, {"$set": automaton_data}, upsert=True)
#     #questions_history
    
#     if next_step is None:
#         logger.debug("FastAPI: No further action required")
#         return {"message": "No further action required"}

#     node = automaton.states.get(str(next_step))

#     if node is None:
#         raise HTTPException(status_code=404, detail="Question not found")

#     question = automaton.substitute_placeholders(node['Question'])
#     answer_choices = node.get("AnswerChoices")
#     logger.debug(f"FastAPI: => Answer choices: {answer_choices}")

#     if "APICALL" in answer_choices:
#         logger.debug("Should make API CALL")
#         api_call = answer_choices.split("APICALL(")[1].split(")")[0]
#         api_call = automaton.substitute_placeholders(api_call)
#         logger.debug(f"API CALL: {api_call}")
#         if "EXTRACT" in answer_choices:
#             extract_key = extract_from_function(answer_choices)
#             response = make_api_call(api_call)
#             #logger.info(f"API Call response: {response}")
#             logger.debug(f"submit_answers - Should Extract data: {extract_key}")
#             answer_choices = extract_data(response, extract_key)
#             logger.info(f"answer_choices: {answer_choices}")
#         else:
#             response = make_api_call(api_call)
#             answer_choices = response

#     if " - " in answer_choices:
#         #case of images answer choices
#         parsed_choices = parse_answer_choices(answer_choices, automaton)
#         logger.debug(f"FastAPI: => Parsed choices: {parsed_choices}")
#     else:
#         parsed_choices = answer_choices

#     question_data = {
#         "question_id": node.get("ID"),
#         "question": question,
#         "answer_type": node.get("AnswerType"),
#         "answer_choices": parsed_choices,
#         "page_number": node.get("Page"),
#         "why_we_asked": node.get("WhyWeAsk"),
#         "design": node.get("Design"),
#         #"redo_questions": affected_questions
#         "updated_questions": affected_questions, 
#         "redo_questions": redo_questions,
#         "remove_questions": remove_questions
#     }

#     logger.debug(f"FastAPI:submit_answer => next_step: {next_step}, Next question: {question_data}")
#     return question_data
@app.get("/questionnaire/{questionnaire_id}/{session_id}/pet_register")
async def register_pet(questionnaire_id: str, session_id: str):
    # Retrieve or create the Automaton and the session using the unique session_key
    automaton, _ = await get_automaton_for_user(session_id, questionnaire_id)
    # Create a unique composite key for session and questionnaire
    session_key = f"{session_id}_{questionnaire_id}"

    # Retrieve the session data using the session_key
    session_data = session_collection.find_one({"session_key": session_key})
    # Retrieve user_id from session data
    user_id = session_data.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=404, detail="User ID not found in session")
    accessToken = session_data.get("accessToken")
    if accessToken is None:
        raise HTTPException(status_code=404, detail="Access Token not found in session")
    
    # Prepare the data to be sent
    pet_data = {
        "user_id": user_id,
        "type": automaton.get_variable_value("@type"),
        "name": automaton.get_variable_value("@name"),
        "breeds_id": convert_to_number(automaton.get_variable_value("@breeds_id")),
        "age": format_date(automaton.get_variable_value("@age")),
        "gender": automaton.get_variable_value("@gender"),
        "profile": {
            "neutralization_code": convert_to_number(automaton.get_variable_value("@neutralization_code")),
            "main_act_place_code": convert_to_number(automaton.get_variable_value("@main_act_place_code")),
            "relationship_code": convert_to_number(automaton.get_variable_value("@relationship_code")),
            "weight": convert_to_number(automaton.get_variable_value("@weight")),
            "body_form_code": convert_to_number(automaton.get_variable_value("@body_form_code")),
            "disease_id": automaton.get_variable_value("@disease_id"),  # Assuming it's a comma-separated string of numbers
            "disease_treat_code": convert_to_number(automaton.get_variable_value("@disease_treat_code")),
            "conditions_code": convert_to_number(automaton.get_variable_value("@conditions_code")),
            "appetite_change_code": convert_to_number(automaton.get_variable_value("@appetite_change_code")),
            "feed_amount_code": convert_to_number(automaton.get_variable_value("@feed_amount_code")),
            "snack": automaton.get_variable_value("@snack"),  # Assuming it's a string "Y" or "N"
            "drinking_amount_code": convert_to_number(automaton.get_variable_value("@drinking_amount_code")),
            "allergy_id": automaton.get_variable_value("@allergy_id"),  # Assuming it's a comma-separated string of numbers
            "how_to_know_allergy_code": convert_to_number(automaton.get_variable_value("@how_to_know_allergy_code")),
            "walk_code": convert_to_number(automaton.get_variable_value("@walk_code"))
        }
    }

    # Log the data for debugging purposes
    logger.debug(f"FastAPI: Sending pet registration data: {pet_data}")
    # Set up headers for authorization
    headers = {
        'Authorization': f'Bearer {accessToken}'
    }
    # Send the data to the external service
    try:
        response = requests.post(f'{serverip}/user-service/v1/pet', json=pet_data, headers=headers)
        response.raise_for_status()  # This will raise an HTTPError for bad responses
        return response.json()  # Return the JSON response content
    except requests.RequestException as e:
        logger.error(f"Failed to register pet: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to register pet") from e     
    

@app.get("/questionnaire/{session_id}/get_metadatatext")
async def get_metadatext(session_id: str):
    
    metadatatexts_map = {
        "main_act_place_code": {
            "metadatatext": "living_space",
            "values": {
                0: "indoor_apartment",
                1: "indoor_with_yard",
                2: "indoor_without_yard",
                3: "outdoor"
            }
        },
        "relationship_code": {
            "metadatatext": "multi_animal_environment",
            "values": {
                0: "no",
                1: "two_animal",
                2: "more_than_three_animal"
            }
        },
        "walk_code": {
            "metadatatext": "daily_walk",
            "values": {
                0: "once_a_day",
                1: "twice_a_day",
                2: "more_than_three_times_a_day",
                3: "not_every_day"
            }
        },
        "how_to_know_allergy_code": {
            "metadatatext": "allergy_detect",
            "values": {
                0: "diagnosed",
                1: "suspected",
            }
        },
        "drinking_amount_code": {
            "metadatatext": "water_intake",
            "values": {
                0: "low",
                1: "normal",
                2: "high",
                3: "excessive"
            }
        },
        "snack": {
            "metadatatext": "treat",
            "values": {
                'Y': "yes",
                'N': "no"
            }
        },
        "feed_amount_code": {
            "metadatatext": "pet_food",
            "values": {
                0: "less_than_recommended",
                1: "less_for_weight_loss",
                2: "approximate_amount",
                3: "self_regulated",
            }
        },
        "appetite_change_code": {
            "metadatatext": "appetite",
            "values": {
                0: "decreased",
                1: "unchanged",
                2: "increased"
            }
        },
        "conditions_code": {
            "metadatatext": "energetic",
            "values": {
                0: "stable",
                1: "slightly_decreased",
                2: "significantly_decreased"
            }
        },
        "disease_treat_code": {
            "metadatatext": "disease_treatment",
            "values": {
                0: "ongoing",
                1: "diagnosed_only"
            }
        },
        "body_form_code": {
            "metadatatext": "body_shape",
            "values": {
                0: "underweight_severe",
                1: "underweight_slight",
                2: "normal",
                3: "overweight_slight",
                4: "obese_severe"
            }
        },
        "neutralization_code": {
            "metadatatext": "neutering_surgery",
            "values": {
                0: "performed",
                1: "planned",
                2: "not_planned"
            }
        },
        "foldEar": {
            "metadatatext": "ear_folded",
            "values": {
                0: "yes",
                1: "no"
            }
        },
        "weight": {
            "metadatatext": "body_weight",
            "direct_value": True
        },
        "name": {
            "metadatatext": "pet_name",
            "direct_value": True
        },
        "age": {
            "metadatatext": "pet_age",
            "direct_value": True
        },
        "gender": {
            "metadatatext": "gender",
            "values": {
                'M': "male",
                'F': "female"
            }
        },
        "type": {
            "metadatatext": "pet_type",
            "direct_value": True
        },
    }
    

    questionnaire_id = "PerpetHealthCheckIntro"
    automaton, _ = await get_automaton_for_user(session_id, questionnaire_id)
    variables_front = automaton.variables
    session_key = f"{session_id}_{questionnaire_id}"
    response_id_front = f"{session_id}_{questionnaire_id}"
    
    questionnaire_id = "Back_Questionnaire"
    automaton, _ = await get_automaton_for_user(session_id, questionnaire_id)
    variables_back = automaton.variables
    response_id_back = f"{session_id}_{questionnaire_id}"
    # Retrieve the session data using the session_key
    session_data = session_collection.find_one({"session_key": session_key})
    # Retrieve user_id from session data
    user_id = session_data.get("user_id")
    
    logger.debug(f"FastAPI: => User ID: {user_id}\n \
                => Variables Back: {variables_back}\n \
                => Variables Front: {variables_front} \n \
                ")
    
    metadata_text = [] 

    required_keys = {'disease_id', 'allergy_id'}  # Keys that need default values if absent or empty

    # First check and add default values if necessary
    for key in required_keys:
        if f'@{key}' not in variables_front or not variables_front[f'@{key}'].strip():
            default_value = "no"
            metadata_text.append(f"{key[:-3]}:{default_value}")  # Append default value, like 'disease:no'
            logger.debug(f"{key}: {default_value}")
    for key, value in variables_front.items():
        if key.startswith('@'):
            logger.debug(f"variable => {key}: {value}")
            metadata_key = key[1:]  # Remove '@' to match keys in the map
            
            if metadata_key == 'breeds_id':
                logger.debug(f"breeds_id: {value}")
                metadata = getBreedMetaText(convert_to_number(value))
                logger.debug(f"metadata: {metadata}")
                metadata_text.append(metadata)
            elif metadata_key == 'disease_id':
                if value.strip():  # Check if value is not empty
                    for disease_id in value.split(","):
                        logger.debug(f"disease_id: {disease_id}")
                        metadata = getDiseaseMetaText(disease_id)
                        metadata_text.append(metadata)
                        logger.debug(f"metadata: {metadata}")
                else:
                    metadata_text.append("disease:no")
                    logger.debug("disease:no")
            elif metadata_key == 'allergy_id':
                if value.strip():  # Check if value is not empty
                    for allergy_id in value.split(","):
                        logger.debug(f"allergy_id: {allergy_id}")
                        metadata = getAllergyMetaText(allergy_id)
                        metadata_text.append(metadata)
                        logger.debug(f"metadata: {metadata}")
                else:
                    metadata_text.append("allergy:no")
                    logger.debug("allergy:no")
            elif metadata_key == 'age' and value.strip():
                print(f"age: {value}")
                try:
                    # Extract YYYY-MM from YYYY-MM-DD and ensure the date is valid
                    year, month, _ = map(int, value.split('-'))
                    birth_date = datetime(year=year, month=month, day=1)
                    today = datetime.now()
                    age_in_months = (today.year - birth_date.year) * 12 + (today.month - birth_date.month)
                    
                    # Determine age category
                    if 0 <= age_in_months < 12:
                        age_category = "growth"#"0-12"
                    elif 12 <= age_in_months < 48:
                        age_category = "young_adult"#"12-48"
                    elif 48 <= age_in_months < 120:
                        age_category = "adult"#"48-120"
                    elif 120 <= age_in_months < 156:
                        age_category = "old_adult"#"120-156"
                    elif age_in_months >= 156:
                        age_category = "geriatric"#"156+"
                    else:
                        age_category = "Undefined"  # In case of future dates or incorrect values
                    #print(f"age_category: {age_category}")
                    # Append formatted data to metadata text
                    formatted_age = f"{birth_date.year}-{birth_date.month:02}"
                    #metadata_text.append(f"age:{formatted_age}")
                    metadata_text.append(f"age:{age_category}")
                    
                except ValueError as e:
                    # Log and raise an error if the date is incorrect
                    print(f"Error processing the date: {e}")
                    raise HTTPException(status_code=400, detail=f"Invalid date format for age: {value}")
                
            elif metadata_key in metadatatexts_map:
                metadata_info = metadatatexts_map[metadata_key]
                if metadata_info.get("direct_value"):
                    metadata_description = f"{metadata_info['metadatatext']}:{value}"
                    metadata_text.append(metadata_description)
                    logger.debug(f"metadata: {metadata_description}")
                elif 'values' in metadata_info and value in metadata_info['values']:
                    metadata_description = metadata_info['values'][value]
                    full_metadata = f"{metadata_info['metadatatext']}:{metadata_description}"
                    metadata_text.append(full_metadata)
                    logger.debug(f"metadata_text: {full_metadata}")
                else:
                    try:
                        int_value = int(value)
                        if int_value in metadata_info['values']:
                            metadata_description = metadata_info['values'][int_value]
                            full_metadata = f"{metadata_info['metadatatext']}:{metadata_description}"
                            metadata_text.append(full_metadata)
                            logger.debug(f"metadata_text: {full_metadata}")
                    except ValueError:
                        logger.error(f"Invalid value `{value}` for metadata key `{metadata_key}`")

    logger.debug(f"Final for Front metadata_text: {metadata_text}")
    source = "front"
    front_metadata_texts = {
            "survey_id": "PerpetHealthCheckIntro",
            "response_id": response_id_front,
            "source": source,
            "metadata_texts": metadata_text
    }
    metadata_text = []
    # Set of variables to ignore
    ignored_variables = {'type', 'user_id', 'pet_id', 'petname', 'gender', 'target', 'queryParams'}
    for key, value in variables_back.items():
        if key.startswith('@'):
            #logger.debug(f"back variable => {key}: {value}")
            metadata_key = key[1:]  # Remove '@' to match keys in the map
            logger.debug(f"variable => {metadata_key}: {value}")
            if metadata_key not in ignored_variables:
                # Process and log if the variable is not in the ignored set
                full_metadata = f"{metadata_key}:{value}"
                metadata_text.append(full_metadata)
                logger.debug(f"Processed variable => {metadata_key}: {value}")
            else:
                # Log that the variable is ignored
                logger.debug(f"Ignored variable => {metadata_key}: {value}")
    
    logger.debug(f"Final with Back metadata_text: {metadata_text}")
    
    source = "back"
    back_metadata_texts = {
            "survey_id": "Back_Questionnaire",
            "response_id": response_id_back,
            "source": source,
            "metadata_texts": metadata_text
    }
    response_data = [front_metadata_texts, back_metadata_texts]
    
    logger.debug(response_data)
    return response_data
    
def convert_to_number(value):
    if value == "" or value is None:
        return None
    try:
        return float(value)
    except ValueError:
        try:
            return int(value)
        except ValueError:
            return value

def format_date(date_str):
    if date_str:
        try:
            # Parse the date string to a datetime object
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            # Format the datetime object to 'YYYY-MM'
            formatted_date = date_obj.strftime("%Y-%m")
            return formatted_date
        except ValueError:
            return None  # Return None if the date format is incorrect
    return None  # Return None if the input is None or empty

# def make_api_call(url: str):
#     try:
#         response = requests.get(url)
#         response.raise_for_status()
#         return response.json()
#     except requests.RequestException as e:
#         raise HTTPException(status_code=400, detail=str(e)) from e
    

# def make_api_call(url: str) -> List[dict]:
#     try:
#         # Checking if the URL contains a list of IDs (indicated by square brackets)
#         base_url, query_param = url.split("?")
#         param_name, param_value = query_param.split("=")
        
#         # Normalize and parse the ID values
#         if param_value.startswith('[') and param_value.endswith(']'):
#             # It's a list of IDs, remove brackets and split by comma
#             ids = param_value[1:-1].split(',')
#         else:
#             # Single ID, make it a list for uniform handling
#             ids = [param_value]
        
#         combined_results = []
        
#         # Make individual API calls for each ID
#         for id_value in ids:
#             id_clean = id_value.strip(" '")  # Remove spaces and quotes
#             modified_url = f"{base_url}?{param_name}={id_clean}"
#             response = requests.get(modified_url)
#             response.raise_for_status()
#             combined_results.append(response.json())  # Each ID's result is added to the list
        
#         return combined_results  # Return the combined list of all results
#     except requests.RequestException as e:
#         raise HTTPException(status_code=400, detail=str(e)) from e

def make_api_call(url: str) -> List[dict]:
    try:
        # Parse the URL to get base components and query parameters
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        combined_results = []
        # Loop through all query parameters to identify lists
        for key, values in query_params.items():
            if isinstance(values, list) and len(values) == 1:
                # Check if the value looks like a list within a string
                if values[0].startswith('[') and values[0].endswith(']'):
                    # It's a list, process each ID
                    ids = [x.strip(" '") for x in values[0].strip("[]'\" ").split(',')]
                    # Remove the original list parameter to avoid duplicates in the URL
                    del query_params[key]

                    for id_clean in ids:
                        # Update the query parameters with the current ID
                        new_query_params = query_params.copy()
                        new_query_params[key] = id_clean
                        # Build a new query string
                        new_query_string = urlencode(new_query_params, doseq=True)
                        # Create a new URL with the updated query string
                        new_url = urlunparse(
                            (parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, new_query_string, parsed_url.fragment)
                        )
                        response = requests.get(new_url)
                        response.raise_for_status()
                        combined_results.append(response.json())

                    break  # Exit after handling the first list parameter

        if not combined_results:  # If no list parameters were found or processed
            # Execute a normal API call with the original URL
            response = requests.get(url)
            response.raise_for_status()
            combined_results.append(response.json())
        logger.debug(f"FastAPI: API Call response of url {url}\n: {combined_results} ")
        return combined_results
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    

# def extract_data(json_data, path):
#     logger.debug(f"FastAPI: Extract data from JSON: {json_data} => Path: {path}\n\n")
#     """
#     Extracts data from json_data based on the provided path and returns a list of values or
#     dictionaries with specified fields in the path.

#     :param json_data: The JSON data from which to extract information.
#     :param path: The path to the data to extract, in the format 'key1.key2[*].field' or 'key1.key2[*].(field1,field2)'.
#     :return: A list of values or dictionaries with specified fields.
#     """
#     elements = path.split('.')
#     current_data = json_data

#     for elem in elements[:-1]:  # Process all elements except the last
#         if elem.endswith('[*]'):
#             key = elem[:-3]
#             if key in current_data and isinstance(current_data[key], list):
#                 current_data = current_data[key]
#             else:
#                 return []  # Key not found or not a list
#         elif elem in current_data:
#             current_data = current_data[elem]
#         else:
#             return []  # Key not found

#     last_element = elements[-1]
#     if '(' in last_element and last_element.endswith(')'):
#         return extracted_from_extract_data(last_element, current_data)
#     # For a single field, return a list of values
#     choices =  [item.get(last_element) for item in current_data if isinstance(item, dict)]
#     logger.debug(f"FastAPI: Extracted choices - simple key: {choices}")
#     return '\n'.join(choices)

def extract_data(json_data, path):
    logger.debug(f"FastAPI: Extract data from JSON: {json_data} => Path: {path}")
    """
    Extracts data from json_data based on the provided path and returns a concatenated string
    of values or dictionaries with specified fields in the path.

    :param json_data: The JSON data from which to extract information.
    :param path: The path to the data to extract, in the format 'key1.key2[*].field' or 'key1.key2[*].(field1,field2)'.
    :return: A concatenated string of values or formatted strings based on the path.
    """
    final_results = []
    for data in json_data:  # Assuming json_data is a list of JSON responses
        current_data = data  # Start with the whole JSON response
        elements = path.split('.')
        for elem in elements[:-1]:  # Navigate down to the last key
            if elem.endswith('[*]'):
                key = elem[:-3]
                if key in current_data and isinstance(current_data[key], list):
                    current_data = current_data[key]
                else:
                    current_data = []
                    break  # Exit if the key is not found or is not a list
            elif elem in current_data:
                current_data = current_data[elem]
            else:
                current_data = []
                break  # Exit if the key is not found

        # Extract the final element, possibly multiple fields
        last_element = elements[-1]
        if last_element.startswith('(') and last_element.endswith(')'):
            fields = last_element.strip('()').split(',')
            for item in current_data:
                extracted = {field.strip(): item.get(field.strip()) for field in fields if isinstance(item, dict)}
                final_results.append(extracted)
        else:
            for item in current_data:
                if isinstance(item, dict) and last_element in item:
                    final_results.append(item[last_element])

    # Convert list of results to a formatted string if needed
    if all(isinstance(i, dict) for i in final_results):
        results_str = '\n'.join([f"{item.get('id')}:{item.get('name')}" for item in final_results if 'id' in item and 'name' in item])
    else:
        results_str = '\n'.join(map(str, final_results))
    logger.debug(f"FastAPI: Extracted choices - {results_str}")
    return results_str



def extracted_from_extract_data(last_element, current_data):
    fields = last_element.replace(' ', '').strip('()').split(',')
    choices = [{field: item.get(field) for field in fields} for item in current_data if isinstance(item, dict)]
    logger.debug(f"FastAPI: Extracted choices - multiple keys : {choices}")
    answer_choices = format_dict_array_to_string(choices)
    logger.debug(f"FastAPI: Extracted choices - answer_choices : {answer_choices}")
    return answer_choices

def format_dict_array_to_string(dict_array):
    """
    Formats an array of dictionaries into a string where each line contains
    the key-value pairs of one dictionary, separated by a colon and space.
    """
    formatted_lines = []

    for dictionary in dict_array:
        formatted_line = ': '.join(f"{value}" for key, value in dictionary.items())
        formatted_lines.append(formatted_line)

    return '\n'.join(formatted_lines)


def parse_answer_choices(answer_choices: str, automaton: Automaton) -> str:
    """
    Parses the answer choices string into a structured list of dictionaries.
    Handles both conditional and non-conditional image choices.

    :param answer_choices: The string containing the choices and conditions.
    :param automaton: The automaton instance that can provide variable values.
    :return: A list of dictionaries with parsed data.
    """
    options = answer_choices.split('\n')

    # Define a pattern to extract the description and details
    pattern = re.compile(
        r"(?P<description>[^\-]+) - "  # Capture everything up to the first dash as the description
        r"(?P<details>[^IF]+)"  # Capture everything up to "IF" as details
    )

    formatted_options = []
    for option in options:
        if match := pattern.match(option.strip()):
            groups = match.groupdict()
            description = groups['description'].strip()
            details = groups['details'].strip().rstrip(" -")

            # Extract conditional or unconditional image part
            image_key = extract_image_key(option, automaton)

            formatted_option = f"{description} - {details} - <img src={image_key}>"
            formatted_options.append(formatted_option)

    return '\n'.join(formatted_options)

def extract_image_key(option_str: str, automaton: Automaton) -> str:
    """
    Extracts the image key from the option string based on conditional logic.

    :param option_str: The individual option string.
    :param automaton: The automaton instance.
    :return: The image key or None.
    """
    conditional_pattern = re.compile(r"IF\(@(?P<var_name>\w+)==(?P<value>\w+)\) THEN IMG\((?P<true_img>[^\)]+)\) ELSE IMG\((?P<false_img>[^\)]+)\)")
    unconditional_pattern = re.compile(r"IMG\((?P<img>[^\)]+)\)")

    if conditional_match := conditional_pattern.search(option_str):
        var_name, value, true_img, false_img = conditional_match.groups()
        actual_value = automaton.get_variable_value(f"@{var_name}")
        return true_img if actual_value == value else false_img
    else:
        unconditional_match = unconditional_pattern.search(option_str)
        return unconditional_match['img'] if unconditional_match else None

def extract_from_function(input_string):
    start = input_string.find("EXTRACT(")
    if start == -1:
        return None  # 'EXTRACT(' not found

    # Adjust start to get content after 'EXTRACT('
    start += len("EXTRACT(")

    # Find the closing parenthesis for the EXTRACT function
    parenthesis_count = 1
    end = start
    while end < len(input_string) and parenthesis_count > 0:
        if input_string[end] == '(':
            parenthesis_count += 1
        elif input_string[end] == ')':
            parenthesis_count -= 1
        end += 1

    return None if parenthesis_count != 0 else input_string[start:end - 1]


def getBreedMetaText(breed_id):
    logger.debug(f"breed_id_map: {breedid_map}")
    return breedid_map.get(breed_id)

def getDiseaseMetaText(disease_id):
    return diseaseid_map.get(disease_id)

def getAllergyMetaText(allergy_id):
    return allergyid_map.get(allergy_id)

@app.get("/questionnaire/{questionnaire_id}", response_class=HTMLResponse)
async def get_questionnaire(request: Request, questionnaire_id: str):
    session_id = request.cookies.get('session_id')
    # If no user ID cookie, generate a new one and set it
    if not session_id:
        logger.debug("No session_id cookie found")
        session_id = str(uuid.uuid4())
        response = templates.TemplateResponse("questionnaire.html", {"request": request, "questionnaire_id": questionnaire_id, "session_id": session_id,
                                                "query_params": request.query_params})
        response.set_cookie(key='session_id', value=session_id, max_age=30*24*60*60)  # Expires in 30 days

        return response
    return templates.TemplateResponse("questionnaire.html", {"request": request, "questionnaire_id": questionnaire_id, "session_id": session_id,
                                                "query_params": request.query_params})

#This is the Flask equivalent part in FastAPI
@app.get("/healthreport", response_class=HTMLResponse)
async def healthreport(request: Request):
    return templates.TemplateResponse("radar.html", {"request": request, "query_params": request.query_params})

@app.get("/")
async def home(request: Request, response: Response):
    return templates.TemplateResponse("intro.html", {"request": request})

breedid_map, allergyid_map, diseaseid_map = {}, {}, {}
def getBreedMetaText(breed_id: str) -> str:
    logger.debug(f"breedid_map: {breedid_map}")
    return breedid_map.get(breed_id, "No metadata found for this breed ID")

def getDiseaseMetaText(disease_id: str) -> str:
    logger.debug(f"breedid_map: {breedid_map}")
    return diseaseid_map.get(disease_id, "No metadata found for this disease ID")

def getAllergyMetaText(allergy_id: str) -> str:
    logger.debug(f"breedid_map: {breedid_map}")
    return allergyid_map.get(allergy_id, "No metadata found for this disease ID")

@app.on_event("startup")
async def startup_event():
    global breedid_map, allergyid_map, diseaseid_map
    # Load the JSON data from a file
    with open('breed_Metadata.json', 'r', encoding='utf-8') as file:
        data = json.load(file)

    # Create a map from breed_id to metadata_text
    breedid_map = {
        item['breed_id']: item['metadata_text'] 
        for item in data
        if '_breed' in item['metadata_text']
    }
    logger.debug(f"breedid_map:{breedid_map}")

    with open('allergy_Metadata.json', 'r', encoding='utf-8') as file:
        data = json.load(file)

    # Create a map from breed_id to metadata_text
    allergyid_map = {
        item['allergy_id']: item['metadata_text'] 
        for item in data
        if item['metadata_text'].startswith('allergy')
    }
    logger.debug(f"allergyid_map:{allergyid_map}")

    with open('disease_Metadata.json', 'r', encoding='utf-8') as file:
        data = json.load(file)

    # Create a map from disease_id to metadata_text, filtering for metadata_text that starts with "disease"
    diseaseid_map = {
        item['disease_id']: item['metadata_text']
        for item in data
        if item['metadata_text'].startswith('disease')
    }
    logger.debug(f"diseaseid_map:{diseaseid_map}")
    # logger.debug(f"breedid_map:{breedid_map}")
    # logger.debug(f"diseaseid_map:{diseaseid_map}")
    # logger.debug(f"allergyid_map:{allergyid_map}")
    session_collection.create_index([("session_id", ASCENDING), ("questionnaire_id", ASCENDING)], unique=True)
    print("Database initialized and indexes created.")

LOGLEVEL = logging.DEBUG
# Set the logging level for Uvicorn loggers
logging.getLogger("uvicorn").setLevel(LOGLEVEL)
logging.getLogger("uvicorn.error").setLevel(LOGLEVEL)
logging.getLogger("uvicorn.access").setLevel(LOGLEVEL)
# Attempt to set the level for "uvicorn.asgi" only if it exists
if logging.getLogger("uvicorn.asgi"):
    logging.getLogger("uvicorn.asgi").setLevel(LOGLEVEL)

# Set the root logger level if you want to adjust the overall logging level
logging.getLogger().setLevel(LOGLEVEL)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000, log_level="debug")
