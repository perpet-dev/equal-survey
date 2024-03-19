import re
#from logicparser import ParserError

import logging
logger = logging.getLogger(__name__)
class Tokenizer:
    def __init__(self):
        self.tokens = []
        self.position = 0
        # Define the token patterns
        token_patterns = {
            'GOTO': r'GOTO\s*:\s*(\d+)',  # Match the 'GOTO' keyword followed by a colon and a step number
            'NUMBER': r'(\d+(\.\d+)?)',
            'IF': r'IF',
            'LITERAL': r'#\w+',
            'EQUALS': r'==',  # Equality comparison
            'NOTEQUALS': r'!=',  # NotEquality comparison
            'THEN': r'THEN',
            'ELSE': r'ELSE',
            'ELIF': r'ELIF',  # Add ELIF pattern         
            'ASSIGNMENT': r'=',  # Assignment
            'ADD': r'\(ADD\)',
            'MULTIPLY': r'\(MULTIPLY\)',
            'TO': r'\(TO\)',
            'BY': r'\(BY\)',
            'OPEN_PAREN': r'\(',
            'CLOSE_PAREN': r'\)',
            'SET': r'SET',
            'ARRAY': r'@\w+(\.\w+)?\[\]',  # Pattern for array variable like @Pizza.size][] with an optional period
            'VARIABLE': r'@\w+(\.\w+)?',
            'WHITESPACE': r'\s+',
            'NEWLINE': r'\n',
            'VALUE': r'\w+'
        }
        self.TOKEN_PATTERNS = {k: re.compile(v) for k, v in token_patterns.items()}

    def tokenize(self, input_text):
        self.tokens = []
        self.position = 0
        
        while self.position < len(input_text):
            match = None
            for token_type, pattern in self.TOKEN_PATTERNS.items():
                regex = re.compile(pattern)
                match = regex.match(input_text, self.position)
                if match:
                    #print(f"Matched token_type:{token_type} pattern:{pattern} match: {match}")  # Debugging statement
                    if token_type not in ['WHITESPACE', 'NEWLINE']:
                        if token_type == 'GOTO':
                            # Extract step number for GOTO token
                            step_number = int(match.group(1))
                            self.tokens.append({'type': 'GOTO', 'value': step_number})
                            self.osition = match.end()  # Consume the GOTO token by updating the position
                        elif token_type == 'EQUALS':
                            self.tokens.append({'type': 'EQUALS', 'value': '=='})
                        elif token_type == 'LITERAL':
                            value = match.group(0)  # The literal match, like '#Small'
                            self.tokens.append({'type': 'LITERAL', 'value': value})
                        elif token_type == 'NUMBER':
                            # Convert to float and then to int if no decimal part, else keep as float
                            value = float(match.group(1))
                            if value.is_integer():
                                value = int(value)
                            self.tokens.append({'type': 'NUMBER', 'value': value})
                        elif token_type == 'ARRAY':
                            array_name = match.group(0)  # The array variable including []
                            self.tokens.append({'type': 'ARRAY', 'value': array_name})
                        else:
                            value = match.group(0)
                            #print(f"{token_type}, value: {value}")  # Debugging statement
                            self.tokens.append({'type': token_type, 'value': value})
                    self.position = match.end()
                    break
            if not match:
                context_start = max(self.position - 10, 0)
                context_end = min(self.position + 10, len(input_text))
                context = input_text[context_start:context_end]
                illegal_char = input_text[self.position]
                logger.error(f'Illegal character context: "{context}" at position {self.position}')
                logger.error(f'Illegal character: "{illegal_char}"')
                raise SyntaxError(f'Illegal character at position {self.position}')
        #print(f"Debug => Tokens: {tokens}")
        return self.tokens

    def get_next_token(self):
        if self.position < len(self.tokens):
            token = self.tokens[self.position]
            self.position += 1
            return token
        else:
            return None

    def peek_next_token(self):
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        else:
            return None
    
    def expect_token(self, expected_type):
        token = self.get_next_token()
        if not token or token['type'] != expected_type:
            raise Exception(f"Expected token type {expected_type}, but got {token['type'] if token else 'None'}")
        return token


#Test
# tokenizer = Tokenizer()
# logic_statement = "SET (@Dessert.quantity) \nTHEN (MULTIPLY) (@Dessert.quantity) (BY) (@Dessert.price) (ADD) (TO) (@Price) \n GOTO: 13"
# # Tokenize the logic statement
# tokens = tokenizer.tokenize(logic_statement)
# # Print the tokens for inspection
# for token in tokens:
#     print(token)

#Test
# tokenizer = Tokenizer()
# # logic_statement = "IF (@petType==고양이) THEN (GOTO: 5) ELSE (GOTO: 6)"
# # logic_statement = "IF(#강아지) THEN SET(@petType=dog) ELSE SET(@petType=cat)\nGOTO 2"
# # logic_statement = "IF (#강아지) THEN (SET(@petType=dog)) ELSE (SET(@petType=cat))"
# logic_statement = "IF (#Y) THEN (GOTO: 19) ELIF (@type==dog) THEN (GOTO: 21) ELSE (GOTO: 24)"
# # # Tokenize the logic statement
# tokens = tokenizer.tokenize(logic_statement)
# # Print the tokens for inspection
# for token in tokens:
#     print(token)
    
    