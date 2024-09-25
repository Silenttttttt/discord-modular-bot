# {
#     "count": 1302,
#     "next": null,
#     "previous": null,
#     "results": [
#         {
#             "name": "bulbasaur",
#             "url": "https://pokeapi.co/api/v2/pokemon/1/"
#         },
#         {


#use this to get the data from bulbasaur and store it in a json file
import requests
import json

# Define the URL for the PokeAPI
url = "https://pokeapi.co/api/v2/pokemon/1/"

# Make a GET request to the PokeAPI
response = requests.get(url)

# Check if the request was successful

if response.status_code == 200:
    # Parse the JSON data
    data = response.json()

    # Open a JSON file for writing
    with open('bulbasaur_data.json', 'w') as file:
        json.dump(data, file, indent=4)
    print("Data has been written to bulbasaur_data.json")
else:
    print("Failed to retrieve data from the PokeAPI")