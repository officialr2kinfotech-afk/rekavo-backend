from flask import Flask
from flask_cors import CORS
import os
import resend

resend.api_key = os.getenv("RESEND_API_KEY")
print("RESEND KEY LOADED:", bool(os.getenv("RESEND_API_KEY")))

app = Flask(__name__)

CORS(app, resources={r"/*": {
    "origins": [
        "https://rekavo.in",
        "https://www.rekavo.in",
        "https://seller.rekavo.in",
        "https://www.seller.rekavo.in",
        "https://rekavo-backend.vercel.app",
        "https://r2k-infotech.vercel.app",
        "http://localhost:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500"
    ],
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization", "Accept", "Origin"],
    "supports_credentials": True
}})

from routes.auth import *
from routes.cart import *
from routes.orders import *
from routes.admin import *
from routes.address import *

@app.route('/')
def home():
    return "REKAVO Backend - CORS Fixed & Seller Added"

@app.route('/health')
def health():
    return {"status": "ok"}

if __name__ == '__main__':
    app.run()
