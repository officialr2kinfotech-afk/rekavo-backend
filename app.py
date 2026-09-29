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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS otps (
            email VARCHAR(255) PRIMARY KEY,
            otp_code VARCHAR(6),
            expires_at TIMESTAMP
        );
    """)
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
    return "Both Tables Created - OTP + USERS"

@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get('email')
    otp = str(random.randint(100000, 999999))
    expiry = datetime.now() + timedelta(minutes=10)
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
        "html": f"<div style='font-family:sans-serif;'><h2>REKAVO</h2><h1>{otp}</h1><p>Valid for 10 min</p></div>"
    })
    return jsonify({"success": True})

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    user_otp = data.get('otp')
    name = data.get('name')
    password = data.get('password')
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
        return jsonify({"success": False, "message": "OTP expired"})
    if db_otp == user_otp:
        if name and password:
            cur.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s) ON CONFLICT (email) DO UPDATE SET name=%s, password=%s", (email, name, password, name, password))
            conn.commit()
        cur.close(); conn.close()
        return jsonify({"success": True})
    else:
        cur.close(); conn.close()
        return jsonify({"success": False, "message": "Wrong OTP"})

@app.route('/admin-users')
def admin_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, password, created_at FROM users ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    total_users = len(rows)
    html_rows = ""
    for r in rows:
        first_letter = r[1][0].upper() if r[1] else 'U'
        date_str = r[4].strftime('%d %b, %Y') if r[4] else ''
        html_rows += f"<tr><td>#{r[0]}</td><td><div style='display:flex;align-items:center;gap:10px;'><div style='width:35px;height:35px;background:#6e00ff;color:white;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:600;'>{first_letter}</div><div><b>{r[1]}</b></div></div></td><td>{r[2]}</td><td><span style='filter:blur(4px);cursor:pointer;' onmouseover=\"this.style.filter='blur(0px)'\" onmouseout=\"this.style.filter='blur(4px)'\">{r[3]}</span></td><td>{date_str}</td><td><span style='background:#e6f9ec;color:#00b831;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:600;'>Active</span></td></tr>"

    return f"""
    <html><head><meta name='viewport' content='width=device-width, initial-scale=1.0'><title>REKAVO Admin</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap');
        body{{font-family:'Poppins',sans-serif;background:#f4f6f9;margin:0;padding:20px;}}
       .header{{background:linear-gradient(135deg,#6e00ff,#ff00a0);color:white;padding:25px;border-radius:20px;display:flex;justify-content:space-between;align-items:center;}}
       .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin:20px 0;}}
       .card{{background:white;padding:20px;border-radius:15px;box-shadow:0 5px 15px rgba(0,0,0,0.05);}}
       .card h2{{margin:5px 0;font-size:28px;}}
       .table-box{{background:white;border-radius:15px;padding:20px;box-shadow:0 5px 15px rgba(0,0,0,0.05);overflow-x:auto;}}
        table{{width:100%;border-collapse:collapse;}} th{{text-align:left;color:#888;font-size:13px;padding:15px 10px;border-bottom:2px solid #f0f0f0;}} td{{padding:15px 10px;border-bottom:1px solid #f0f0f0;font-size:14px;}}
    </style></head>
    <body>
        <div class='header'><div><h1 style='margin:0;'>REKAVO Admin Panel</h1><p style='margin:0;opacity:0.9;'>Welcome back, Boss 🔥</p></div><div style='font-size:14px;'>rekavo.in • Live</div></div>
        <div class='stats'>
            <div class='card'><small>TOTAL USERS</small><h2>{total_users}</h2><span style='color:green;'>▲ Real Hosting</span></div>
            <div class='card'><small>TOTAL ORDERS</small><h2>0</h2><span>Coming Soon</span></div>
            <div class='card'><small>REVENUE</small><h2>₹0</h2><span>Next Update</span></div>
        </div>
        <div class='table-box'>
            <h3>All Customers - ID Wise</h3>
            <table><tr><th>ID</th><th>CUSTOMER</th><th>EMAIL</th><th>PASSWORD</th><th>JOINED</th><th>STATUS</th></tr>
                {html_rows if html_rows else "<tr><td colspan=6 style='text-align:center;padding:40px;'>Abhi koi user nahi hai... pehle register ka intezar hai</td></tr>"}
            </table>
        </div>
    </body></html>
    """

@app.route('/')
def home():
    return "REKAVO Full Backend Running"
