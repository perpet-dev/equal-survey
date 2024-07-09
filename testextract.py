import json
import re

def extract_data(json_data, custom_path):
    # If the JSON data is a list and not a dictionary at the top level, we wrap it in a dictionary
    if isinstance(json_data, list) and len(json_data) == 1:
        json_data = json_data[0]  # Use the first dictionary in the list
    
    # Use regular expressions to parse the custom path
    match = re.match(r"(.*)\[\*\]\.\((.*)\)", custom_path)
    if not match:
        return "Invalid custom path format"
    
    base_path, fields = match.groups()
    field_list = fields.split(", ")
    
    # Navigate to the correct level in the JSON data
    content = json_data
    print(content)
    for key in base_path.split('.'):
        if isinstance(content, dict) and key in content:
            print(key, content[key])
            content = content[key]
        else:
            return "Path not found or not a dictionary at some level"
    
    # Ensure the content is a list for iteration
    if not isinstance(content, list):
        return "Expected list at path, got something else"
    
    # Extract the specified fields from each item in the list
    result = []
    for item in content:
        values = [str(item.get(field, 'Field not found')) for field in field_list]
        result.append(":".join(values))
    
    return "\n".join(result)


# def extract_data(json_data, custom_path):
#     # Regular expression to parse the custom path
#     match = re.match(r"(.*)\[\*\]\.\((.*)\)", custom_path)
#     if not match:
#         return "Invalid custom path format"

#     base_path, fields = match.groups()
#     field_list = fields.split(", ")

#     # Navigate to the correct level in the JSON data
#     content = json_data
#     for key in base_path.split('.'):
#         if key in content:
#             content = content[key]
#         else:
#             return "Path not found or not a dictionary at some level"

#     # Ensure the content is a list for extraction
#     if not isinstance(content, list):
#         return "Expected list at path, got something else"

#     # Extract the specified fields from each item in the list
#     result = []
#     for item in content:
#         extracted_values = [str(item.get(field, 'Field not found')) for field in field_list]
#         result.append(":".join(extracted_values))

#     return "\n".join(result)

# # Example JSON input
# json_data = {
#     "success": True,
#     "code": 200,
#     "msg": "Success",
#     "data": {
#         "content": [
#             {"id": 9, "name": "간담도계"},
#             {"id": 377, "name": "내분비계"},
#             {"id": 13, "name": "뇌신경"},
#             # More items...
#         ]
#     }
# }

#Sample JSON data based on your input
# json_data =  [
#     {'success': True, 'code': 200, 'msg': 'Success', 'data': 
#         {'content': [{'id': 40, 'type': 'dog', 'name': '믹스견', 'sort_order': 0, 'insert_date': '2023-05-26T19:49:28', 'update_date': '2023-11-08T15:46:35', 'insert_user': 11, 'update_user': None, '_candidate': False, '_expired': False, '_main': True},
#                      {'id': 1, 'type': 'dog', 'name': '골든 리트리버', 'sort_order': 1, 'insert_date': '2023-05-26T19:49:27', 'update_date': '2023-09-22T23:55:45', 'insert_user': 11, 'update_user': None, '_candidate': False, '_expired': False, '_main': True}, 
#                      {'id': 2, 'type': 'dog', 'name': '그레이 하운드', 'sort_order': 1, 'insert_date': '2023-05-26T19:49:27', 'update_date': '2023-09-22T23:52:59', 'insert_user': 11, 'update_user': None, '_candidate': False, '_expired': False, '_main': False}, 
#                      {'id': 3, 'type': 'dog', 'name': '그레이트 데인', 'sort_order': 1, 'insert_date': '2023-05-26T19:49:27', 'update_date': '2023-09-22T23:52:59', 'insert_user': 11, 'update_user': None, '_candidate': False, '_expired': False, '_main': False},
#                     ], 
#          'pageable': {'sort': {'empty': True, 'sorted': False, 'unsorted': True}, 'offset': 0, 'pageNumber': 0, 'pageSize': 500, 'paged': True, 'unpaged': False}, 
#          'totalElements': 215, 'totalPages': 1, 'last': True, 'size': 500, 'number': 0, 
#          'sort': {'empty': True, 'sorted': False, 'unsorted': True}, 'numberOfElements': 215, 'first': True, 'empty': False}}
#     ]


json_data = {
    "success": True,
    "code": 200,
    "msg": "Success",
    "data": {
        "content": [
            {"id": 9, "name": "간담도계"},
            {"id": 377, "name": "내분비계"},
            {"id": 13, "name": "뇌신경"},
            {"id": 3, "name": "당뇨"},
            {"id": 2, "name": "비뇨생식기계"},
            {"id": 10, "name": "소화기계"},
            {"id": 8, "name": "신장"},
            {"id": 11, "name": "심혈관계"},
            {"id": 5, "name": "악성종양"},
            {"id": 17, "name": "안과"},
            {"id": 16, "name": "인지장애"},
            {"id": 14, "name": "정형외과"},
            {"id": 6, "name": "치과"},
            {"id": 1, "name": "피부"},
            {"id": 15, "name": "행동학적 질환"},
            {"id": 7, "name": "호흡기계"}
        ],
        "pageable": {
            "sort": {"empty": True, "sorted": False, "unsorted": True},
            "offset": 0,
            "pageNumber": 0,
            "pageSize": 500,
            "paged": True,
            "unpaged": False
        },
        "totalElements": 16,
        "totalPages": 1,
        "last": True,
        "size": 500,
        "number": 0,
        "sort": {"empty": True, "sorted": False, "unsorted": True},
        "numberOfElements": 16,
        "first": True,
        "empty": False
    }
}

# Custom path to extract 'id' and 'name'
custom_path = 'data.content[*].(id, name)'

# Using the function to extract data
extracted_data = extract_data(json_data, custom_path)
print(extracted_data)
# # Example usage
# custom_path = 'data.content[*].(id, name)'
# print(extract_data(json_data, custom_path))

