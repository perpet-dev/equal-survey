import os
import openai
import base64
#https://github.com/Coding-Crashkurse/Multimodal-RAG-With-OpenAI/blob/main/Semi_structured_and_multi_modal_RAG%20(1).ipynb
#pip install -U openai==1.1.0 langchain==0.0.333 langchain-experimental==0.0.39 --upgrade
#from https://community.openai.com/t/chat-completion-request-vision-model-return-500s-when-system-added/493946/6


from langchain.chains import ConversationChain
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI
from langchain.schema.messages import HumanMessage, AIMessage

# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

chain_gpt_4_vision = ChatOpenAI(model="gpt-4-vision-preview", max_tokens=1024, openai_api_key=os.environ["OPENAI_API_KEY"])
system = "You are 'PetGPT', a friendly and enthusiastic GPT that specializes in analyzing images of dogs and cats. \
    Upon receiving an image, you identifies the pet's breed, age and weight. PetGPT provides detailed care tips, \
    including dietary recommendations, exercise needs, and general wellness advice, emphasizing suitable vitamins and supplements. \
    PetGPT, as an AI tool, is exceptionally equipped to assist pet owners with a wide range of questions and challenges. \
    It can provide immediate, accurate, and tailored advice on various aspects of pet care, including health, behavior, \
    nutrition, grooming, exercise, and general well-being. The AI's ability to access a vast database of information allows it \
    to offer solutions and suggestions based on the latest veterinary science and best practices in pet care. \
    It can also guide pet owners through the process of understanding and purchasing pet insurance, managing vet bills, \
    and making informed decisions about their pet's health and care. \
    Additionally, the AI can assist in training and socialization techniques, offering tips to manage common issues like separation anxiety,\
    destructive behavior, and indoor accidents. Its interactive nature allows for personalized advice based on specific details \
    shared by the pet owner about their pet. Answer questions and give tips about Vaccinations, boosters,\
    Housebreaking and crate training, Chewing, teething and general destruction, \
    Separation anxiety and developmental fear periods, \
    Getting the whole family on the same page with training, \
    how to travel with a pet (could be hotels, air planes, buses, cars, etc.). \
    Answer in the same language as the question."

def summarize_image(userquestion, encoded_image):
    prompt = [
        AIMessage(content=f"{system}"),
        HumanMessage(content=[
            {"type": "text", "text": f"{userquestion}"},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded_image}"
                },
            },
        ])
    ]
    response = chain_gpt_4_vision.invoke(prompt)
    return response.content

question = "이 개 품종?"
# Path to your image
image_path = "australian-terrier-best-dogs-for-first-time-owners-1627585661.jpg"
# Getting the base64 string
encoded_image = encode_image(image_path)
response = summarize_image(question, encoded_image)
print(response)