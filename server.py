# server.py
from math import log
from fastapi import FastAPI, Path, Body, Form, Header, HTTPException, Depends, Response, Request, File, UploadFile, status, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from numpy import size
from pydantic import BaseModel
from typing import Any, Optional, Tuple, List, Dict

import pymongo

from automaton import Automaton
import base64
from io import BytesIO
#import firebase_admin
#from firebase_admin import credentials, firestore
import uvicorn
import requests
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import re
import uuid
from pymongo import MongoClient, UpdateOne, ASCENDING
import json
from config import LOGGING_LEVEL, LOGGING_CONFIG, MONGODB, MONGODB_DBNAME, EUREKA
from py_eureka_client import eureka_client
import logging
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)
from config import APISERVER, PREFIXURL
from userdb import UserInfo
from petdb import PetInfo

import aiohttp
import asyncio
# Assuming UserInfo class is already imported
user_db = UserInfo()  # Global instance for reusing the connection pool
pet_db = PetInfo()  # Global instance for reusing the connection pool

class AnswerSubmission(BaseModel):
    question_id: str
    user_answer: str

class SingleAnswer(BaseModel):
    variable_name: str
    value: str
class AnswersSubmission(BaseModel):
    question_id: str
    answers: List[SingleAnswer]  # List of answers

# client = MongoClient(MONGODB)
# mongo_db = client.perpet_surveys #surveys db
# Connect to MongoDB
# Get the MongoDB connection string and database name from the config file
mongodb_connection_string = MONGODB
database_name = MONGODB_DBNAME 
client = MongoClient(mongodb_connection_string)
mongo_db = client[database_name]

automaton_collection = mongo_db.automatons
session_collection = mongo_db.automaton_sessions
images_collection = mongo_db.pet_images

#app = FastAPI()
app = FastAPI(root_path=PREFIXURL)
# origins = [
#     "http://localhost:3000",
#     "http://dev.promptinsight.ai:10095",
#     "http://dev.promptinsight.ai:10071",
#     "http://survey.equal.pet:10095",
#     "https://survey.equal.pet",
#     "http://backsurvey.equal.pet:10071",
# ]
# # Allow all origins
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,#["*"],  # Allows all origins
#     allow_credentials=True,
#     allow_methods=["*"],  # Allows all methods
#     allow_headers=["*"],  # Allows all headers
# )

# static files directory for web app
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

breedid_map = {}
allergyid_map = {} 
diseaseid_map = {} 

@app.get("/doc2s", include_in_schema=False)
async def custom_swagger_ui():
    return HTMLResponse("""
    <html>
        <head>
            <title>Custom Swagger UI</title>
            <link rel="stylesheet" type="text/css" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.17.3/swagger-ui.css">
        </head>
        <body>
            <div id="swagger-ui"></div>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.17.3/swagger-ui-bundle.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.17.3/swagger-ui-standalone-preset.js"></script>
            <script>
            const ui = SwaggerUIBundle({
                url: '/openapi.json',  // Ensure this points to the correct path to your OpenAPI spec
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout",
                deepLinking: true
            });
            </script>
        </body>
    </html>
    """)

@app.post("/initialize_session/{questionnaire_id}")
async def initialize_session(
    request: Request,
    questionnaire_id: str,
    user_id: str = Header(None, alias='X-User-ID'),
    access_token: str = Header(None, alias='X-Access-Token'),
    query_params: Optional[Dict[str, Any]] = Body(default={}, embed=True) 
):
    # Extract pet_type and petname from the query_params if available
    pet_type = query_params.get('pet_type')
    petname = query_params.get('petname')
    if not user_id:
        user_id = query_params.get('user_id')
    session_id = query_params.get('session_id')
    gender = query_params.get('gender')
    logger.debug(f"User ID: {user_id}, session_id: {session_id}, Questionnaire ID: {questionnaire_id}, petname: {petname}, pet_type: {pet_type}, gender:{gender}")

    if not user_id:
        # Generate new session for anonymous users
        # session_id = str(uuid.uuid4())
        # user_data = await registerUser(session_id)  # Assuming register_user is an async function
        # if user_data.get('id') and user_data.get('accessToken'):
        #     user_id = user_data['id']
        #     access_token = user_data['accessToken']
        #     logger.debug(f"Registered anonymous user: {user_id} with access token: {access_token}")
        # else:
        raise HTTPException(status_code=500, detail="Anonymous user not allowed")

    # For logged-in users or newly registered anonymous users
    if user_id and not session_id: 
        profile = pet_db.get_pet_profile_deleted(user_id, petname)
        session_data = session_collection.find_one({"session_key": str(user_id) + "_" + petname+ "_" + questionnaire_id})
        if session_data is not None and profile is not None:
            logger.info(f"User: {user_id} has deleted profile in registered petname: {petname}")
            session_collection.delete_one({"session_key": str(user_id) + "_" + petname + "_" + questionnaire_id})
            
        session_id = await retrieve_or_create_session_for_user(user_id, str(user_id) + "_" + petname, questionnaire_id, query_params)

    return JSONResponse(status_code=200, content={
        "session_id": session_id,
        "user_id": user_id,
        "access_token": access_token,
        "questionnaire_id": questionnaire_id,
        "petname": petname,
        "pet_type": pet_type
    })

async def retrieve_or_create_session_for_user(user_id: str, pet_info: str, questionnaire_id: str, query_params: Dict[str, Any]):
    # This function should handle the retrieval or creation of sessions and automatons asynchronously
    session_key = f"{pet_info}_{questionnaire_id}"
    logger.debug(f"Retrieving or creating session for session_key: {session_key}")
    
    session_data = session_collection.find_one({"session_key": session_key})

    # Get the current time with timezone set to UTC
    now_utc = datetime.now(timezone.utc)

    # Format the datetime object to the desired string format
    formatted_datetime = now_utc.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
    variables = {}
    user_answers = {}
    goto = '1'
    if not session_data:
        logger.debug("No session data found, creating new session and automaton.")
        #session_id = str(uuid.uuid4())
        if questionnaire_id == "Back_Questionnaire":
            session_data = session_collection.find_one({"session_key": f"{pet_info}_PerpetHealthCheckIntro"})
            session_id = session_data['session_id']
        else:
            session_id = str(uuid.uuid4())
            
        automaton = Automaton()
        automaton_data = await create_or_update_automaton(automaton, questionnaire_id)
        petname = query_params.get('petname')
        if petname:
            variables['@petname'] = petname
            automaton.set_variable_value("@petname", petname)
        gender = query_params.get('gender')
        if gender:
            variables['@gender'] = gender
            automaton.set_variable_value("@gender", gender)
        pet_type = query_params.get('pet_type')
        if pet_type:
            automaton.set_variable_value("@pet_type", pet_type)
            variables['@pet_type'] = pet_type
            if questionnaire_id == "PerpetHealthCheckIntro":
                user_answers['1'] = pet_type
                goto = '2'
        
        logger.info(f"Creating new session data for session_key: {session_key}, session_id: {session_id}, questionnaire_id: {questionnaire_id}")
        # session_collection.update_one({
        #     "session_key": session_key,
        #     "session_id": session_id,
        #     "questionnaire_id": questionnaire_id,
        #     "insertDate": formatted_datetime,
        #     "automaton_id": automaton_data['_id'],
        #     "user_id": int(user_id),
        #     "goto": goto,
        #     "user_answers": user_answers,
        #     "variables": variables,
        #     "questions_history": {}
        # })
        try:
            session_collection.update_one(
                {"session_id": session_id, "questionnaire_id": questionnaire_id},
                {
                    "$set": {
                        "session_key": session_key,
                        "insertDate": formatted_datetime,
                        "automaton_id": automaton_data['_id'],
                        "user_id": int(user_id),
                        "goto": goto,
                        "user_answers": user_answers,
                        "variables": variables,
                        "questions_history": {}
                    }
                },
                upsert=True  # This will insert the document if it does not exist
            )
        except pymongo.errors.PyMongoError as e:
            logger.error(f"An error occurred: {e}")
            raise
    else:
        automaton = Automaton()
        logger.debug(f"Found existing session data, loading automaton.{session_data}")
        automaton.deserialize_data(session_data)
        session_id = session_data['session_id']

    return session_id

