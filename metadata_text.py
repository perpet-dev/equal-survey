import json

# Load the JSON data from a file
with open('breed_Metadata.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

# Create a map from breed_id to metadata_text
breedid_map = {
    item['breed_id']: item['metadata_text'] 
    for item in data
    if item['metadata_text'].endswith('_breed')
}


with open('allergy_Metadata.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

# Create a map from breed_id to metadata_text
allergyid_map = {
    item['allergy_id']: item['metadata_text'] 
    for item in data
    if item['metadata_text'].startswith('allergy')
}

with open('disease_Metadata.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

# Create a map from disease_id to metadata_text, filtering for metadata_text that starts with "disease"
diseaseid_map = {
    item['disease_id']: item['metadata_text']
    for item in data
    if item['metadata_text'].startswith('disease')
}
# Now you can retrieve metadata_text by breed_id
# For example, to get the metadata_text for breed_id 1:
metadata_text = breedid_map.get(1)  # 'dog_breed:golden_retriever'

print("breedid_map:")
print(breedid_map)
print("breedid_map for (1)")
print(metadata_text)


# For example, to get the metadata_text for breed_id 1:
metadata_text = allergyid_map.get(1)  # 'dog_breed:golden_retriever'

print("allergyid_map:")
print(allergyid_map)
print("allergyid_map for (1)")
print(metadata_text)


# For example, to get the metadata_text for breed_id 1:
metadata_text = diseaseid_map.get(10)  # 'dog_breed:golden_retriever'

print("diseaseid_map:")
print(diseaseid_map)
print("diseaseid_map for (10)")
print(metadata_text)