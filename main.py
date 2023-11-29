#import os
#import sys

#sys.path.insert(0, os.path.dirname(__file__))

#def application(environ, start_response):
#    start_response('200 OK', [('Content-Type', 'text/plain')])
#    message = 'It works!\n'
#    version = 'Python v' + sys.version.split()[0] + '\n'
#    response = '\n'.join([message, version])
#    return [response.encode()]

from flask import Flask
app = Flask(__name__)
application = app # our hosting requires application in passenger_wsgi

from neon_api import fetch_neon_events
import json

@app.route("/")
def hello():
  return "This is Helloo World!\n"

@app.route("/instructor_hours")
def instructor_hours_handler():
  return "Hello the second" # json.dumps(fetch_neon_events())

if __name__ == "__main__":
  app.run()