async def create_or_update_automaton(automaton, questionnaire_id):
    # Load or create new automaton configurations asynchronously
    automaton_data = automaton_collection.find_one({"name": questionnaire_id})
    if not automaton_data:
        automaton.load_from_excel(f"{questionnaire_id}.xlsx")
        automaton_data = automaton.serialized_states()
        automaton_collection.insert_one(automaton_data)
    else:
        automaton.deserialize_states(automaton_data)
    return automaton_data

async def registerUser(session_id: str):
    url = f"{APISERVER}/user-service/v1/auth/social"
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
    user_data = response.json()
    return user_data['data']  # Return the nested 'data' dictionary

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
    # logger.debug(f"Automaton data: {automaton_data}")
    # Create a unique composite key for session and questionnaire
    #Find or create the session
    session_data = session_collection.find_one({
        "session_id": session_id,
        "questionnaire_id": questionnaire_id
    })
    if session_data:
        automaton.deserialize_data(session_data)
        
    logger.debug(f"get_automaton_for_user for session_id: {session_id}")
    return automaton, session_id

@app.get("/questionnaire/{questionnaire_id}/{session_id}/restore")
async def restore_session(questionnaire_id: str, session_id: str):
    """
    Restores a session for a given automaton ID and session ID by retrieving or creating an Automaton instance.
    """
    # Retrieve or create the Automaton and the session using the unique session_key
    automaton, _ = await get_automaton_for_user(session_id, questionnaire_id)
    
    logger.debug(f"restore_session; automaton found => automaton_data = {automaton.serialize_data()}")

    # Retrieve the session data using the session_key
    session_data = session_collection.find_one({
        "session_id": session_id,
        "questionnaire_id": questionnaire_id
    })

    
    if not session_data:
        logger.info(f"No session data found... initializing new session.")
        session_data = {
            "session_key": session_id + "_" + questionnaire_id,
            "session_id": session_id,
            "questionnaire_id": questionnaire_id,
            "automaton_id": automaton.name,
            "questions_history": {},
            "user_answers": {}
        }
        session_collection.insert_one(session_data)
    session_key = session_data['session_key']
    logger.debug(f"Restore => Session data for session_key: {session_key},  session_id:{session_id}")
    
    # Proceed with session restoration logic
    questions_history = session_data.get("questions_history", {})
    current_question_id = str(automaton.goto)  # or some default value
    if questions_history is None:
        questions_history = {}
    if current_question_id not in questions_history:
        node = automaton.states.get(current_question_id)
        logger.debug(f"Current question node: {node}")
        
        question = automaton.substitute_placeholders(node['Question'])
        question_data = {
                "session_id": session_id,
                "question_id": current_question_id,
                "question": question,
                "answer_type": node.get("AnswerType"),
                "answer_choices": node.get("AnswerChoices", ""),
                "page_number": node.get("Page"),
                "why_we_asked": node.get("WhyWeAsk"),
                "updated_questions": [],
                "redo_questions": [],
                "remove_questions": []
            }
        questions_history = {current_question_id: question_data}
        logger.debug(f"Questions history: {questions_history}")
        update_history_query = {"$set": {f"questions_history.{current_question_id}": question_data}}
        
        logger.debug(f"Updating questions history: {update_history_query} for session_key: {session_key}")
        if session_key:
            session_collection.update_one({"session_key": f"{session_key}"}, update_history_query, upsert=True)
    
    restored_session_data = {
        "session_id": session_id,
        "questionnaire_id": questionnaire_id,
        "current_question_id": current_question_id,
        "questions_history": questions_history,
        "variables": automaton.variables,  # Include other automaton states if needed
        "user_answers": session_data.get("user_answers", {})
    }
    
    logger.debug(f"Restored session data: done => {restored_session_data}")
    return restored_session_data

