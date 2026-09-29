from flask import Flask, request, jsonify
from flask_cors import CORS
import os, random
import psycopg2
import resend
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# Vercel me Environment Variable se aayega
resend.api_key = os.environ.get('RESEND_API_KEY')
DATABASE_URL = os.environ.get('DATABASE_URL') # Neon ka URL

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# Table banane ke liye ek baar chalega
@app.route('/create-table')
def create_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS otps (
            email VARCHAR(255) PRIMARY KEY,
            otp_code VARCHAR(6),
            expires_at TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    return "Table Created - Ab ye 100 saal tak rahega"

@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get('email')
    otp = str(random.randint(100000, 999999))
    expiry = datetime.now() + timedelta(minutes=5)

    conn = get_db()
    cur = conn.cursor()
    # Neon me save - 100 saal tak safe
    cur.execute("INSERT INTO otps (email, otp_code, expires_at) VALUES (%s, %s, %s) ON CONFLICT (email) DO UPDATE SET otp_code=%s, expires_at=%s", (email, otp, expiry, otp, expiry))
    conn.commit()
    cur.close()
    conn.close()

    # Inbox me bhejne ke liye
    resend.Emails.send({
        "from": "REKAVO <otp@rekavo.in>",
        "to": email,
        "subject": f"{otp} is your REKAVO OTP",
        "html": f"<h1>{otp}</h1><p>Your REKAVO OTP. Valid for 5 minutes.</p>"
    })
    return jsonify({"success": True})

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    user_otp = data.get('otp')

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT otp_code, expires_at FROM otps WHERE email=%s", (email,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"success": False, "message": "OTP not sent"})
    
    db_otp, expiry = row
    if datetime.now() > expiry:
        return jsonify({"success": False, "message": "OTP expired"})

    if db_otp == user_otp:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Wrong OTP"})

@app.route('/')
def home():
    return "REKAVO Perfect OTP Backend Running on Vercel + Neon"
