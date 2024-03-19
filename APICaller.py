import requests
import itertools

#https://api.equal.pet/sign-service/v1/breeds?type=cat&limit=500
#https://api.equal.pet/sign-service/v1/breeds?type=dog&limit=500

#jusoSearchApiEndpoint = https://business.juso.go.kr/addrlink/addrLinkApi.do
#jusoSearchApiKey = "U01TX0FVVEgyMDIzMTAwNjEwMDQyODExNDE0ODA="
# 펫 GPT 주소
#   static let petGptEndpoint = "https://app.customgpt.ai/projects/11628/ask-me-anything?shareable_slug=9bec0e9c6be34bc53f4e3d84e82eb9ad&embed=1"
# https://" + self.domain
# api.equal.pet

def APICALL(url, parameters):
    try:
        response = requests.get(url, params=parameters)
        response.raise_for_status()
        #print(f"response.json(): \n{response.json()}")
        return response.json()
    
    except requests.HTTPError as error:
        print(f"HTTP error occurred: {error}")
    except Exception as e:
        print(f"An error occurred: {e}")
    return []

def extract_data(json_data, path):
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
        else:
            if elem in current_data:
                current_data = current_data[elem]
            else:
                return []  # Key not found

    last_element = elements[-1]
    if '(' in last_element and last_element.endswith(')'):
        fields = last_element.replace(' ', '').strip('()').split(',')
        return [{field: item.get(field) for field in fields} for item in current_data if isinstance(item, dict)]
    else:
        # For a single field, return a list of values
        return [item.get(last_element) for item in current_data if isinstance(item, dict)]

# # Example usage
print("Breeds list for cat:")
result = APICALL("https://api.equal.pet/sign-service/v1/breeds", {"type": "cat", "limit": 500})
result = extract_data(result, 'data.content[*].name')
print(result)

print("Breeds list for dog:")
result = APICALL("https://api.equal.pet/sign-service/v1/breeds", {"type": "dog", "limit": 500})
result = extract_data(result, 'data.content[*].name')
print(result)

print("Allergy list:")
result = APICALL("https://api.equal.pet/sign-service/v1/allergy", {"limit": 500})
result = extract_data(result, 'data.content[*].name')
print(result)

print("Main Disease Categories list:")
result = APICALL("https://api.equal.pet/sign-service/v1/disease", {"is_main": True, "limit": 500})
result = extract_data(result, 'data.content[*].(id,name)')
print(result)


print("Sub Disease list:")
result = APICALL("https://api.equal.pet/sign-service/v1/disease", {"main_ctgr_id": 11, "limit": 500})
result = extract_data(result, 'data.content[*].name')
print(result)