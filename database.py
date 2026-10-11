import os
import psycopg2
from flask import request

DATABASE_URL = os.environ.get('DATABASE_URL')
ADMIN_KEY = os.environ.get('ADMIN_KEY', 'rekavo@123')
ADMIN_EMAILS = os.environ.get('ADMIN_EMAILS', '').lower().split(',')

def get_db():
    return psycopg2.connect(DATABASE_URL)

def is_admin_allowed():
    key = request.args.get('key') or request.args.get('admin_key') or request.headers.get('X-Admin-Key')
    admin_email = (request.args.get('admin_email') or '').lower()
    if key and key == ADMIN_KEY:
        return True
    if admin_email and admin_email in ADMIN_EMAILS:
        return True
    if not ADMIN_EMAILS or ADMIN_EMAILS == ['']:
        return key == ADMIN_KEY
    return False

def mask_mobile(phone):
    if not phone: return "-"
    phone = str(phone).strip()
    if len(phone) < 6: return phone
    return phone[:2] + "XXXX" + phone[-2:]

def mask_password(p):
    if not p: return "-"
    if p.startswith('scrypt:') or p.startswith('pbkdf2:'):
        return p[:22] + "••••••••••••"
    return "●●●●●●HASHED●●●●●●"
