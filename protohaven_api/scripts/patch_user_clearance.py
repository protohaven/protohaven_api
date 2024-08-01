# pylint: skip-file

import sys

import requests

url = "http://localhost:5000/user/clearances"
emails = sys.argv[1]
codes = sys.argv[2]
key = sys.argv[3]

print("PATCH", url, "emails", emails, "codes", codes, "key", key)
r = requests.patch(url, data={"emails": emails, "codes": codes, "api_key": key})
print(r.status_code)
print(r.content)
