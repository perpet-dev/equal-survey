import asyncio
import logging
import traceback
import uuid
from fastapi import WebSocket, WebSocketDisconnect
from openai import OpenAI

client = OpenAI()
from openai import OpenAI
import json

from sympy import true

client = OpenAI()
system_with_image = "You are 'PetGPT', a friendly and enthusiastic GPT that specializes in analyzing images of dogs and cats. \
    Upon receiving an image, you identifies the pet's breed, age and weight. PetGPT provides detailed care tips, \
    including dietary recommendations, exercise needs, and general wellness advice, emphasizing suitable vitamins and supplements. \
    PetGPT, as an AI tool, is exceptionally equipped to assist pet owners with a wide range of questions and challenges. \
    It can provide immediate, accurate, and tailored advice on various aspects of pet care, including health, behavior, \
    nutrition, grooming, exercise, and general well-being. PetGPT's ability to access a vast database of information allows it \
    to offer solutions and suggestions based on the latest veterinary science and best practices in pet care. \
    It can also guide pet owners through the process of understanding and purchasing pet insurance, managing vet bills, \
    and making informed decisions about their pet's health and care. \
    Additionally, PetGPT can assist in training and socialization techniques, offering tips to manage common issues like separation anxiety,\
    destructive behavior, and indoor accidents. Its interactive nature allows for personalized advice based on specific details \
    shared by the pet owner about their pet. Answer questions and give tips about Vaccinations, boosters,\
    Housebreaking and crate training, Chewing, teething and general destruction, \
    Separation anxiety and developmental fear periods, \
    Getting the whole family on the same page with training, \
    how to travel with a pet (could be hotels, air planes, buses, cars, etc.). \
    Answer in the same language as the question."
system = "You are 'PetGPT', a friendly and enthusiastic GPT that specializes in healthcare for dogs and cats. \
    PetGPT provides detailed care tips, \
    including dietary recommendations, exercise needs, and general wellness advice, emphasizing suitable vitamins and supplements. \
    PetGPT, as an AI tool, is exceptionally equipped to assist pet owners with a wide range of questions and challenges. \
    It can provide immediate, accurate, and tailored advice on various aspects of pet care, including health, behavior, \
    nutrition, grooming, exercise, and general well-being. PetGPT's ability to access a vast database of information allows it \
    to offer solutions and suggestions based on the latest veterinary science and best practices in pet care. \
    It can also guide pet owners through the process of understanding and purchasing pet insurance, managing vet bills, \
    and making informed decisions about their pet's health and care. \
    Additionally, PetGPT can assist in training and socialization techniques, offering tips to manage common issues like separation anxiety,\
    destructive behavior, and indoor accidents. Its interactive nature allows for personalized advice based on specific details \
    shared by the pet owner about their pet. Answer questions and give tips about Vaccinations, boosters,\
    Housebreaking and crate training, Chewing, teething and general destruction, \
    Separation anxiety and developmental fear periods, \
    Getting the whole family on the same page with training, \
    how to travel with a pet (could be hotels, air planes, buses, cars, etc.). \
    Answer in the same language as the question."
    
logger = logging.getLogger(__name__)

# Assuming API key and custom model/server configurations are set elsewhere
# openai.api_key = "your-api-key"
# openai.api_base = "your-api-base-url"

# Example of filtering out unsupported fields from messages before sending to OpenAI
def prepare_messages_for_openai(messages):
    # Define the allowed fields in a message
    allowed_fields = {'role', 'content'}

    # Filter each message to only include allowed fields
    filtered_messages = []
    for message in messages:
        filtered_message = {key: value for key, value in message.items() if key in allowed_fields}
        filtered_messages.append(filtered_message)

    return filtered_messages


