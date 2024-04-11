# server.py
from fastapi import FastAPI, Body, Form, Header, HTTPException, Depends, Response, Request, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, Tuple, List, Dict
import os
from automaton import Automaton
from config import LOGGING_CONFIG, MONGODB
#import firebase_admin
#from firebase_admin import credentials, firestore
import uvicorn
import requests
import re
import uuid
from pymongo import MongoClient
from fastapi.middleware.cors import CORSMiddleware

import logging
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

class AnswerSubmission(BaseModel):
    question_id: str
    user_answer: str
    # question: str
    # why_we_asked : str
    # answer_type: str
    # answer_choices: str 
    # redo_questions: List[str]
    # page_number: int

class SingleAnswer(BaseModel):
    variable_name: str
    value: str
class AnswersSubmission(BaseModel):
    question_id: str
    answers: List[SingleAnswer]  # List of answers

client = MongoClient(MONGODB)
mongo_db = client.perpet_healthcheck

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

async def get_automaton_for_user(session_id: str, questionnaire_id: str) -> Tuple[Automaton, str]:
    """
    Retrieves an Automaton instance for a given user ID and questionnaire ID.
    If no Automaton is associated with the user ID, a new instance is created
    using the questionnaire file corresponding to the questionnaire ID.

    Args:
        session_id (str): The session_id for which the Automaton is to be retrieved or created.
        questionnaire_id (str): The questionnaire ID to load the appropriate questionnaire.

    Returns:
        Tuple[Automaton, str]: A tuple containing the Automaton instance and the user ID.
    """
    logger.debug(f"FastAPI session_id: {session_id}, questionnaire_id: {questionnaire_id} => get_automaton_for_user")
    automaton = Automaton()
    # Step 1: Check if the Automaton for the questionnaire_id exists, if not, create it.
    automaton_collection = mongo_db.automatons
    if automaton_states := automaton_collection.find_one(
        {"name": questionnaire_id}
    ):
        logger.debug(f"FastAPI: for questionnaire_id: {questionnaire_id} found in MongoDB. Load Automaton from DB")
        automaton_id = automaton_states["_id"]
        automaton.name = automaton_id
        # Create Automaton instance from state data
        automaton.deserialize_states(automaton_states)
        logger.debug(f"FastAPI: for questionnaire_id: {questionnaire_id} => Automaton: {automaton.serialized_states()}")
    else:
        logger.debug(f"FastAPI: for questionnaire_id: {questionnaire_id} not found. Load from excel")
        automaton = Automaton()
        automaton.load_from_excel(f"{questionnaire_id}.xlsx")
        new_automaton = automaton.serialized_states()
        inserted_document = automaton_collection.insert_one(new_automaton)
        logger.debug(f"FastAPI: for questionnaire_id: {questionnaire_id} => Inserted document: {inserted_document}")
        automaton_id = inserted_document.inserted_id

    # Step 2: Create or Retrieve a session for this user and automaton
    session_collection = mongo_db.automaton_sessions
    if session_data := session_collection.find_one({"_id": session_id}):
        logger.debug(f"FastAPI: for session_id: {session_id} => Found Session data: {session_data}")
        # Process existing session data
        automaton.deserialize_data(session_data)
    else:
        #logger.debug(f"FastAPI: for session_id: {session_id} => New session for the automaton_id {automaton_id}")
        new_session = {
            "_id": session_id,
            "session_id": session_id,
            "automaton_id": automaton_id
        }
        session_collection.insert_one(new_session)

    return automaton, session_id

@app.get("/questionnaire/{automaton_id}/{session_id}/restore")
async def restore_session(automaton_id: str, session_id: str):
    session_collection = mongo_db.automaton_sessions
    session_data = session_collection.find_one({"_id": session_id})

    # If session_data is not found, create a new session
    if not session_data:
        # Initialize an empty session data structure
        new_session_data = {
            "_id": session_id,
            "session_id": session_id,
            "automaton_id": automaton_id
        }
        # Insert the new session into the database
        session_collection.insert_one(new_session_data)
        session_data = new_session_data
        logger.info(f"New session created with session_id: {session_id}")

    # Proceed with session restoration logic
    # Initialize the Automaton instance and deserialize its state
    automaton = Automaton()
    automaton.deserialize_data(session_data)
    # The rest of your restoration logic here
    questions_history = session_data.get("questions_history", {})
    current_question_id = automaton.goto  # or some default value
    questionnaire_id = automaton.name  # Assuming the questionnaire ID is stored in the automaton's name attribute
    restored_session_data = {
        "session_id": session_id,
        "questionnaire_id": questionnaire_id,
        "current_question_id": current_question_id,
        # "current_question": {},  # You may want to fetch the current question based on current_question_id
        "questions_history": questions_history,
        "variables": automaton.variables,  # Optionally include other automaton states if needed
        "user_answers": session_data.get("user_answers", {})
    }
    
    logger.info(f"Restored session data: {restored_session_data}")
    return restored_session_data

