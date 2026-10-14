from flask import Flask, request
from flask_cors import CORS
import os
import resend

resend.api_key = os.getenv("RESEND_API_KEY")
print("RESEND KEY LOADED:", bool(os.getenv("RESEND_API_KEY")))

app = Flask(__name__)

# FINAL CORS FIX - Preflight ka error 100% khatam hoga
CORS(app, resources={r"/*": {
    "origins": "*",
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"]
}})

@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    if origin:
        response.headers.set('Access-Control-Allow-Origin', origin)
    else:
        response.headers.set('Access-Control-Allow-Origin', '*')
    response.headers.set('Access-Control-Allow-Headers', 'Content-Type,Authorization,Accept,Origin,X-Requested-With')
    response.headers.set('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    response.headers.set('Access-Control-Allow-Credentials', 'true')
    return response

from routes.auth import *
from routes.cart import *
from routes.orders import *
from routes.admin import *
from routes.address import *

@app.route('/')
def home():
    return "REKAVO Backend - CORS Fixed FINAL"

@app.route('/health')
def health():
    return {"status": "ok"}

if __name__ == '__main__':
    app.run()
