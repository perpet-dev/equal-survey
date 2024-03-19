from enum import auto
import logging
import pandas as pd
import json
from tokenizer import Tokenizer
from logicparser import Parser
import re

logger = logging.getLogger(__name__)
class Automaton:
    def __init__(self):
        self.states = {}  # states of automaton
        self.variables = {}  # Dictionary for variables like @Price, @Beverage, etc.
        self.arrays = {}  # Arrays like @Pizza.size[]
        self.user_answers = {}  # Separate dictionary for user answers
        #self.pages = {}  # Dictionary for pages
        self.goto = "1"  # The next step to go to"
        self.next_steps = {}  # Initialize the next_steps dictionary
        self.name = "Automaton"
        
    def serialized_states(self):
        serialized_ = {
            "states": self.states,
            "name": self.name
            # "variables": self.variables,
            # "next_steps": self.next_steps,
            # "arrays": self.arrays,
            # "user_answers": self.user_answers,
            # #"pages": self.pages,
            # "goto": self.goto
        }
        
        return serialized_
    
    def serialize_data(self):
        serialized_ = {
            "name": self.name,
            "variables": self.variables,
            "next_steps": self.next_steps,
            "arrays": self.arrays,
            "user_answers": self.user_answers,
            #"pages": self.pages,
            "goto": self.goto
        }

        return serialized_
    
    def deserialize_states(self, data):
        self.states = data.get("states", {})
        self.name = data.get("name", "Automaton")
        # automaton.variables = data.get("variables", {})
        # automaton.arrays = data.get("arrays", {})
        # automaton.next_steps = data.get("next_steps", {})
        # automaton.user_answers = data.get("user_answers", {})
        # #automaton.pages = data.get("pages", {})
        self.goto = data.get("goto", "1")
    
    def deserialize_data(self, data):
        self.name = data.get("name", "Automaton")
        self.variables = data.get("variables", {})
        self.arrays = data.get("arrays", {})
        self.next_steps = data.get("next_steps", {})
        self.user_answers = data.get("user_answers", {})
        #automaton.pages = data.get("pages", {})
        self.goto = data.get("goto", "1")
    
    def reset(self):
        """
        Resets the automaton to its initial state.
        """
        self.variables = {}  # Dictionary for variables like @Price, @Beverage, etc.
        self.arrays = {}  # Arrays like @Pizza.size[]
        self.user_answers = {}  # Separate dictionary for user answers
        self.goto = "1"  # The next step to go to"
        
    # def get_questions_for_page(self, page_number):
    #     """
    #     Retrieves the questions for a given page number.

    #     Args:
    #         page_number (int): The page number.

    #     Returns:
    #         list: The list of questions for the page.
    #     """
    #     return self.pages.get(page_number)
    
    def get_variable_value(self, variable_name):
        return self.variables.get(variable_name)
    
    def set_variable_value(self, variable_name, value):
        self.variables[variable_name] = value
    
    def store_user_answer(self, question_id, answer):
        """
        Stores the user's answer keyed by the question ID.

        Args:
            question_id (str): The ID of the question.
            answer (str): The user's answer to the question.
        """
        self.user_answers[question_id] = answer

    def get_user_answer(self, question_id):
        """
        Retrieves the user's answer for a given question ID.

        Args:
            question_id (str): The ID of the question.

        Returns:
            str: The user's answer, or None if not found.
        """
        return self.user_answers.get(question_id)

    def get_user_choice(self, question_id):
        # Retrieve the full response for the question using the question_id
        full_response = self.get_user_answer(question_id)
        logger.debug(f"full_response: {full_response}")
        # For example, you might have stored the user's choices in a dictionary like so:
        # self.variables = {'2 -> What's your name?': 'Ivan', '3 -> Hi @2, What pizza size do you prefer?': 'Medium - $15'}
        # You would extract 'Medium' from 'Medium - $15' and return it.

        # Split the response on ' - ' and return the choice part
        # Split the response on ': ' and return the choice part
        if full_response is not None:
            choice = full_response.split('-')[0]
            choice = full_response.split(':')[0]
            logger.debug(f"get_user_choice:{choice.strip()}")
            return choice.strip()

        # Return None if the response is not found
        return None

    def execute_action(self, action):
        if action['type'] == 'selected_option':
            # Extract the option variable and the question ID
            option_variable = action['option']
            question_id = action['question_id']

            # Find the answer to the specified question
            answer_key = f"{question_id} ->"
            answer = next((value for key, value in self.variables.items() if key.startswith(answer_key)), None)

            # Assign the answer to the specified option variable
            if answer is not None:
                self.variables[option_variable] = answer
            else:
                logger.debug(f"Answer for question {question_id} not found.")

        if action['type'] == 'add':
            logger.debug(f"action:{action}")
            variable = action['target_variable']
            if variable not in self.variables:
                self.variables[variable] = 0
            self.variables[variable] += action['value']
        elif action['type'] == 'multiply':
            self.variables[action['variable']] *= action['value']
        elif action['type'] == 'set':
            # Implement logic for 'set' action
            variable_name = action['variable']
            new_value = action['value']
            # Set the new value to the specified variable
            self.variables[variable_name] = new_value

        if action['type'] == 'goto':
            logger.debug(f"Executing goto statement: {action['step']}")  # Debugging
            self.goto = str(action['step'])

    def execute_goto(self, step):
        logger.debug(f"Executing goto statement: {step}")  # Debugging
        self.goto = str(step)

    def execute_set(self, statement, node_id):
        logger.debug(f"Executing set statement: {statement}")  # Debugging
        step_key = str(node_id) #str(self.goto)

        variable_name = statement['variable']
        logger.debug(f"variable_name: {variable_name}")  # Debugging
        logger.debug(f"user_answers: {self.user_answers}")  # Debugging
        value_to_set = ""
        if step_key in self.user_answers:
            value_to_set = self.user_answers[step_key]

        logger.debug(f"Original value_to_set: {value_to_set}")
        original_value_to_set = value_to_set
        items = value_to_set.split(',')
        names = [item.split(':')[0].strip() for item in items]
        value_to_set = names
        if len(names) == 1:
            value_to_set = names[0]
        if variable_name.endswith('[]'):
            # Trim '[]' from the variable name for array handling
            array_name = variable_name[:-2]
            # Initialize the array if it doesn't exist
            if array_name not in self.arrays:
                self.arrays[array_name] = []
            # Append the value to the array
            logger.debug(f"Set array {variable_name} = {value_to_set}")  # Debugging
            self.arrays[array_name] = value_to_set
            # Also set the individual variable (non-array)
            self.variables[array_name] = original_value_to_set
        else:
            # For non-array variables, just set the value
            logger.debug(f"Set non-array {variable_name} = {value_to_set}")  # Debugging
            self.variables[variable_name] = value_to_set
        logger.debug(f"Set {variable_name} = {value_to_set}")  # Debugging
        logger.debug(f"variables: {self.variables}")
        logger.debug(f"arrays: {self.arrays}")

    def run(self, parse_info):
        node_id = parse_info['ID']
        logger.debug(f"run node: {node_id} with parsed_statements: {parse_info['parsed_statements']}")
        parsed_statements = parse_info['parsed_statements']

        for statement in parsed_statements:
            logger.debug(f"statement: {statement}")
            if statement['type'] == 'if':
                # Extract and Evaluate the condition
                logger.debug(f"statement['condition']: {statement['condition']}")
                condition = statement['condition']
                condition_met = False
                
                if 'operator' in condition:  # For comparison conditions
                    left_value = self.evaluate_condition_part(condition['left'])
                    right_value = self.evaluate_condition_part(condition['right'])
                    logger.debug(f"condition['operator']: {condition['operator']}")
                    logger.debug(f"left_value: {left_value}; right_value: {right_value}")
                    if condition['operator'] == 'equals':
                        condition_met = (left_value == right_value)
                        logger.debug(f"left_value: {left_value}; right_value: {right_value} => condition_met: {condition_met}")
                    elif condition['operator'] == 'notequals':
                        condition_met = (left_value != right_value)
                        logger.debug(f"left_value: {left_value}; right_value: {right_value} => condition_met: {condition_met}")

                elif 'value' in condition:  # For direct literal check
                    # Assuming you have a method or way to get the user response or the value to compare with
                    user_response = self.get_user_answer(self.goto) #self.get_user_response()
                    literal_value = condition['value'].lstrip('#')  # Remove the leading '#' from the literal
                    condition_met = (user_response == literal_value)

                # Execute 'then' or 'else' part based on the condition
                if condition_met:
                    logger.debug(f"Condition met -> statement['then']: {statement['then']}")
                    for action in statement['then']:
                        self.execute_action(action)
                elif 'else' in statement and statement['else'] is not None:  # Corrected line
                    logger.debug(f"Condition not met -> statement['else']: {statement['else']}")
                    for action in statement['else']:
                        self.execute_action(action)
            
            elif 'else' in statement and statement['else'] is not None:  # Corrected line
                logger.debug(f"Condition not met -> statement['else']: {statement['else']}")
                for action in statement['else']:
                    self.execute_action(action)
            if statement['type'] == 'action':
                logger.debug(f"Action: {statement}")
                self.execute_action(statement)
            if statement['type'] == 'set':  # Handle the 'set' statement type
                self.execute_set(statement, node_id)
            if statement['type'] == 'goto':
                self.goto = str(statement['step'])
                break

    
    def evaluate_condition_part(self, part):
    # Implement logic to evaluate the part of the condition (variable or literal value)
    # For example, if part is a variable, retrieve its value; if it's a literal, use it as is
    # This is a placeholder; adapt it to your specific implementation needs
        if part.startswith('@'):
            # Assuming variables start with '@', retrieve their values
            return self.get_variable_value(part)
        else:
            # For literals, use the value directly
            return part
    
    def substitute_placeholders(self, question):
        # Regex pattern to find both {@variable} and @node patterns
        pattern = r'\{@\w+\}|@\w+'
        placeholders = re.findall(pattern, question)

        for placeholder in placeholders:
            # Normalize the key by removing curly braces and '@'
            normalized_key = placeholder.replace('{', '').replace('}', '').lstrip('@')

            # Check and replace placeholders based on the key
            found = False
            for variable_key, variable_value in self.variables.items():
                # Handle '->' format and direct '@key' format
                if variable_key.startswith(normalized_key + " ->") or variable_key.startswith("@" + normalized_key):
                    # Ensure the variable_value is a string
                    variable_value_str = str(variable_value)
                    question = question.replace(placeholder, variable_value_str)
                    found = True
                    logger.info(f" Found substitute_placeholder for {placeholder} = {variable_value_str}")
                    break

            if not found:
                logger.debug(f"Placeholder '{placeholder}' not found in variables")

        return question
    
    def display_and_get_choice(self, answer_choices, multiple_selection=False):
        choices = [choice.strip() for choice in answer_choices.split("\n")]
        for idx, choice in enumerate(choices, 1):
            print(f"{idx}. {choice}")
        if multiple_selection:
            print("Enter your choices separated by comma (e.g., 1,3):")
        else:
            print("Enter your choice (number):")

        while True:
            user_input = input()
            selected = user_input.split(',' if multiple_selection else None)
            try:
                selected_choices = [choices[int(choice.strip()) - 1] for choice in selected]
                if all(choice in choices for choice in selected_choices):
                    return ', '.join(selected_choices)
                else:
                    logger.debug("Invalid choice(s). Please select number(s) from the list.")
            except (ValueError, IndexError):
                logger.debug("Please enter a valid number.")
                
    def normalize_string(self, input_string):
        # Replace newlines with spaces
        #no_newlines = input_string.replace('\n', ' ')
        
        # Split the string by comma and strip spaces from each part
        parts = [part.strip() for part in input_string.split(',')]
        
        # Join the parts back together with ', '
        normalized = '\n'.join(parts)
        
        return normalized
    
    # Example usage
    def load_from_excel(self, file_path):
        """
        Loads the automaton configuration from an Excel file.

        Args:
            file_path (str): The path to the Excel file.
        """
        logger.info(f"Loading automaton from Excel file: {file_path}")
        df = pd.read_excel(file_path)
        name = file_path.split('/')[-1].split('.')[0]
        self.name = name
        # Initialize an empty automaton dictionary
        states = {}

        # Iterate over the rows of the DataFrame and populate the automaton
        for _, row in df.iterrows():
            # Check if the ID is NaN. If yes, stop the loop.
            if pd.isna(row['ID']):
                break
            #logger.debug(f"row: {row}")  # Debugging statement
            #logger.debug(f"row ID: {row['ID']}")  # Debugging statement
            node_id = str(row['ID']).strip()
            logic = row['Logic']
            if pd.isna(row['Logic']):
                logic = ""
            answerChoices = row['AnswerChoices']
            if pd.isna(row['AnswerChoices']):
                answerChoices = ""
            
            #answerChoices = self.normalize_string(answerChoices)
            
            # try:
            #     pageid = int(float(str(row['Page']).strip()))
            # except ValueError:
            #     # Handle the error, e.g., by setting a default value or logging an error message
            #     pageid = 1  # Replace with an appropriate default value
            
            if 'WhyWeAsk' in df.columns:
                # Check if the value in 'WhyWeAsk' is NaN, and handle accordingly
                WhyWeAsk = row['WhyWeAsk'] if not pd.isna(row['WhyWeAsk']) else ""
            else:
                # Handle the case where 'WhyWeAsk' column does not exist
                WhyWeAsk = ""  # or any default value you want to assign
            
            states[node_id] = {
                "ID": node_id,
                "Question": str(row['Question']).strip(),
                "AnswerType": str(row['AnswerType']).strip(),
                "AnswerChoices": str(answerChoices).strip(),
                "Logic": logic.strip(),
                "WhyWeAsk": WhyWeAsk.strip()
                #"Page": pageid
            }
            # nodeofpage = self.pages.get(pageid, [])
            # nodeofpage.append({
            #     "ID": node_id,
            #     "Question": str(row['Question']).strip(),
            #     "AnswerType": str(row['AnswerType']).strip(),
            #     "AnswerChoices": str(answerChoices).strip(),
            #     "Logic": logic.strip(),
            #     "WhyWeAsk": WhyWeAsk.strip(), 
            #     "Page": pageid
            # })
            # self.pages[pageid] = nodeofpage
            # logger.debug(f"pages: {self.pages}")
            
        self.states = states
        #self.dataframe = df
        
        return self
    
    def initVariables(self):
        # Initialize variables and arrays from the 'Logic' column
        array_pattern = re.compile(r'SET \((@[A-Za-z0-9_.]+)\[\]\)')
        # Updated regex to exclude the '=' from the variable name
        variable_pattern = re.compile(r'SET \((@[\w.]+)=(\d*\.?\d+)\)')

        # Initialize dictionaries outside of the loop
        self.variables = {}
        self.arrays = {}

        for logic in self.dataframe['Logic']:
            # Find all variable assignments and array initializations
            if logic is None or not isinstance(logic, str):
                continue

            logic_lines = logic.split('\n')
            for line in logic_lines:
                if 'SET' not in line:
                    continue

                # Arrays
                arrays = array_pattern.findall(line)
                for array in arrays:
                    self.arrays[array] = []

                # Variables
                variables_found = variable_pattern.findall(line)
                for var_name, var_value in variables_found:
                    try:
                        if '.' in var_value:
                            self.variables[var_name] = float(var_value)
                        else:
                            self.variables[var_name] = int(var_value)
                    except ValueError:
                        logger.debug(f"Invalid value for variable {var_name}: {var_value}")

        logger.debug("Variables initialized:", self.variables)
        logger.debug("Arrays initialized:", self.arrays)


    def print_automaton(self):
        """
        Prints the automaton in a readable format.
        Args:
            automaton (dict): The automaton dictionary.
        """
        logger.debug(json.dumps(self.states, indent=2))

    def to_graph(self):
        self.nodes = []
        self.edges = []

        for node_id, node in self.states.items():
            # Add node to the nodes list
            label = node_id + " -> " + node.get("Question", "")
            self.nodes.append({
                "data": {"id": node_id, "label": label}
            })

            # Add edges based on GOTO logic
            logic = node.get("Logic", "")
            for line in logic.splitlines():
                if "GOTO" in line:
                    target_node = line.split(":")[-1].strip()
                    target_node = target_node.strip(")")
                    self.edges.append({
                        "data": {
                            "source": node_id,
                            "target": target_node
                        }
                    })

        cytoscape_json = {
            "nodes": self.nodes,
            "edges": self.edges
        }
        return cytoscape_json

    def processnextstep(self, question_id):
        node = self.states.get(question_id)
        if node is None:
            logger.debug(f"No node found for ID: {question_id}. Ending execution.")
            return None

        logger.debug(f"node: {node}")
        question = self.substitute_placeholders(node['Question'])
        logger.debug(f"Question: {question}")
        # Process the logic of the node line by line
        logic_lines = node['Logic'].splitlines()
            
        for line in logic_lines:
            if line.strip() == "":
                continue
            tokenizer = Tokenizer()
            parser = Parser(tokenizer)
            parsed_statements = parser.parse(line)
            parse_info = {
                "parsed_statements": parsed_statements,
                "ID": question_id
            }
            self.run(parse_info)
            logger.debug(f"parse_info: {parse_info}")
            # Check for conditional statements and determine the next step
            for statement in parsed_statements:
                if statement['type'] == 'conditional':
                    logger.debug(f"statement['condition']: {statement['condition']}; type: {type(statement['condition'])}")
                    #condition = statement['condition']['value'].strip('#')
                    condition = statement['condition']

                    # Check if condition is a string
                    if isinstance(condition, str):
                        condition = condition.strip('#')

                    # Check if condition is a dictionary and extract the string value
                    elif isinstance(condition, dict) and 'value' in condition:
                        condition = condition['value'].strip('#')

                    if (condition == answer and statement.get('then')):
                        for action in statement['then']:
                            if action['type'] == 'goto':
                                next_step = action['step']
                                logger.debug(f"next_step: {next_step}")
                                break
                    elif statement.get('else'):
                        for action in statement['else']:
                            if action['type'] == 'goto':
                                next_step = action['step']
                                logger.debug(f"next_step: {next_step}")
                                break
            
        logger.debug(f"variables: {self.variables}")
        logger.debug(f"arrays: {self.arrays}")
        logger.debug(f"user_answers: {self.user_answers}")
        
        print(f"logic_lines: {logic_lines}")
        # Retrieve the next step from a suitable place, like self.next_steps
        next_step = self.next_steps.get(question_id, None)
        if next_step:
            logger.debug(f"Using previously determined next step: {next_step}")
            return next_step
        else:
            logger.debug(f"No previously determined next step found. Continuing...")

        
    def process(self, question_id, answer):
        logger.debug(f"Processing question_id: {question_id}, answer: {answer}")
        """
        Processes the user's answer to a given question and determines the next step.
        """
        # Check if this question has been answered before
        if question_id in self.user_answers:
            logger.debug(f"Updating answer for question_id: {question_id}")
            # This is an update, handle accordingly
            # Store the user's answer
            self.variables[str(question_id) + " -> " + self.states[question_id]['Question']] = answer
            self.store_user_answer(question_id, answer)
            logger.debug(f"user_answers: {self.user_answers}")
            
            # Process the current question based on the provided question_id
            node = self.states.get(question_id)
            if node is None:
                logger.debug(f"No node found for ID: {question_id}. Ending execution.")
                return None

            logger.debug(f"node: {node}")
            question = self.substitute_placeholders(node['Question'])
            logger.debug(f"Question: {question}")
            # Process the logic of the node line by line
            logic_lines = node['Logic'].splitlines()
                
            for line in logic_lines:
                if line.strip() == "":
                    continue
                tokenizer = Tokenizer()
                parser = Parser(tokenizer)
                parsed_statements = parser.parse(line)
                parse_info = {
                    "parsed_statements": parsed_statements,
                    "ID": question_id
                }
                self.run(parse_info)
                logger.debug(f"parse_info: {parse_info}")
                # Check for conditional statements and determine the next step
                for statement in parsed_statements:
                    if statement['type'] == 'conditional':
                        logger.debug(f"statement['condition']: {statement['condition']}; type: {type(statement['condition'])}")
                        #condition = statement['condition']['value'].strip('#')
                        condition = statement['condition']

                        # Check if condition is a string
                        if isinstance(condition, str):
                            condition = condition.strip('#')

                        # Check if condition is a dictionary and extract the string value
                        elif isinstance(condition, dict) and 'value' in condition:
                            condition = condition['value'].strip('#')

                        if (condition == answer and statement.get('then')):
                            for action in statement['then']:
                                if action['type'] == 'goto':
                                    next_step = action['step']
                                    logger.debug(f"next_step: {next_step}")
                                    break
                        elif statement.get('else'):
                            for action in statement['else']:
                                if action['type'] == 'goto':
                                    next_step = action['step']
                                    logger.debug(f"next_step: {next_step}")
                                    break
                
            logger.debug(f"variables: {self.variables}")
            logger.debug(f"arrays: {self.arrays}")
            logger.debug(f"user_answers: {self.user_answers}")
            
            print(f"logic_lines: {logic_lines}")
            
            # Retrieve the next step from a suitable place, like self.next_steps
            next_step = self.next_steps.get(question_id, None)
            if next_step:
                logger.debug(f"Using previously determined next step: {next_step}")
                return next_step
            else:
                logger.debug(f"No previously determined next step found. Continuing...")
                

        # Store the user's answer
        self.variables[str(question_id) + " -> " + self.states[question_id]['Question']] = answer
        self.store_user_answer(question_id, answer)
        logger.debug(f"user_answers: {self.user_answers}")

        # Process the current question based on the provided question_id
        node = self.states.get(question_id)
        if node is None:
            logger.debug(f"No node found for ID: {question_id}. Ending execution.")
            return None

        logger.debug(f"node: {node}")
        question = self.substitute_placeholders(node['Question'])
        logger.debug(f"Question: {question}")

        next_step = None

        # Process the logic of the node line by line
        logic_lines = node['Logic'].splitlines()
            
        for line in logic_lines:
            if line.strip() == "":
                continue
            tokenizer = Tokenizer()
            parser = Parser(tokenizer)
            parsed_statements = parser.parse(line)
            parse_info = {
                "parsed_statements": parsed_statements,
                "ID": question_id
            }
            logger.debug(f"parse_info: {parse_info}")
            self.run(parse_info)
            
            # Check for conditional statements and determine the next step
            for statement in parsed_statements:
                if statement['type'] == 'conditional':
                    logger.debug(f"statement['condition']: {statement['condition']}; type: {type(statement['condition'])}")
                    #condition = statement['condition']['value'].strip('#')
                    condition = statement['condition']

                    # Check if condition is a string
                    if isinstance(condition, str):
                        condition = condition.strip('#')

                    # Check if condition is a dictionary and extract the string value
                    elif isinstance(condition, dict) and 'value' in condition:
                        condition = condition['value'].strip('#')

                    if (condition == answer and statement.get('then')):
                        for action in statement['then']:
                            if action['type'] == 'goto':
                                next_step = action['step']
                                logger.debug(f"next_step: {next_step}")
                                break
                    elif 'elif' in statement:
                        for elif_clause in statement['elif']:
                            elif_condition = elif_clause['condition']

                            # Check if elif_condition is a string
                            if isinstance(elif_condition, str):
                                elif_condition = elif_condition.strip('#')

                            # Check if elif_condition is a dictionary and extract the string value
                            elif isinstance(elif_condition, dict) and 'value' in elif_condition:
                                elif_condition = elif_condition['value'].strip('#')

                            # Evaluate elif_condition
                            if elif_condition == answer:
                                for action in elif_clause['then']:
                                    if action['type'] == 'goto':
                                        next_step = action['step']
                                        logger.debug(f"next_step in elif: {next_step}")
                                        break
                                if next_step:
                                    break  # Break out of the loop if the condition is met and action is taken
                            
                    elif statement.get('else'):
                        for action in statement['else']:
                            if action['type'] == 'goto':
                                next_step = action['step']
                                logger.debug(f"next_step: {next_step}")
                                break

                if next_step:
                    logger.debug(f"next_step: {next_step}")
                    self.next_steps[question_id] = next_step
                    break  # Exit the loop once the next step is determined
            
        logger.debug(f"variables: {self.variables}")
        logger.debug(f"arrays: {self.arrays}")
        logger.debug(f"user_answers: {self.user_answers}")
        print(f"logic_lines: {logic_lines}")
        if all('GOTO' not in line for line in logic_lines):
            self.goto = str(int(self.goto) + 1)
        
        next_step = self.goto
        # Return the next step or None if no further action is required
        logger.debug(f"Next step: {next_step}")
        self.next_steps[question_id] = next_step
        return next_step
    
# # Example usage
# automaton = Automaton()
# automaton.load_from_excel('Back_Questionnaire.xlsx')
# # # Print the automaton
# logger.debug("Automaton states:")
# automaton.print_automaton()
# logger.debug(automaton.serialize())

# # graph = automaton.to_graph()
# # logger.debug(json.dumps(graph, indent=4))
# # # Execute the automaton
# # logger.debug(f"variables:{automaton.variables}")
# # logger.debug(f"arrays:{automaton.arrays}")
# automaton.execute()