#2 Save Session State
@app.post("/questionnaire/{session_id}/save")
async def save_session(session_id: str, session_data: dict):
    session_collection = mongo_db.automaton_sessions
    result = session_collection.update_one({"_id": session_id}, {"$set": session_data}, upsert=True)
    if result.modified_count == 0 and result.upserted_id is None:
        raise HTTPException(status_code=500, detail="Failed to save session")
    return {"message": "Session saved successfully"}

#End or Reset Session
@app.post("/questionnaire/{session_id}/end")
async def end_session(session_id: str):
    session_collection = mongo_db.automaton_sessions
    # Option 1: Delete the session
    session_collection.delete_one({"_id": session_id})
    # Option 2: Reset the session (if you prefer to keep the session record)
    # automaton = Automaton()
    # initial_state = automaton.serialize_data()  # Assuming serialize_data() can represent the initial state
    # session_collection.update_one({"_id": session_id}, {"$set": initial_state}, upsert=True)

    return {"message": "Session ended successfully"}

@app.post("/get_question/{questionaire_id}/{question_id}")
async def get_question(response: Response, request: Request, questionaire_id: str, question_id: str, query_params: Optional[dict] = Body(default=None)):
    session_id = request.headers.get('session_id', None) or request.cookies.get('session_id', None)

    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info(f"FastAPI generated new session_id: {session_id}")
        # Set the cookie
        response.set_cookie(key="session_id", value=session_id)

    logger.info(f"FastAPI session_id: {session_id} => Question ID: {question_id}")
    logger.info(f"Query Parameters: {query_params}")

    automaton, session_id = await get_automaton_for_user(session_id, questionaire_id)
    logger.info(f"Found automaton for session_id: {session_id}, questionaire_id: {questionaire_id}, automaton: {automaton.serialized_states()}, automaton: {automaton.serialize_data()}")
    
    if question_id == "1" and query_params:
        for key, inner_dict in query_params.items():
            if isinstance(inner_dict, dict):
                for inner_key, value in inner_dict.items():
                    formatted_key = f"@{inner_key}"
                    if len(formatted_key) > 1:
                        automaton.set_variable_value(formatted_key, value)

        # Serialize and save the state to 
        # Firestore
        # db.collection("automaton_sessions").document(session_id).set(automaton.serialize())
        # MongoDB: Serialize and save or update the state
        automaton_data = automaton.serialize_data()
        automaton_sessions_collection = mongo_db.automaton_sessions
        automaton_sessions_collection.update_one({"_id": session_id}, {"$set": automaton_data}, upsert=True)

    node = automaton.states.get(question_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Question not found")

    question = automaton.substitute_placeholders(node['Question'])
    answer_choices = node.get("AnswerChoices")
    logger.debug(f"FastAPI: => Answer choices: {answer_choices}")
    if "APICALL" in answer_choices:
        logger.debug("Should make API CALL")
        api_call = answer_choices.split("APICALL(")[1].split(")")[0]
        api_call = automaton.substitute_placeholders(api_call)
        logger.debug(f"API CALL: {api_call}")
        if "EXTRACT" in answer_choices:
            logger.debug(f"get_question - answer_choices: {answer_choices}")
            extract_key = extract_from_function(answer_choices)
            response = make_api_call(api_call)
            logger.debug(f"get_question - Should Extract data: {extract_key}")
            answer_choices = extract_data(response, extract_key)
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
        "question_id": question_id,
        "question": question,
        "answer_type": node.get("AnswerType"),
        "answer_choices": parsed_choices,
        "page_number": node.get("Page"),
        "why_we_asked": node.get("WhyWeAsk"),
        #"design": node.get("Design"),
        "updated_questions": [],
        "redo_questions": [],
        "remove_questions": []
    }
    
    logger.debug(f"FastAPI:/get_question/{questionaire_id}/{question_id} => Next question: {question_data}")
    # MongoDB: Serialize and save or update the state
    automaton.update_questions_path(question_id)
    automaton_data = automaton.serialize_data()
    automaton_sessions_collection = mongo_db.automaton_sessions
    automaton_sessions_collection.update_one({"_id": session_id}, {"$set": automaton_data}, upsert=True)
    # Add the current question data to `questions_history`
    update_history_query = {"$set": {f"questions_history.{question_id}": question_data}}
    automaton_sessions_collection.update_one({"_id": session_id}, update_history_query, upsert=True)
    return question_data

