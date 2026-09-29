from flask import Flask, request, jsonify
from flask_cors import CORS
import os, random
import psycopg2
import resend
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

resend.api_key = os.environ.get('RESEND_API_KEY')
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

@app.route('/create-table')
def create_table():
    conn = get_db()
    cur = conn.cursor()
    # 1. OTP table (temporary)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS otps (
            email VARCHAR(255) PRIMARY KEY,
            otp_code VARCHAR(6),
            expires_at TIMESTAMP
        );
    """)
    # 2. USERS table (permanent - 100 saal tak)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            email VARCHAR(255) UNIQUE,
            password VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    return "Both Tables Created - OTP + USERS - Ab perfect hai"

@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get('email')
    otp = str(random.randint(100000, 999999))
    expiry = datetime.now() + timedelta(minutes=10) # 10 min kar diya

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO otps (email, otp_code, expires_at) VALUES (%s, %s, %s) ON CONFLICT (email) DO UPDATE SET otp_code=%s, expires_at=%s", (email, otp, expiry, otp, expiry))
    conn.commit()
    cur.close()
    conn.close()

    resend.Emails.send({
        "from": "REKAVO <otp@rekavo.in>",
        "to": email,
        "subject": f"{otp} is your REKAVO OTP",
        "html": f"<div style='font-family: sans-serif;'><h2>REKAVO Verification</h2><h1 style='letter-spacing:5px;'>{otp}</h1><p>Valid for 10 minutes. Don't share with anyone.</p></div>"
    })
    return jsonify({"success": True})

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    user_otp = data.get('otp')
    name = data.get('name') # register se aayega
    password = data.get('password') # register se aayega

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT otp_code, expires_at FROM otps WHERE email=%s", (email,))
    row = cur.fetchone()

    if not row:
        cur.close(); conn.close()
        return jsonify({"success": False, "message": "OTP not sent"})

    db_otp, expiry = row
    if datetime.now() > expiry:
        cur.close(); conn.close()
        return jsonify({"success": False, "message": "OTP expired, 10 min ho gaya"})

    if db_otp == user_otp:
        # OTP sahi hai to user ko permanent save karo
        if name and password:
            cur.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s) ON CONFLICT (email) DO UPDATE SET name=%s, password=%s", (email, name, password, name, password))
            conn.commit()
        cur.close(); conn.close()
        return jsonify({"success": True})
    else:
        cur.close(); conn.close()
        return jsonify({"success": False, "message": "Wrong OTP"})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name FROM users WHERE email=%s AND password=%s", (email, password))
    row = cur.fetchone()
    cur.close(); conn.close()
    if row:
        return jsonify({"success": True, "name": row[0]})
    else:
        return jsonify({"success": False, "message": "Email ya Password galat hai"})

@app.route('/admin-users')
def admin_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, password, created_at FROM users ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    # simple HTML me dikhayega taaki tu asani se dekh paye
    html = "<h1>REKAVO - All Users</h1><table border=1 cellpadding=10><tr><th>ID</th><th>Name</th><th>Email</th><th>Password</th><th>Date</th></tr>"
    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td></tr>"
    html += "</table>"
    return html

@app.route('/')
def home():
    return "REKAVO Full Backend - OTP + Login + Admin Running"