@app.post("/get_question/{questionnaire_id}/{question_id}")
async def get_question(
    response: Response, request: Request, 
    questionnaire_id: str,
    question_id: str,
    session_id: str = Header(None),  # Header parameter
    query_params: Optional[Dict[str, Any]] = Body(default={})
):
    print("Received session_id:", session_id)
    print("Received query_params:", query_params)
    global session_collection  # Add this line to use the global session_collection

    if not session_id:
        raise HTTPException(status_code=500, detail="A session_id is required to proceed.")

    logger.info(f"Session ID: {session_id}, Questionnaire ID: {questionnaire_id}, Question ID: {question_id}")
    
    automaton, _ = await get_automaton_for_user(session_id, questionnaire_id)
    logger.info(f"Loaded automaton for Session ID: {session_id}, Questionnaire ID: {questionnaire_id}")

    if query_params:
        logger.debug(f"Query Parameters: {query_params}")
        #actual_params = query_params.get('queryParams', {})
        for key, value in query_params.items():
            formatted_key = f"@{key}"
            logger.debug(f"Setting variable: {formatted_key} => {value}")
            automaton.set_variable_value(formatted_key, value)
    
    # Check if the pet type is already known and skip the first question if it is.
    if question_id == "1" and query_params and questionnaire_id == "PerpetHealthCheckIntro":
        #actual_params = query_params.get('query_params', {})
        pet_type = query_params.get('pet_type', None)
        logger.debug(f"Pet type: {pet_type}")
        if pet_type:
            # Assuming you have a mapping of pet types to the next question ID
            next_question_id_map = {
                'cat': '2',  # If pet type is cat, go to question ID 2
                'dog': '2',  # If pet type is dog, go to question ID 2
            }
            next_question_id = next_question_id_map.get(pet_type.lower(), '1')  # Default to question ID 1 if pet type is unknown
            
            logger.info(f"Skipping question ID 1 for pet type: {pet_type}, moving to question ID: {next_question_id}")
            automaton.goto = str(next_question_id)
            # Serialize and save the automaton's current state before moving to the next question
            automaton_data = automaton.serialize_data()
            session_collection.update_one({"session_key": f"{session_id}_{questionnaire_id}"}, {"$set": automaton_data}, upsert=True)

            # If the next question ID is different from the current, fetch the next question data
            if next_question_id != question_id:
                return await get_question(response, questionnaire_id, next_question_id, query_params)
    ##############################

    node = automaton.states.get(str(question_id))
    if node is None:
        raise HTTPException(status_code=404, detail="Question not found")
    logger.debug(f"Node: {node}")
    logger.debug(f"Question of node: {node['Question']}")
    question = automaton.substitute_placeholders(node['Question'])
    answer_choices = node.get("AnswerChoices", "")

    if "APICALL" in answer_choices:
        api_call = answer_choices.split("APICALL(")[1].split(")")[0]
        api_call = automaton.substitute_placeholders(api_call)
        logger.debug(f"Should make API CALL for: {api_call}")
        if "EXTRACT" in answer_choices:
            extract_key = extract_from_function(answer_choices)
            responses = make_api_call(api_call) # return  a list of choices for each sub-ids
            
            logger.debug(f"get_question - Should Extract data: {extract_key}")
            answer_choices = extract_data(responses, extract_key)
            logger.debug(f"answer_choices: {answer_choices}")
        #     main_list = []
        #     medical_terms = {
        #             9: "간담도계",
        #             377: "내분비계",
        #             13: "뇌신경",
        #             3: "당뇨",
        #             2: "비뇨생식기계",
        #             10: "소화기계",
        #             8: "신장",
        #             11: "심혈관계",
        #             5: "악성종양",
        #             17: "안과",
        #             16: "인지장애",
        #             14: "정형외과",
        #             6: "치과",
        #             1: "피부",
        #             15: "행동학적 질환",
        #             7: "호흡기계"
        #         }
        #     sub_list = []
        #     for resp in responses:
        #         logger.debug(f"Should extract for single: {resp}")
        #         list_subs = extract_data(resp, extract_key)
        #         logger.debug(f"list_subs: {list_subs}")
        #         sub_list.append(list_subs)
        #     logger.debug(f"sub_lists: {sub_list}")
            
        #     # If no list is found, search for a single id
        #     match = re.search(r"main_ctgr_id=(\d+)", api_call)
        #     if match:
        #         main_list = [medical_terms[int(match.group(1))]]
            
        #     "api_call => disease?main_ctgr_id=['8', '17', '1']"
        #     #match = re.search(r"(\['\d+', '\d+', '\d+'\])", api_call)
        #     match = re.search(r"\[\s*((?:'\d+'\s*,\s*)*'(?:\d+)')?\s*\]", api_call)

        #     if match:
        #         # Extract the matched group, which is the list as a string
        #         list_string = match.group(1)
        #         print(list_string)
        #         import ast
        #         list_of_strings = ast.literal_eval(list_string)
        #         # Convert each string in the list to an integer
        #         list_of_integers = [int(item) for item in list_of_strings]
        #         logger.debug(f"List of integers: {list_of_integers}")
                
        #         for item in list_of_integers:
        #             if item in medical_terms:
        #                 logger.debug(f"Medical term: {medical_terms[item]}")
        #                 main_list.append(medical_terms[item])
        #     if size(main_list) == 0:
        #         main_list = [""]
        #     # else:
        #     logger.debug(f"Main list: {main_list}")
            
        #     answer_choices = ""
            
        #     if size(main_list) == 1:
        #         answer_choices = f"질병분야_{main_list[0]}|{sub_list[0]}"
        #     else: 
        #         for sub, main in zip(sub_list, main_list):
        #             # Concatenate the new pair at the end of the answer_choices string
        #             answer_choices += f"질병분야_{main}|{sub}\n"

        #     # Remove the trailing newline character from the last line
        #     answer_choices = answer_choices.strip()

                
        #     logger.info(f"get_question/{questionnaire_id}/{question_id} APICALL/EXTRACT list_subs answer_choices: {answer_choices}")
        #     #list of answer_choices with corresponding sub-ids
            
    # else:
    #     response = make_api_call(api_call)
    #     answer_choices = response

    if "IMG(" in answer_choices:
        #case of images answer choices
        logger.info(f"answer_choices: {answer_choices}")
        parsed_choices = parse_answer_choices(answer_choices, automaton)
        logger.debug(f"Images: {parsed_choices}")
    elif "IF(" in answer_choices:   
        #case of conditional answer choices
        logger.info(f"Conditional answer_choices: {answer_choices}")
        parsed_choices = extract_content_based_on_condition(answer_choices, automaton)
        logger.debug(f"Conditional: {parsed_choices}")
    else:
        parsed_choices = answer_choices

    question_data = {
        "session_id": session_id,
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
    #logger.debug(f"Automaton data: {automaton_data}")
    session_collection = mongo_db.automaton_sessions
    
    session_data = session_collection.find_one({
        "session_id": session_id,
        "questionnaire_id": questionnaire_id
    })
    session_key = session_data['session_key']
    
    session_collection.update_one({"session_key": f"{session_key}"}, {"$set": automaton_data}, upsert=True)
    
    update_history_query = {"$set": {f"questions_history.{question_id}": question_data}}
    session_collection.update_one({"session_key": f"{session_key}"}, update_history_query, upsert=True)

    return question_data

@app.post("/submit_answer/{questionnaireId}")
async def submit_answer(
    questionnaireId: str,
    submission: AnswerSubmission,
    session_id: str = Header(None, alias='Session-Id'),  # Correctly aliased as it appears in the fetch headers
    user_id: str = Header(None, alias='X-User-ID'),  # Header parameter for user ID
    access_token: str = Header(None, alias='X-Access-Token')  # Header parameter for access token
):
    # Here you can use user_id and access_token as needed
    logger.debug(f"Received user_id: {user_id}, access_token: {access_token}, session_id: {session_id}")
    
    
    automaton, _ = await get_automaton_for_user(session_id, questionnaireId)
    
    question_id = submission.question_id
    user_answer = submission.user_answer

    logger.debug(f"Session ID: {session_id}, Question ID: {question_id}, User Answer: {user_answer}")
    
    # Process the answer and determine next steps in the questionnaire
    next_step, affected_questions, redo_questions, remove_questions = automaton.process(question_id, user_answer)
    
    # Retrieve the session data using the session_key
    session_data = session_collection.find_one({
        "session_id": session_id,
        "questionnaire_id": questionnaireId
    })
    session_key = session_data['session_key']
    logger.debug(f"Restore => Session data: {session_data} for session_key: {session_key}")
    
    # Update session data with the current answers
    update_fields = {
        f"questions_history.{question_id}.user_answer": user_answer,
        f"questions_history.{question_id}.update_questions": affected_questions,
        f"questions_history.{question_id}.redo_questions": redo_questions,
        f"questions_history.{question_id}.remove_questions": remove_questions
    }
    #automaton_sessions_collection = mongo_db.automaton_sessions
    #automaton_sessions_collection.update_one({"session_key": session_key}, {"$set": update_fields}, upsert=True)
    
    # Prepare the unset operation for the questions to be removed
    unset_fields = {f"questions_history.{q_id}": "" for q_id in remove_questions}

    # Get the collection
    automaton_sessions_collection = mongo_db.automaton_sessions

    # Perform the update and unset in a single operation
    automaton_sessions_collection.update_one(
        {"session_key": session_key},
        {
            "$set": update_fields,
            "$unset": unset_fields
        },
        upsert=True
    )
    if next_step is None:
        return {"message": "No further action required"}

    # Load the next question node
    node = automaton.states.get(str(next_step))
    if node is None:
        raise HTTPException(status_code=404, detail="Next question not found")
    
    question = automaton.substitute_placeholders(node['Question'])
    answer_choices = node.get("AnswerChoices")
    logger.debug(f"FastAPI: => Answer choices: {answer_choices}")
    
    if "APICALL" in answer_choices:
        
        api_call = answer_choices.split("APICALL(")[1].split(")")[0]
        api_call = automaton.substitute_placeholders(api_call)
        logger.debug(f"Should make API CALL for: {api_call}")
        if "EXTRACT" in answer_choices:
            extract_key = extract_from_function(answer_choices)
            responses = make_api_call(api_call) # return  a list of choices for each sub-ids
            
            #logger.debug(f"API Call response: {responses}")
            logger.debug(f"submit_answers - Should Extract data: {extract_key}")
            answer_choices = extract_data(responses, extract_key)
            logger.debug(f"submit_answers - Extracted data: {answer_choices}")
            # main_list = []
            # medical_terms = {
            #         9: "간담도계",
            #         377: "내분비계",
            #         13: "뇌신경",
            #         3: "당뇨",
            #         2: "비뇨생식기계",
            #         10: "소화기계",
            #         8: "신장",
            #         11: "심혈관계",
            #         5: "악성종양",
            #         17: "안과",
            #         16: "인지장애",
            #         14: "정형외과",
            #         6: "치과",
            #         1: "피부",
            #         15: "행동학적 질환",
            #         7: "호흡기계"
            #     }
            # sub_list = []
            # for resp in responses:
            #     logger.debug(f"Should extract for single: {resp}")
            #     list_subs = extract_data(resp, extract_key)
            #     logger.debug(f"list_subs: {list_subs}")
            #     sub_list.append(list_subs)
            # logger.debug(f"sub_lists: {sub_list}")
            
            # # If no list is found, search for a single id
            # match = re.search(r"main_ctgr_id=(\d+)", api_call)
            # if match:
            #     main_list = [medical_terms[int(match.group(1))]]
    
            # "api_call => disease?main_ctgr_id=['8', '17', '1']"
            # #match = re.search(r"(\['\d+', '\d+', '\d+'\])", api_call)
            # match = re.search(r"\[\s*((?:'\d+'\s*,\s*)*'(?:\d+)')?\s*\]", api_call)
            
            # if match:
            #     # Extract the matched group, which is the list as a string
            #     list_string = match.group(1)
            #     print(list_string)
            #     import ast
            #     list_of_strings = ast.literal_eval(list_string)
            #     # Convert each string in the list to an integer
            #     list_of_integers = [int(item) for item in list_of_strings]
            #     logger.debug(f"List of integers: {list_of_integers}")
 
            #     for item in list_of_integers:
            #         if item in medical_terms:
            #             logger.info(f"Medical term: {medical_terms[item]}")
            #             main_list.append(medical_terms[item])
            # if size(main_list) == 0:
            #     main_list = [""]
            # # else:
            # logger.info(f"Main list: {main_list}")
            
            # answer_choices = ""
            
            # if size(main_list) == 1:
            #     answer_choices = f"질병분야_{main_list[0]}|{sub_list[0]}"
            # else: 
            #     for sub, main in zip(sub_list, main_list):
            #         # Concatenate the new pair at the end of the answer_choices string
            #         answer_choices += f"질병분야_{main}|{sub}\n"

            # # Remove the trailing newline character from the last line
            # answer_choices = answer_choices.strip()
                
            # logger.debug(f"submit_answer APICALL/EXTRACT for API CALL: {api_call} => \nlist_subs answer_choices: {answer_choices}")
            # #list of answer_choices with corresponding sub-ids
            
        else:
            response = make_api_call(api_call)
            answer_choices = response


    if "IMG(" in answer_choices:
        #case of images answer choices
        logger.debug(f"answer_choices: {answer_choices}")
        parsed_choices = parse_answer_choices(answer_choices, automaton)
        logger.debug(f"Images: {parsed_choices}")
    elif "IF(" in answer_choices:   
        #case of conditional answer choices
        logger.debug(f"Conditional answer_choices: {answer_choices}")
        parsed_choices = extract_content_based_on_condition(answer_choices, automaton)
        logger.debug(f"Conditional: {parsed_choices}")
    else:
        parsed_choices = answer_choices
    
    logger.debug(f"FastAPI: => Parsed choices: {parsed_choices}")
    
    question_data = {
        "session_id": session_id,
        "question_id": next_step,
        "question": question,
        "answer_type": node.get("AnswerType"),
        "answer_choices": parsed_choices,
        "page_number": node.get("Page"),
        "why_we_asked": node.get("WhyWeAsk"),
        "updated_questions": affected_questions, 
        "redo_questions": redo_questions,
        "remove_questions": remove_questions
    }
    logger.debug(f"Next question details: {question_data}")
    
    # Serialize and update the automaton's state
    automaton.update_questions_path(next_step)
    automaton_data = automaton.serialize_data()
    logger.debug(f"session_key: {session_key}\nautomaton_data: {automaton_data}")
    automaton_sessions_collection.update_one({"session_key": session_key}, {"$set": automaton_data}, upsert=True)
    
    # Handle updates to affected questions
    #bulk_operations = [UpdateOne({"session_key": session_key}, {'$set': {f"questions_history.{q_id}.question": text}}) for q_id, text in affected_questions.items()]
    bulk_operations = [UpdateOne({"session_key": session_key}, {'$set': {f"questions_history.{item['id']}.question": item['text']}}) for item in affected_questions]

    if bulk_operations:
        automaton_sessions_collection.bulk_write(bulk_operations)

    # Update the history for the next question
    automaton_sessions_collection.update_one({"session_key": session_key}, {"$set": {f"questions_history.{next_step}": question_data}}, upsert=True)
    
    logger.debug(f"Next question details: {question_data}")
    return question_data

@app.get("/healthscan/{session_id}")
async def healthcheck(session_id: str):
    questionnaire_register_id = "PerpetHealthCheckIntro"
    questionnaire_id = "Back_Questionnaire"
    #logger.info(f"check registered session ID: {session_id}, Questionnaire ID: {questionnaire_register_id}")
    # Retrieve or create the Automaton and the session using the unique session_key
    automaton, _ = await get_automaton_for_user(session_id, questionnaire_register_id)
    session_data = session_collection.find_one({
        "session_id": session_id,
        "questionnaire_id": questionnaire_register_id
    })
    if not session_data:
        return {"message": "registration session not found"}
    
    session_key = session_data['session_key']
    # Retrieve the session data using the session_key
    session_data = session_collection.find_one({"session_key": session_key})
    # logger.debug(f"Session data: {session_data}")
    # Retrieve user_id from session data
    user_id = session_data.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=404, detail="User ID not found in session")
    
    petname = automaton.get_variable_value("@petname")
    pet_type = automaton.get_variable_value("@pet_type")
    gender = automaton.get_variable_value("@gender")
    redirect_url_template = "Back_Questionnaire?user_id={user_id}&pet_type={pet_type}&petname={petname}&gender={gender}"
    
    redirect_url = redirect_url_template.format(
                user_id=user_id,
                pet_type=pet_type,
                petname=petname,
                gender=gender
            )
    logger.debug(f"Found Redirect URL: {redirect_url}")
    
    #should create a session for the healthcheck questionnaire with the same user_id and petname and pet_type and gender
    automaton, _ = await get_automaton_for_user(session_id, questionnaire_id)
    automaton.set_variable_value("@petname", petname)
    automaton.set_variable_value("@pet_type", pet_type)
    automaton.set_variable_value("@gender", gender)
    
    # Get the current time with timezone set to UTC
    now_utc = datetime.now(timezone.utc)

    # Format the datetime object to the desired string format
    formatted_datetime = now_utc.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
    
    session_collection.update_one(
        {
        "session_id": session_id,
        "questionnaire_id": "Back_Questionnaire",
        },
        { "$set": {
                "session_key": f"{user_id}_{petname}_Back_Questionnaire",
                "insertDate": formatted_datetime,
                "automaton_id": "Back_Questionnaire",
                "user_id": int(user_id),
                "goto": '1',
                "user_answers": {},
                "variables": automaton.variables,
                "questions_history": {}
            }
        },
        upsert=True
    )

    return {"redirect_url": redirect_url}