@app.post("/submit_answer/{questionnaireId}")
async def submit_answer(request: Request, questionnaireId: str, submission: AnswerSubmission, response: Response):
    session_id = request.headers.get('session_id', None)  or request.cookies.get('session_id', None)
    if not session_id:
        # Generate a new session_id if not present
        session_id = str(uuid.uuid4())
        # Set the cookie
        response.set_cookie(key="session_id", value=session_id)

    automaton, session_id = await get_automaton_for_user(session_id, questionnaireId)
    
    question_id = submission.question_id
    answer = submission.user_answer
    logger.debug(f"FastAPI session_id: {session_id} => Question ID: {question_id}, Answer: {answer}")
    next_step, updated_affected_questions, redo_questions, remove_questions = automaton.process(question_id, answer)
    
    logger.debug(f"FastAPI: => current question:{question_id} => next_step: {next_step} => affected_questions: {updated_affected_questions}")
    
    # First, update the user's answer for the current question in the questions_history
    automaton_sessions_collection = mongo_db.automaton_sessions
    update_fields = {
        f"questions_history.{question_id}.update_questions": updated_affected_questions,
        f"questions_history.{question_id}.redo_questions": redo_questions,
        f"questions_history.{question_id}.remove_questions": remove_questions,
        f"questions_history.{question_id}.user_answer": answer
    }
    update_history_query = {"$set": update_fields}
    automaton_sessions_collection.update_one({"_id": session_id}, update_history_query, upsert=True)
    
    if next_step is None:
        logger.info("FastAPI: No further action required")
        return {"message": "No further action required"}
    
    node = automaton.states.get(str(next_step))
    if node is None:
        raise HTTPException(status_code=404, detail="Question not found")

    question = automaton.substitute_placeholders(node['Question'])
    answer_choices = node.get("AnswerChoices")
    logger.debug(f"FastAPI: => Answer choices: {answer_choices}")

    if "APICALL" in answer_choices:
        logger.debug("Should make API CALL")
        api_call = answer_choices.split("APICALL(")[1].split(")")[0]
        api_call = automaton.substitute_placeholders(api_call)
        logger.debug(f"API CALL: {api_call}")
        if "EXTRACT" in answer_choices:
            extract_key = extract_from_function(answer_choices)
            response = make_api_call(api_call)
            #logger.info(f"API Call response: {response}")
            logger.debug(f"submit_answer - Should Extract data: {extract_key}")
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
        "question_id": node.get("ID"),
        "question": question,
        "answer_type": node.get("AnswerType"),
        "answer_choices": parsed_choices,
        "why_we_asked": node.get("WhyWeAsk"),
        #"design": node.get("Design"),
        #"page_number": node.get("Page"),
        "updated_questions": updated_affected_questions, 
        "redo_questions": redo_questions,
        "remove_questions": remove_questions
    }
    next_question_id = node.get("ID")
    # MongoDB: Serialize and save or update the state
    automaton_sessions_collection = mongo_db.automaton_sessions
    automaton.update_questions_path(next_question_id)
    automaton_data = automaton.serialize_data()
    automaton_sessions_collection.update_one({"_id": session_id}, {"$set": automaton_data}, upsert=True)

    update_history_query = {"$set": {f"questions_history.{next_question_id}": question_data}}
    automaton_sessions_collection.update_one({"_id": session_id}, update_history_query, upsert=True)
    
    logger.debug(f"FastAPI:submit_answer => next_step: {next_step}, Next question: {question_data}")
    
    return question_data

