import jwt
import os
from functools import wraps
from flask import request, jsonify, g

SECRET_KEY = os.getenv("JWT_SECRET", "rekavo_super_secret_123")

def create_token(user_data):
    return jwt.encode(user_data, SECRET_KEY, algorithm="HS256")

def init_central_security(app):
    @app.before_request
    def check_auth():
        path = request.path
        public = ['/auth', '/products', '/health', '/upload-url', '/']
        if any(p in path for p in public):
            return None
        private = ['/address', '/cart', '/orders', '/wishlist']
        if any(p in path for p in private):
            token = request.cookies.get('rekavo_token')
            if not token:
                return jsonify({"success": False, "message": "Login required"}), 401
            try:
                g.user = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            except:
                return jsonify({"success": False, "message": "Invalid session"}), 401