def retrieve_first_image(user_id: int, pet_name: str):
    """ Retrieves image data for a given user and pet from MongoDB """
    try:
        # Define the filter for the document to find
        filter = {"user_id": user_id, "pet_name": pet_name}
        document = images_collection.find_one(filter)
        if document:
            images = document.get("images", [])
            first_image = images[0] if images else None
            # Delete the document after retrieving the image
            images_collection.delete_one(filter)

            return first_image
        else:
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve image data")

def post_pet_profile_img(user_id, petname, pet_id, access_token):
    """Post images to the external pet profile image registration API."""
    api_url = f'{APISERVER}/user-service/v1/pet/profile_img'
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    first_image = retrieve_first_image(user_id, petname)
    logger.debug(f"image found for user_id:{user_id} and petname:{petname}")
    
    if first_image:
        # Strip the prefix and decode the Base64 string
        if first_image.startswith('data:image/jpeg;base64,'):
            first_image = first_image.split(',', 1)[1]
        image_data = base64.b64decode(first_image)
        image_file = BytesIO(image_data)
        image_file.name = f'{user_id}_{petname}.jpeg'  # Naming the file
        
        #files = {'image': image_file}
        files = {'image': ('filename.jpg', image_file, 'image/jpeg')}
        data = {'pet_id': str(pet_id)}
        
        response = requests.post(api_url, headers=headers, files=files, data=data)
        
        # Handle the response
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to upload image: {response.status_code} {response.text}")