async def handle_text_messages(websocket: WebSocket, model, conversation):
    system_message = {"role": "system", "content": system}
    conversation_with_system = [system_message] + conversation
    #message_stream_id = str(uuid.uuid4())
    conversation = prepare_messages_for_openai(conversation_with_system)
    
    # Synchronously call the OpenAI API without await
    response = client.chat.completions.create(
        model = model,
        messages=conversation,
        temperature=0,
        max_tokens=1024,
        stream=True
    )
    message_stream_id = str(uuid.uuid4())
    # iterate through the stream of events
    try:
        for chunk in response:
            chunk_message = chunk.choices[0].delta.content  # extract the message
            if  chunk_message is not None:
                chunk_message_with_id = {"id": message_stream_id, "content":chunk_message}
                #send to socket
                logger.info(f"Generation WebSocket to ChatGPT {chunk_message_with_id}")
                await websocket.send_json(chunk_message_with_id)

        # Send a finished signal with the same ID
        await websocket.send_json({"id": message_stream_id, "finished": True})
    except Exception as e:
        logger.error(f"Error processing text message: {e}", exc_info=True)
        await websocket.send_json({"error": "Error processing your request"})

async def handle_image_messages(websocket: WebSocket, model, messages):
    try:
        response = client.chat.completions.create(
            model = model,#"gpt-4-vision-preview"{}
            messages=[
                    {"role": "system", "content": system},
                    {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What’s in this image?"},
                        {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg",
                        },
                        },
                    ],
                    }
                ],
                max_tokens=4096,
        )

        print(response.choices[0])

        choice = response.choices[0]
        message = choice.message

        # Manually create the response dictionary
        answer = {
            "finish_reason": choice.finish_reason,
            "index": choice.index,
            "logprobs": choice.logprobs,
            "content": message.content,
            "role": message.role,
            "function_call": message.function_call,
            "tool_calls": message.tool_calls,
            "finished": True  # Add 'finished': true to the response
        }

        logger.info(answer)
        await websocket.send_json(answer)
    except Exception as e:
        logger.error(f"Error processing text message: {e}", exc_info=True)
        await websocket.send_json({"error": "Error processing your request"})

async def generation_websocket_endpoint_chatgpt(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected")

    try:
        while True:
            data = await websocket.receive_json()
            logger.debug(f"Received data: {data}")
            
            # Extracting the user message from the received data
            messages = data.get("messages", [])
            #conversation = data.get("messages")
            if not messages:
                logger.error("No messages provided")
                await websocket.send_json({"error": "No messages provided"})
                continue
            # Determine if the input contains an image
            logger.info(f"got messages:{messages}")
            # Check the content type and handle accordingly
            first_message_content = messages[0].get("content")
            if isinstance(first_message_content, str):
                # This is a text-only message
                contains_image = False
            elif isinstance(first_message_content, list):
                # This is expected to be a list of items (e.g., text and/or images)
                contains_image = any(item.get("type") == "image_url" for item in first_message_content if isinstance(item, dict))
            else:
                logger.error("Unexpected content type")
                await websocket.send_json({"error": "Unexpected content type"})
                continue

            # Choose the model based on whether an image is included
            model = "gpt-4-vision-preview" if contains_image else "gpt-4-0125-preview"
            
            try: 
                if contains_image:
                    await handle_image_messages(websocket, model, messages)
                else:
                    await handle_text_messages(websocket, model, messages)
                
                # choice = response.choices[0]
                # message = choice.message

                # # Manually create the response dictionary
                # answer = {
                #     "finish_reason": choice.finish_reason,
                #     "index": choice.index,
                #     "logprobs": choice.logprobs,
                #     "content": message.content,
                #     "role": message.role,
                #     "function_call": message.function_call,
                #     "tool_calls": message.tool_calls,
                #     "finished": True  # Add 'finished': true to the response
                # }

                # logger.info(answer)
                # await websocket.send_json(answer)
                
            except Exception as e:
                logger.error(f"Error while calling OpenAI API: {e}", exc_info=True)
                await websocket.send_json({"error": "Failed to process the request."})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        await websocket.send_json({"error": "An unexpected error occurred while processing your request."})
