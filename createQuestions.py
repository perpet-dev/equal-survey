import os
import csv
from pathlib import Path
import openai
from openai import OpenAI
# Set your OpenAI API key securely
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = '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' #OPENAI_API_KEY

'''
GPT-3.5 Turbo models are capable and cost-effective.

gpt-3.5-turbo-0125 is the flagship model of this family, supports a 16K context window and is optimized for dialog.

Model	Input	Output
gpt-3.5-turbo-0125	$0.50 / 1M tokens	$1.50 / 1M tokens
gpt-3.5-turbo-instruct	$1.50 / 1M tokens	$2.00 / 1M tokens
===

GPT4 => 
Model	Input	Output
gpt-4	$30.00 / 1M tokens	$60.00 / 1M tokens
gpt-4-32k	$60.00 / 1M tokens	$120.00 / 1M tokens

GPT-4 Turbo => 
gpt-4-0125-preview	$10.00 / 1M tokens	$30.00 / 1M tokens
gpt-4-1106-preview	$10.00 / 1M tokens	$30.00 / 1M tokens
gpt-4-1106-vision-preview	$10.00 / 1M tokens	$30.00 / 1M tokens

'''

def extract_questions(content_to_analyze, relative_path, csv_writer):
    system_question = '''
    You are a specialist in content written by Veterinarians. The content provided in a translated content in Korean. 
    You have to rewrite the content in Korean as is has been written by Korean  Veterinarians. 
    Please keep similar length as original content, don't try to summarize.
    '''
    # '''
    #     You are compiling a FAQ section for a pet care website and need to extract potential frequently asked questions from content written by veterinarians. 
    #     The content covers a wide range of topics important to pet owners, including but not limited to:
    #     Healthcare for pets of all ages (babies, young, and old-aged pets)
    #     Accessories such as strollers, clothes, and toys
    #     Food recommendations and dietary advice
    #     Behavior problems, anxiety, aggressivity and training
    #     Activities, sports, and games for pets
    #     Medicines and treatments for various diseases
    #     The goal is to identify questions that provide practical, actionable information and advice for pet owners. 
    #     Please extract questions that cover these topics comprehensively, ensuring that they're relevant and useful for an FAQ section.  
    #     Aim for clarity and directness in each question to make them as helpful as possible.
    #     Just output as many as possible questions. Answer in Korean Language.
    # '''
    try:
        client = OpenAI(
            organization='org-oMDD9ptBReP4GSSW5lMD1wv6',
        )
        completion = client.chat.completions.create(
            #model= "gpt-3.5-turbo-0125", # "gpt-4-1106-preview", #"gpt-4", 
            model= "gpt-4-32k",
            messages=[
                {"role": "system", "content": system_question},
                {"role": "user", "content": f"Here is the content: {content_to_analyze}"},
            ]
        )
        questions = completion.choices[0].message.content
        
        # Log the file being processed and its extracted questions
        print(f"Processing file: {relative_path}")
        print("Extracted Questions:")
        print(questions)

        # Write only the questions to the CSV file
        csv_writer.writerow([relative_path, questions])

    except Exception as e:
        print(f"Error processing {relative_path}: {str(e)}")

def process_directory(directory_path, base_path, output_csv_path):
    filenumber = 0
    base_path = Path(base_path)
    with open(output_csv_path, mode='w', newline='', encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['File Path', 'Questions'])
        filename = 'text_translated_utf8.txt' #'text_utf8.txt'
        for path in Path(directory_path).rglob(filename):
            relative_path = path.relative_to(base_path).parent
            with open(path, 'r', encoding='utf-8') as file:
                try:
                    content = file.read()
                    extract_questions(content, str(relative_path), csv_writer)
                    filenumber=filenumber+1
                    print(filenumber)
                except Exception as e:
                    print(f"Error reading {path}: {str(e)}")

# Set your directory path and output CSV file path
directory_path = '/Users/ivanpro/Library/CloudStorage/OneDrive-PERPET/PETMD/'
base_path = '/Users/ivanpro/Library/CloudStorage/OneDrive-PERPET/PETMD/'
output_csv_path = 'output_questions.csv'

# Process the directory
process_directory(directory_path, base_path, output_csv_path)