@app.get("/{user_id}/{pet_name}/isRegistered")
async def isRegistered(user_id: int, pet_name: str):
    """ Check if the pet is already registered in the database """
    try:
        petprofile = pet_db.get_pet_profile(user_id, pet_name)
        logger.debug(f"For user_id={user_id} and pet_name = {pet_name} found Pet profile: {petprofile}")
        return petprofile is not None
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="Failed to check if pet is already registered")

@app.get("/{user_id}/{pet_name}/existNonRegistered")
async def existNonRegistered(user_id: int, pet_name: str):
    """ Check if the pet is in mondodb with key user_id / petname / PerpetHealthCheckIntro """
    try:
        session_key = f"{user_id}_{pet_name}_PerpetHealthCheckIntro"
        # Define the filter for the document to find
        filter = {"session_key": session_key}
        document = session_collection.find_one(filter)
        if document:
            petprofile = pet_db.get_pet_profile(user_id, pet_name)
            if petprofile is None:
                return True
            else:
                logger(f"user_id:{user_id} has a registered pet name: {petname}")
                return False
        else:
            return False
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="Failed to check existNonRegistered")

@app.delete("/{user_id}/{pet_name}/deleteNonRegistered")
async def deleteNonRegistered(user_id: int, pet_name: str):
    """ delete Non Registered in mongoDB """
    try:
        petprofile = pet_db.get_pet_profile(user_id, pet_name)
        if petprofile is None:
            session_key = f"{user_id}_{pet_name}_PerpetHealthCheckIntro"
            filter = {"session_key": session_key}
            session_collection.delete_one(filter)
        return True
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="Failed to deleteNonRegistered")
    
@app.get("/{user_id}/{pet_name}/existNonScanned")
async def existNonScanned(user_id: int, pet_name: str):
    """ Check if the pet is we have a session in mongodb for back_questionnaire collection """
    try:
        session_key = f"{user_id}_{pet_name}_Back_Questionnaire"
        # Define the filter for the document to find
        filter = {"session_key": session_key}
        document = session_collection.find_one(filter)
        if document:
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="Failed to check existNonScanned")
    
@app.delete("/{user_id}/{pet_name}/deleteNonScanned")
async def deleteNonScanned(user_id: int, pet_name: str):
    """delete session in back_questionnaire collection """
    try:
        session_key = f"{user_id}_{pet_name}_Back_Questionnaire"
        # Define the filter for the document to find
        filter = {"session_key": session_key}
        session_collection.delete_one(filter)
        return True
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete deleteNonScanned")

@app.get("/pet_register/{session_id}")
async def register_pet(request: Request, session_id: str):
    questionnaire_id = "PerpetHealthCheckIntro"
    logger.info(f"Registering pet for session ID: {session_id}, Questionnaire ID: {questionnaire_id}")
    # Retrieve or create the Automaton and the session using the unique session_key
    automaton, _ = await get_automaton_for_user(session_id, questionnaire_id)
    # Create a unique composite key for session and questionnaire
    #session_key = f"{session_id}_{questionnaire_id}"
    session_data = session_collection.find_one({
        "session_id": session_id,
        "questionnaire_id": questionnaire_id
    })
    session_key = session_data['session_key']
    # Retrieve the session data using the session_key
    session_data = session_collection.find_one({"session_key": session_key})
    
    logger.debug(f"Session data: {session_data}")
    # Retrieve user_id from session data
    user_id = session_data.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=404, detail="User ID not found in session")
    else:
        logger.debug(f"User ID: {user_id}")

    from register_map import health_map
    logger.info("Questionnaire completed => Must register pet")
    # register_pet(questionnaireId, session_id)
    logger.info(f"variables: {automaton.variables}")
    # Prepare the data to be sent
    earfold = automaton.get_variable_value("@ear_folded")
    if earfold is not None:
        earfold = health_map["ear_folded_" + earfold]
    petname = automaton.get_variable_value("@petname")
    pet_data = {
        "user_id": user_id,
        "type": automaton.get_variable_value("@pet_type"),
        "name": automaton.get_variable_value("@petname"),
        "breeds_id": convert_to_number(automaton.get_variable_value("@breeds_id")),
        "age": format_date(automaton.get_variable_value("@age")),
        "gender": health_map["gender_"+automaton.get_variable_value("@gender")],
        "profile": {
            "neutralization_code": convert_to_number(health_map["neutering_surgery_"+automaton.get_variable_value("@neutering_surgery")]),
            "body_form_code": convert_to_number(health_map["body_shape_"+automaton.get_variable_value("@body_shape")]),
            "weight": convert_to_number(automaton.get_variable_value("@body_weight")),
            "conditions_code": convert_to_number(health_map["energetic_"+automaton.get_variable_value("@energetic")]),
            "appetite_change_code": convert_to_number(health_map["appetite_"+automaton.get_variable_value("@appetite")]),
            "feed_amount_code": convert_to_number(health_map["pet_food_"+automaton.get_variable_value("@pet_food")]),
            "snack": health_map["treat_"+automaton.get_variable_value("@treat")],  # Assuming it's a string "Y" or "N"
            "drinking_amount_code": convert_to_number(health_map["water_intake_"+automaton.get_variable_value("@water_intake")])
        }
    }
    
    if earfold:
        pet_data["profile"]["ear_folded"] = earfold
    if automaton.get_variable_value("@multi_animal_environment"):
        pet_data["profile"]["relationship_code"] = health_map["multi_animal_environment_" + automaton.get_variable_value("@multi_animal_environment")]
    if automaton.get_variable_value("@living_space"): 
        pet_data["profile"]["main_act_place_code"] = convert_to_number(health_map["living_space_"+automaton.get_variable_value("@living_space")])
    if automaton.get_variable_value("@daily_walk"):
        pet_data["profile"]["walk_code"] = convert_to_number(health_map["daily_walk_"+automaton.get_variable_value("@daily_walk")])   
    if automaton.get_variable_value("@allergy_detect"):
        pet_data["profile"]["how_to_know_allergy_code"] = convert_to_number(health_map["allergy_detect_"+automaton.get_variable_value("@allergy_detect")])
    if automaton.get_variable_value("@allergy_id"):
        pet_data["profile"]["allergy_id"] = automaton.get_variable_value("@allergy_id")  # Assuming it's a comma-separated string of numbers
    if automaton.get_variable_value("@disease_treatment"):
        pet_data["profile"]["disease_treat_code"] = convert_to_number(health_map["disease_treatment_"+automaton.get_variable_value("@disease_treatment")])
    else:
        pet_data["profile"]["allergy_id"] = ""
    if automaton.get_variable_value("@disease_id"):
        #pet_data["profile"]["disease_id"] = automaton.get_variable_value("@disease_id")  # Assuming it's a comma-separated string of numbers
        disease_ids = automaton.get_variable_value("@disease_id")
        logger.debug(f"Disease IDs: {disease_ids}")
        # disease_id_string = ','.join(disease_ids) => no, it's already comma separated
        # logger.debug(f"Disease IDs string : {disease_id_string}")
        
        # Handle disease_ids whether it's a list or a string
        if isinstance(disease_ids, list):
            disease_id_string = ','.join(disease_ids)
        else:
            disease_id_string = disease_ids
        
        pet_data["profile"]["disease_id"] = disease_id_string

    else:
        pet_data["profile"]["disease_id"] = ""

    # Log the data for debugging purposes
    logger.info(f"FastAPI: Sending pet registration data: {pet_data}")
    
    # login_info = loginUser(user_id)
    # logger.debug(f"Login info: {login_info}")
    # accessToken = login_info['accessToken']
    # Retrieve the access token from the request headers
    accessToken = request.headers.get('Authorization')
    if not accessToken:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    # Assume the accessToken is in the format 'Bearer <token>'
    accessToken = accessToken.split(" ")[1] if " " in accessToken else accessToken
    logger.info(f"Access Token: {accessToken}")
    # Set up headers for authorization
    headers = {
        'Authorization': f'Bearer {accessToken}'
    }
    # Send the data to the external service
    try:
        response = requests.post(f'{APISERVER}/user-service/v1/pet', json=pet_data, headers=headers)
        response.raise_for_status()  # This will raise an HTTPError for bad responses
        # should update the session with the pet_id and survey_id
        answer = response.json()
        logger.info(f"Pet registration response: {answer}")
        pet_id = answer['data']['id']
        logger.debug(f"Pet id: {pet_id}")
        # Record the session completion and pet_id
        completion_info = {
            'session_complete': True,
            'completion_date': datetime.now(timezone.utc).isoformat(),
            'pet_id': pet_id
        }
        # Update the session data with the completion info
        automaton_sessions_collection = mongo_db.automaton_sessions
        automaton_sessions_collection.update_one(
            {"session_key": session_key},
            {"$set": completion_info},
            upsert=True
        )
        
        post_pet_profile_img(user_id, petname, pet_id, accessToken)
        
        return  answer # Return the JSON response content
    except requests.RequestException as e:
        logger.error(f"Failed to register pet: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to register pet") from e   

