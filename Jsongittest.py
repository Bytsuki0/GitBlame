import requests
import json
import configparser

# Load config file with token
config = configparser.ConfigParser()
config.read('config.ini')
username = config['github']['username']
token = config['github']['token']
# Get the list of repositories

headers = {"Authorization": f"token {token}"}

url = f"https://api.github.com/search/issues?q=is:pr+author:{username}+is:merged"
response = requests.get(url, headers=headers)
print("\nPull Requests com merge:")
if response.status_code == 200:
    data = response.json()


print(data)