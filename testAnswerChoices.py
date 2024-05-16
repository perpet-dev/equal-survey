import re
from automaton import Automaton
from typing import Optional, List, Dict, Tuple

def parse_answer_choices(answer_choices: str, automaton: Automaton) -> List[Dict]:
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
        match = pattern.match(option.strip())
        if match:
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

    conditional_match = conditional_pattern.search(option_str)
    if conditional_match:
        var_name, value, true_img, false_img = conditional_match.groups()
        actual_value = automaton.get_variable_value(f"@{var_name}")
        return true_img if actual_value == value else false_img
    else:
        unconditional_match = unconditional_pattern.search(option_str)
        return unconditional_match.group('img') if unconditional_match else None

def test():
    answer_choices = "thin - 저체중 - 많이 말랐어요 - IF(@petType==cat) THEN IMG(bsc_cat01) ELSE IMG(bsc_dog01)\n" \
                    "light - 약간 저체중 마른 편이에요 - IF(@petType==cat) THEN IMG(bsc_cat02) ELSE IMG(bsc_dog02)\n" \
                    "normal - 정상 - 딱 보기 좋아요 - IF(@petType==cat) THEN IMG(bsc_cat03) ELSE IMG(bsc_dog3)\n" \
                    "chubby - 준비만 - 조금 통통해요 - IF(@petType==cat) THEN IMG(bsc_cat04) ELSE IMG(bsc_dog04)\n" \
                    "heavy - 고도비만 - 뚱뚱해요 - IF(@petType==cat) THEN IMG(bsc_cat05) ELSE IMG(bsc_dog05)"
    automaton = Automaton()
    automaton.load_from_excel('Back_Questionnaire.xlsx')
    automaton.set_variable_value('@petType', 'cat')
    parsed_choices = parse_answer_choices(answer_choices, automaton)
    
    print(parsed_choices)
    
test()