def get_provider_id(user_id: int):
    """
    Retrieves the provider details from the user's profile and extracts the provider type and the rest of the provider_id.
    """
    user_profile = user_db.get_user_profile(user_id)
    if user_profile:
        if isinstance(user_profile, dict) and "error" in user_profile:
            raise HTTPException(status_code=404, detail=user_profile["error"])
        
        # Assuming 'provider_id' is directly stored in the user_profile dictionary
        provider_id = user_profile.get('provider_id')
        logger.debug(f"Provider ID: {provider_id}")
        if not provider_id:
            raise HTTPException(status_code=404, detail="Provider ID not found")
        
        # Split the provider_id at the first underscore
        parts = provider_id.split('_', 1)
        if len(parts) > 1:
            provider_type, rest = parts
        else:
            provider_type = parts[0]
            rest = None  # If there's no underscore
        logger.debug(f"Provider Type: {provider_type}, ID: {rest}")
        return provider_type, rest
    else:
        raise HTTPException(status_code=500, detail="Unable to retrieve user profile")
    
# @app.get("/login/{user_id}")
# async def loggin(user_id: str):
#     return loginUser(user_id)

def loginUser(user_id: str):
    provider, id = get_provider_id(user_id)
    logger.debug(f"provider: {provider}, id={id}")
    url = f"{APISERVER}/user-service/v1/auth/social"
    data = {
        "id": id,
        "type": provider,
        "service_agree": "Y", 
        "privacy_agree": "Y"
    }
    logger.debug(f"Logging in user: {data}")

    try:
        # Make the POST request to external service
        response = requests.post(url, json=data)
        response.raise_for_status()  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
        user_data = response.json()['data']
        logger.debug("Success login user:", user_data)

        # Fetch user profile from internal database
        user_profile = user_db.get_user_profile(user_data['id'])
        if user_profile:
            logger.debug(f"Retrieved internal user profile successfully: {user_profile}")
        else:
            logger.warning(f"No internal profile found for user_id: {user_data['id']}")
        
        return user_data  # or return user_profile based on your requirements

    except requests.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        raise HTTPException(status_code=response.status_code, detail=str(http_err))
    except Exception as err:
        logger.error(f"An error occurred: {err}")
        raise HTTPException(status_code=500, detail=str(err))

def load_metadata_text(filepath='metadatatext.json'):
    try:
        with open(filepath, 'r') as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        print("The file was not found.")
    except json.JSONDecodeError:
        print("Error decoding JSON from the file.")
    except Exception as e:
        print(f"An error occurred: {e}")

def convert_to_number(value):
    if value == "" or value is None:
        return None
    try:
        # First try converting directly to an int
        value = int(value)
        #logger.debug(f"Converted value to int: {value}")
        return value
    except ValueError:
        # If int conversion fails, try float
        try:
            value = float(value)
            #logger.debug(f"Converted value to int: {value}")
            return value
        except ValueError:
            # Return the original value if it's neither int nor float
            #logger.debug(f"Converted value failed: {value}")
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
                        logger.debug(f"FastAPI: API Call response of sub url {new_url} with id: {id_clean}")
                        response.raise_for_status()
                        combined_results.append(response.json())

                    break  # Exit after handling the first list parameter

        if not combined_results:  # If no list parameters were found or processed
            # Execute a normal API call with the original URL
            response = requests.get(url)
            logger.debug(f"FastAPI: API Call for single url: {url}")
            response.raise_for_status()
            combined_results.append(response.json())
        #logger.debug(f"FastAPI: API Call response of url {url}\n: {combined_results} ")
        return combined_results
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

# def extract_data(json_data, custom_path):
#     # If the JSON data is a list and not a dictionary at the top level, we wrap it in a dictionary
#     if isinstance(json_data, list) and len(json_data) == 1:
#         json_data = json_data[0]  # Use the first dictionary in the list
    
#     # Use regular expressions to parse the custom path
#     match = re.match(r"(.*)\[\*\]\.\((.*)\)", custom_path)
#     if not match:
#         return "Invalid custom path format"
    
#     base_path, fields = match.groups()
#     field_list = fields.split(", ")
    
#     # Navigate to the correct level in the JSON data
#     content = json_data
    
#     for key in base_path.split('.'):
#         if isinstance(content, dict) and key in content:
#             print(key, content[key])
#             content = content[key]
#         else:
#             return "Path not found or not a dictionary at some level"
    
#     # Ensure the content is a list for iteration
#     if not isinstance(content, list):
#         return "Expected list at path, got something else"
    
#     # Extract the specified fields from each item in the list
#     result = []
#     for item in content:
#         values = [str(item.get(field, 'Field not found')) for field in field_list]
#         result.append(":".join(values))
    
#     list_result = "\n".join(result)
#     logger.debug(f"FastAPI: Extracted data: {list_result}")
#     return list_result


