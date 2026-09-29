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
    return psycopg2.connect(DATABASE_URL)

@app.route('/create-table')
def create_table():
    conn = get_db()
    cur = conn.cursor()
    # Base tables
    cur.execute("CREATE TABLE IF NOT EXISTS otps (email VARCHAR(255) PRIMARY KEY, otp_code VARCHAR(6), expires_at TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name VARCHAR(255), email VARCHAR(255) UNIQUE, password VARCHAR(255), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, user_id INTEGER, product_name VARCHAR(255), amount INTEGER, status VARCHAR(50) DEFAULT 'Pending', order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")

    # Fix - purani table me phone column jod dega agar nahi hai toh
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);")

    conn.commit()
    cur.close()
    conn.close()
    return "FIXED - Phone column added, ab error nahi ayega"

@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get('email')
    otp = str(random.randint(100000, 999999))
    expiry = datetime.now() + timedelta(minutes=10)
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO otps (email, otp_code, expires_at) VALUES (%s, %s, %s) ON CONFLICT (email) DO UPDATE SET otp_code=%s, expires_at=%s", (email, otp, expiry, otp, expiry))
    conn.commit(); cur.close(); conn.close()
    resend.Emails.send({"from": "REKAVO <otp@rekavo.in>","to": email,"subject": f"{otp} is your REKAVO OTP","html": f"<h1>{otp}</h1><p>Valid 10 min</p>"})
    return jsonify({"success": True})

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email, user_otp = data.get('email'), data.get('otp')
    name, phone, password = data.get('name'), data.get('phone'), data.get('password')
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT otp_code, expires_at FROM otps WHERE email=%s", (email,))
    row = cur.fetchone()
    if not row: cur.close(); conn.close(); return jsonify({"success": False, "message": "OTP not sent"})
    db_otp, expiry = row
    if datetime.now() > expiry: cur.close(); conn.close(); return jsonify({"success": False, "message": "OTP expired"})
    if db_otp == user_otp:
        if name and password:
            cur.execute("INSERT INTO users (name, phone, email, password) VALUES (%s, %s, %s, %s) ON CONFLICT (email) DO UPDATE SET name=%s, phone=%s, password=%s", (name, phone, email, password, name, phone, password))
            conn.commit()
        cur.close(); conn.close()
        return jsonify({"success": True})
    else:
        cur.close(); conn.close()
        return jsonify({"success": False, "message": "Wrong OTP"})

@app.route('/admin-users')
def admin_users():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT id, name, phone, email, password, created_at FROM users ORDER BY id DESC")
        rows = cur.fetchall(); cur.close(); conn.close()
        html_rows = ""
        for r in rows:
            html_rows += f"<tr><td>#{r[0]}</td><td>{r[1]}</td><td>{r[2] or '-'}</td><td>{r[3]}</td><td><span style='filter:blur(4px)'>{r[4]}</span></td><td>{r[5].strftime('%d %b') if r[5] else ''}</td><td><a href='/admin-user/{r[0]}' style='background:#6e00ff;color:white;padding:6px 12px;border-radius:8px;text-decoration:none;'>View Detail</a></td></tr>"
        return f"<html><head><meta name='viewport' content='width=device-width'><style>body{{font-family:sans-serif;background:#f4f6f9;padding:15px}}.header{{background:linear-gradient(135deg,#6e00ff,#ff00a0);color:white;padding:20px;border-radius:15px}} table{{width:100%;background:white;border-radius:10px;border-collapse:collapse}} th,td{{padding:12px 10px;border-bottom:1px solid #eee;text-align:left;font-size:12px}}</style></head><body><div class='header'><h2>REKAVO Admin - Total: {len(rows)}</h2></div><div style='overflow-x:auto;margin-top:15px;'><table><tr><th>ID</th><th>Name</th><th>Mobile</th><th>Email</th><th>Pass</th><th>Date</th><th>Action</th></tr>{html_rows or '<tr><td colspan=7 style=text-align:center;padding:30px>No users</td></tr>'}</table></div></body></html>"
    except Exception as e:
        return f"Error: {str(e)} - /create-table khol ke pehle FIX karo"
@app.route('/delete-user/<int:user_id>')
def delete_user(user_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM orders WHERE user_id=%s", (user_id,))
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit(); cur.close(); conn.close()
    return f"User #{user_id} Deleted. <a href='/admin-users'>Back to Admin</a>"
@app.route('/admin-user/<int:user_id>')
def admin_user_detail(user_id):
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT id, name, phone, email FROM users WHERE id=%s", (user_id,))
    user=cur.fetchone()
    cur.execute("SELECT id, product_name, amount, status FROM orders WHERE user_id=%s", (user_id,))
    orders=cur.fetchall()
    cur.close(); conn.close()
    return f"<html><body style='font-family:sans-serif;padding:20px'><a href='/admin-users'>Back</a><h2>{user[1]} (#{user[0]})</h2><p>{user[3]} | {user[2]}</p><h3>Orders: {len(orders)}</h3></body></html>"

@app.route('/')
def home(): return "REKAVO Fixed"