#Endpoint to process in case of multiple answers for multiple variables
@app.post("/submit_answers/{questionnaireId}")
async def submit_answers(request: Request, questionnaireId: str, submission: AnswersSubmission, response: Response):
    session_id = request.headers.get('session_id', None)  or request.cookies.get('session_id', None)
    if not session_id:
        # Generate a new session_id if not present
        session_id = str(uuid.uuid4())
        # Set the cookie
        response.set_cookie(key="session_id", value=session_id)

    automaton, session_id = await get_automaton_for_user(session_id, questionnaireId)
    question_id = submission.question_id
    answers = submission.answers
    for answer in answers:
        logger.debug(f"FastAPI session_id: {session_id} => Question ID: {question_id}, Variable:{answer.variable_name} Value: {answer.value}")
        automaton.set_variable_value(answer.variable_name, answer.value)

    # Process the user's answer
    next_step, affected_questions, redo_questions, remove_questions = automaton.process(question_id, answer)

    # Serialize and save the state to Firestore
    # db.collection("automaton_sessions").document(session_id).set(automaton.serialize())
    # MongoDB: Serialize and save or update the state
    automaton_data = automaton.serialize_data()
    #logger.debug(f"FastAPI: => {automaton_data}")
    automaton_sessions_collection = mongo_db.automaton_sessions
    automaton_sessions_collection.update_one({"_id": session_id}, {"$set": automaton_data}, upsert=True)
    #questions_history
    
    if next_step is None:
        logger.debug("FastAPI: No further action required")
        return {"message": "No further action required"}

    node = automaton.states.get(str(next_step))

    if node is None:
        raise HTTPException(status_code=404, detail="Question not found")

    question = automaton.substitute_placeholders(node['Question'])
    answer_choices = node.get("AnswerChoices")
    logger.debug(f"FastAPI: => Answer choices: {answer_choices}")

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
        "question_id": node.get("ID"),
        "question": question,
        "answer_type": node.get("AnswerType"),
        "answer_choices": parsed_choices,
        "page_number": node.get("Page"),
        "why_we_asked": node.get("WhyWeAsk"),
        "design": node.get("Design"),
        #"redo_questions": affected_questions
        "updated_questions": affected_questions, 
        "redo_questions": redo_questions,
        "remove_questions": remove_questions
    }

    logger.debug(f"FastAPI:submit_answer => next_step: {next_step}, Next question: {question_data}")
    return question_data

def get_url_parameters(request: Request):
    """
    Returns the URL parameters as a dictionary.
    For function like GET_URL_PARAMETERS(petname, target,gender)
    """
    query_params = dict(request.query_params)
    return query_params

def make_api_call(url: str):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

def extract_data(json_data, path):
    logger.debug(f"FastAPI: Extract data from JSON: {json_data} => Path: {path}\n\n")
    """
    Extracts data from json_data based on the provided path and returns a list of values or
    dictionaries with specified fields in the path.

    :param json_data: The JSON data from which to extract information.
    :param path: The path to the data to extract, in the format 'key1.key2[*].field' or 'key1.key2[*].(field1,field2)'.
    :return: A list of values or dictionaries with specified fields.
    """
    elements = path.split('.')
    current_data = json_data

    for elem in elements[:-1]:  # Process all elements except the last
        if elem.endswith('[*]'):
            key = elem[:-3]
            if key in current_data and isinstance(current_data[key], list):
                current_data = current_data[key]
            else:
                return []  # Key not found or not a list
        elif elem in current_data:
            current_data = current_data[elem]
        else:
            return []  # Key not found

    last_element = elements[-1]
    if '(' in last_element and last_element.endswith(')'):
        return extracted_from_extract_data(last_element, current_data)
    # For a single field, return a list of values
    choices =  [item.get(last_element) for item in current_data if isinstance(item, dict)]
    logger.debug(f"FastAPI: Extracted choices - simple key: {choices}")
    return '\n'.join(choices)

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



# @app.post("/reset_automaton")
# async def reset_automaton(session_id: str = Header(...)):
#     automaton, session_id = await get_automaton_for_user(session_id)
#     automaton.reset()
#     # Update the reset state in Firestore
#     db.collection("automaton_sessions").document(session_id).set(automaton.serialize())
#     return {"message": "Automaton reset"}


#This is the Flask equivalent part in FastAPI
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