def extract_data(json_data, path):
    import logging
    logger = logging.getLogger(__name__)
    
    # Check if the initial json_data is a list and use the first element
    if isinstance(json_data, list):
        json_data = json_data[0]
    
    #logger.debug(f"FastAPI: Extracting data from JSON: {json_data}")
    
    try:
        base_path, fields = path.split('[*].')
        fields = fields.strip('()').split(',')
        fields = [field.strip() for field in fields]
        
        # Navigate to the base path in the JSON data
        for key in base_path.split('.'):
            json_data = json_data[key] if key in json_data else None
            if json_data is None:
                raise KeyError(f"Key '{key}' not found in the JSON data.")
        
        # Extract the desired fields from each item in the resulting JSON data
        results = []
        for item in json_data:
            result = ':'.join(str(item.get(field, 'Field not found')) for field in fields)
            results.append(result)
        
        # Joining all results with newline characters
        list_result = '\n'.join(results)
        logger.debug(f"FastAPI: Extracted data: {list_result}")
        return list_result
    
    except Exception as e:
        logger.error(f"Error extracting data: {str(e)}")
        return f"Error: {str(e)}"

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

def extract_image_key(option_str: str, automaton) -> str:
    # Regex to handle conditional images
    conditional_pattern = re.compile(
        r"IF\(@(?P<var_name>\w+)==(?P<value>\w+)\) THEN IMG\((?P<true_img>[^\)]+)\) ELSE IMG\((?P<false_img>[^\)]+)\)"
    )
    # Check if the condition exists in the option string
    match = conditional_pattern.search(option_str)
    if match:
        var_name = match.group('var_name')
        value = match.group('value')
        true_img = match.group('true_img')
        false_img = match.group('false_img')
        
        # Obtain the current value from the automaton, simulate it here
        actual_value = automaton.get_variable_value(f"@{var_name}")
        # Return the appropriate image based on the condition
        return true_img if actual_value == value else false_img
    else:
        # Default image if no conditional logic is found
        return "default_image.png"


def extract_content_based_on_condition(option_str: str, automaton: Automaton) -> str:
    # Split the option string into parts, potentially containing conditional or non-conditional segments
    segments = option_str.split('\n')  # Adjust the delimiter based on actual data format, here assuming newline

    result = []
    conditional_pattern = re.compile(
        r"IF\(@(?P<var_name>\w+)==(?P<value>[^)]+)\) THEN \((?P<true_content>[^)]+)\)(?: ELSE \((?P<false_content>[^)]+)\))?"
    )

    for segment in segments:
        match = conditional_pattern.search(segment)
        if match:
            var_name = "@" + match.group('var_name')
            value = match.group('value')
            true_content = match.group('true_content')
            false_content = match.group('false_content') or ""

            # Get the actual value from the automaton
            actual_value = automaton.get_variable_value(var_name)
            
            # Append the appropriate content based on the condition
            if actual_value == value:
                if true_content:  # Ensure true_content is not empty
                    result.append(true_content)
            elif false_content:  # Check if false_content is not empty before appending
                result.append(false_content)
        else:
            # Append the segment directly if no conditional logic is found
            result.append(segment)

    return '\n'.join(result)


def parse_answer_choices(answer_choices: str, automaton) -> List[str]:
    """
    Parses and formats the answer choices from a provided string for UI.
    """
    options = answer_choices.split('\n')
    formatted_options = []
    for option in options:
        # Split based on the first occurrence of ' - '
        parts = option.split(' - ', 1)
        if len(parts) == 2:
            description, condition = parts
            img_src = extract_image_key(condition, automaton)
            formatted_option = f"{description.strip()} - <img src='{img_src}'>"
            formatted_options.append(formatted_option)
        else:
            # Log or handle the error if the option does not split into two parts
            formatted_options.append("Error in option format.")
    return '\n'.join(formatted_options)

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

@app.get("/")
async def home(request: Request, response: Response):
    # endpoint with conditional logging
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Handling request: {request.url}")
    return templates.TemplateResponse("intro.html", {"request": request})

@app.get("/get_report/{user_id}/{petname}")
async def get_report(request: Request, user_id: int, petname: str = Path(..., description="The name of the pet")):
    
    # Retrieve the access token from the request headers
    accessToken = request.headers.get('Authorization')
    if not accessToken:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    # Assume the accessToken is in the format 'Bearer <token>'
    accessToken = accessToken.split(" ")[1] if " " in accessToken else accessToken
    logger.info(f"FastAPI: Getting health report for user ID: {user_id} and petname: {petname} and access token: {accessToken}")
    metadatatexts = getMetadataText(user_id, petname)
    '''
    {pet_id} // {usr_id} // {
	"user_id": "",
	"pet_id": "",
	"survey_metadatas": []
    ''' 
    pet_id = pet_db.get_pet_profile(user_id, petname)
    logger.info(f"Pet ID: {pet_id}")
    result = {
        "user_id": user_id,
        "pet_id": pet_id,
        "survey_metadatas": metadatatexts
    }
    # Set up headers for authorization
    headers = {
        'Authorization': f'Bearer {accessToken}'
    }
    # try:
    #     logger.info(f"Sending health report data: {result}")
    #     response = requests.post(f'{APISERVER}/checkup-service/v2/checkup', json=result, headers=headers)
    #     response.raise_for_status()  # This will raise an HTTPError for bad responses
    #     # should update the session with the pet_id and survey_id
    #     answer = response.json()
    #     logger.info(f"health report response: {answer}")
    #     # Access the 'id' value within the 'data' dictionary
        
    #     checkup_id = answer['data']['id']
    #     #url = f"{APISERVER}/report-service/v2/report/{checkup_id}/redirect"
    #     logger.debug(f"Checkup ID: {checkup_id}")
    #     return checkup_id
        
    # except requests.RequestException as e:
    #     logger.error(f"Failed to get health report: {str(e)}")
    #     raise HTTPException(status_code=400, detail="Failed to get health report") from e
    url = f'{APISERVER}/checkup-service/v2/checkup'
    async with aiohttp.ClientSession() as session:
        try:
            logger.info(f"Sending health report data: {result}")
            async with session.post(url, json=result, headers=headers) as response:
                if response.status != 200:
                    response_text = await response.text()
                    logger.error(f"Failed to get health report: {response_text}")
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=response_text,
                        headers=response.headers
                    )
                answer = await response.json()
                logger.info(f"health report response: {answer}")
                
                checkup_id = answer['data']['id']
                logger.debug(f"Checkup ID: {checkup_id}")
                return checkup_id
        
        except aiohttp.ClientError as e:
            logger.error(f"Failed to get health report: {str(e)}")
            raise HTTPException(status_code=400, detail="Failed to get health report") from e

@app.get("/get_metadatatexts/{user_id}/{petname}")
async def get_metadatext(user_id: int, petname: str):
    response_data = getMetadataText(user_id, petname)
    return response_data

