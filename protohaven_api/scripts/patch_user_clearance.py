# pylint: skip-file

import base64
import sys

import requests

url = "http://localhost:5000/user/clearances"
emails = sys.argv[1]
codes = sys.argv[2]
key = sys.argv[3]
encoded_key = base64.b64encode(key.encode()).decode()

print("PATCH", url, "emails", emails, "codes", codes, "key", encoded_key)
r = requests.patch(url, data={"emails": emails, "codes": codes, "api_key": encoded_key})
print(r.status_code)
print(r.content)
