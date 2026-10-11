from flask import Flask
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["https://r2k-infotech.vercel.app", "https://rekavo.in", "http://localhost:3000", "https://rekavo-backend.vercel.app"])

# Routes import - tere hi routes
from routes.auth import *
from routes.cart import *
from routes.orders import *
from routes.address import *
from routes.admin import *

@app.route('/')
def home(): return "REKAVO Fixed - Modular - Admin Ready - Welcome Mail Live"

if __name__ == '__main__': app.run()