def getMetadataText(user_id: int, petname: str):
    logger.debug(f"FastAPI: Getting metadata text for user ID: {user_id} and petname: {petname}")
    session_key = f"{user_id}_{petname}_PerpetHealthCheckIntro"
    session_data = session_collection.find_one({
        "session_key": session_key,
        "questionnaire_id": "PerpetHealthCheckIntro"
    })
    automaton = Automaton()
    if session_data:
        automaton.deserialize_data(session_data)
        
    variables_front = automaton.variables
    response_id_front = f"{user_id}_{petname}_PerpetHealthCheckIntro"
    
    session_key = f"{user_id}_{petname}_Back_Questionnaire"
    session_data = session_collection.find_one({
        "session_key": session_key,
        "questionnaire_id": "Back_Questionnaire"
    })
    automaton = Automaton()
    if session_data:
        automaton.deserialize_data(session_data)
    
    variables_back = automaton.variables
    response_id_back = f"{user_id}_{petname}_Back_Questionnaire"
    
    logger.debug(f"FastAPI: => User ID: {user_id}\n \
                => Variables Back: {variables_back}\n \
                => Variables Front: {variables_front} \n \
                ")
    
    metadata_text = [] 

    required_keys = {'disease_id', 'allergy_id'}  # Keys that need default values if absent or empty
    default_value = "no"  # Set this outside the loop, so it's not reset every iteration

    for key in required_keys:
        #logger.debug(f"Checking key: {key}")
        vf = variables_front.get(f'@{key}', default_value)  # Use default_value here
        #logger.debug(f"variables_front: {vf}")

        # If the value is falsy, or the key is not in variables_front, append the default text
        if not vf or vf == 'no':  # This already checks both: f'@{key}' not in variables_front or not variables_front[f'@{key}']
            metadata_text.append(f"{key[:-3]}:{default_value}")  # Append default value, like 'disease:no'
            logger.debug(f"{key}: {default_value}")
        # else:
        #     metadata_text.append(f"{key[:-3]}:{vf}")  # If key exists and value is not falsy, append the value
        #     logger.debug(f"{key}: {vf}")
    
    ignored_variables = {'query_params', 'petname'}
    for key, value in variables_front.items():
        if key.startswith('@'):
            metadata_key = key[1:]  # Remove '@' to match keys in the map
            if metadata_key in ignored_variables:
                continue
            logger.debug(f"variable => {metadata_key}: value={value}")
            if metadata_key == 'breeds_id':
                logger.debug(f"breeds_id: {value}")
                metadata = getBreedMetaText(convert_to_number(value))
                logger.debug(f"metadata: {metadata}")
                metadata_text.append(metadata)
            elif metadata_key == 'disease_id':
                if value:  # Check if value is not empty
                    for disease_id in value:
                        logger.debug(f"disease_id: {disease_id}")
                        metadata = getDiseaseMetaText(disease_id)
                        if metadata:
                            metadata_text.append(metadata)
                            logger.debug(f"disease metadata: {metadata}")
                else:
                    metadata_text.append("disease:no")
                    logger.debug("disease:no")
            elif metadata_key == 'sub_disease_id':
                if value.strip():  # Check if value is not empty
                    for sub_disease_id in value.split(","):
                        logger.debug(f"sub_disease_id: {sub_disease_id}")
                        metadata = getDiseaseMetaText(sub_disease_id)
                        if metadata:
                            metadata_text.append(metadata)
                            logger.debug(f"metadata: {metadata}")
            elif metadata_key == 'allergy_id':
                if value.strip():  # Check if value is not empty
                    for allergy_id in value.split(","):
                        logger.debug(f"allergy_id: {allergy_id}")
                        metadata = getAllergyMetaText(allergy_id)
                        if metadata:
                            metadata_text.append(metadata)
                            logger.debug(f"allergy metadata: {metadata}")
                else:
                    metadata_text.append("allergy:no")
                    logger.debug("allergy:no")
            elif metadata_key == 'age' and value.strip():
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
                    # Append formatted data to metadata text
                    formatted_age = f"{birth_date.year}-{birth_date.month:02}"
                    #metadata_text.append(f"age:{formatted_age}")
                    metadata_text.append(f"age:{age_category}")
                    
                except ValueError as e:
                    # Log and raise an error if the date is incorrect
                    logger.error(f"Error processing the date: {e}")
                    raise HTTPException(status_code=400, detail=f"Invalid date format for age: {value}")
                
            elif metadata_key in metadatatexts_map:
                metadata_info = metadatatexts_map[metadata_key]
                logger.debug(f"metadata_key: {metadata_key}, metadata_info: {metadata_info}")
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
            else:
                logger.debug(f"metadata_key: {metadata_key} not found in the metadata map")
                full_metadata = f"{metadata_key}:{value}"
                metadata_text.append(full_metadata)
    
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
    ignored_variables = {'type', 'user_id', 'pet_id', 'petname', 'gender', 'target', 'body_weight', 'query_params', 'pet_type'}
    for key, value in variables_back.items():
        if key.startswith('@'):
            #logger.debug(f"back variable => {key}: {value}")
            metadata_key = key[1:]  # Remove '@' to match keys in the map
            #logger.debug(f"variable => {metadata_key}: {value}")
            if metadata_key not in ignored_variables:
                # Process and log if the variable is not in the ignored set
                full_metadata = f"{metadata_key}:{value}"
                metadata_text.append(full_metadata)
                #logger.debug(f"Processed variable => {metadata_key}: {value}")
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

breedid_map, allergyid_map, diseaseid_map = {}, {}, {}
metadatatexts_map = {}
def getBreedMetaText(breed_id: str) -> str:
    #logger.debug(f"breedid_map: {breedid_map}")
    return breedid_map.get(breed_id, "No metadata found for this breed ID")

def getDiseaseMetaText(disease_id: str) -> str:
    if len(disease_id) == 0:
        return None
    # logger.debug(f"getDiseaseMetaText -> diseaseid: {disease_id}")
    diseaseMeta = diseaseid_map.get(int(disease_id), None) 
    logger.debug(f"getDiseaseMetaText ->  diseaseid: {disease_id} => diseaseMata: {diseaseMeta}")
    return diseaseMeta

def getAllergyMetaText(allergy_id: str) -> str:
    #logger.debug(f"allergy_id: {allergy_id}")
    if len(allergy_id) == 0:
        return None
    return allergyid_map.get(int(allergy_id), None)

@app.on_event("startup")
async def startup_event():
    global breedid_map, allergyid_map, diseaseid_map, metadatatexts_map
    metadatatexts_map = load_metadata_text()
    # Load the JSON data from a file
    with open('breed_Metadata.json', 'r', encoding='utf-8') as file:
        data = json.load(file)

    # Create a map from breed_id to metadata_text
    breedid_map = {
        item['breed_id']: item['metadata_text'] 
        for item in data
        if '_breed' in item['metadata_text']
    }
    #logger.debug(f"breedid_map:{breedid_map}")

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
        if item['metadata_text'].startswith('disease:')
    }
    logger.debug(f"diseaseid_map:{diseaseid_map}")
    session_collection.create_index([("session_id", ASCENDING), ("questionnaire_id", ASCENDING)], unique=True)

LOGLEVEL = logging.DEBUG
# Set the logging level for Uvicorn loggers
logging.getLogger("uvicorn").setLevel(LOGLEVEL)
logging.getLogger("uvicorn.error").setLevel(LOGLEVEL)
logging.getLogger("uvicorn.access").setLevel(LOGLEVEL)

# Attempt to set the level for "uvicorn.asgi" only if it exists
if logging.getLogger("uvicorn.asgi"):
    logging.getLogger("uvicorn.asgi").setLevel(LOGLEVEL)

@app.on_event("startup")
async def startup_event():
    import logging 
    logger.setLevel(LOGGING_LEVEL)
    # Register with Eureka when the FastAPI app starts
    logger.info(f"Application startup: Registering {PREFIXURL} service on port {PORT} with Eureka at {EUREKA} and logging level: {LOGGING_LEVEL}")
    await register_with_eureka()
    logger.info(f"Application startup: Registering {PREFIXURL} done")

async def register_with_eureka():
    if PREFIXURL == "/backsurvey-service":
        # Asynchronously register service with Eureka
        try:
            logger.debug(f"Registering with Eureka at {EUREKA}...")
            await eureka_client.init_async(eureka_server=EUREKA,
                                        app_name="backsurvey-service",
                                        instance_port=PORT)
            logger.info("Registration with Eureka successful.")
        except Exception as e:
            logger.error(f"Failed to register with Eureka: {e}")
            
# Set the root logger level if you want to adjust the overall logging level
logging.getLogger().setLevel(LOGGING_LEVEL)
from config import PORT
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level=LOGGING_LEVEL.lower())
