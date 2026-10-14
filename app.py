from flask import Flask
from flask_cors import CORS

app = Flask(__name__)

# Ye line sabse important hai - ye www.rekavo.in ko allow karegi
CORS(app, resources={r"/*": {
    "origins": ["https://rekavo.in", "https://www.rekavo.in", "https://rekavo-backend.vercel.app", "https://r2k-infotech.vercel.app", "http://localhost:3000", "http://localhost:5500"],
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
    return "REKAVO Backend - CORS Fixed"

@app.route('/health')
def health():
    return {"status": "ok"}

if __name__ == '__main__':
    app.run()
