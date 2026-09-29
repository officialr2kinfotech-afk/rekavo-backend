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
    cur.execute("CREATE TABLE IF NOT EXISTS otps (email VARCHAR(255) PRIMARY KEY, otp_code VARCHAR(6), expires_at TIMESTAMP);")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            phone VARCHAR(20),
            email VARCHAR(255) UNIQUE,
            password VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            product_name VARCHAR(255),
            amount INTEGER,
            status VARCHAR(50) DEFAULT 'Pending',
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    return "All 3 Tables Created - Users, OTP, Orders - Ab full system ready hai"

#... send-otp, verify-otp, login same rahega bas phone add karna...
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
    resend.Emails.send({"from": "REKAVO <otp@rekavo.in>","to": email,"subject": f"{otp} is your REKAVO OTP","html": f"<h1>{otp}</h1><p>Valid 10 min</p>"})
    return jsonify({"success": True})

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    user_otp = data.get('otp')
    name = data.get('name')
    phone = data.get('phone')
    password = data.get('password')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT otp_code, expires_at FROM otps WHERE email=%s", (email,))
    row = cur.fetchone()
    if not row: return jsonify({"success": False, "message": "OTP not sent"})
    db_otp, expiry = row
    if datetime.now() > expiry: return jsonify({"success": False, "message": "OTP expired"})
    if db_otp == user_otp:
        if name and password:
            cur.execute("INSERT INTO users (name, phone, email, password) VALUES (%s, %s, %s, %s) ON CONFLICT (email) DO UPDATE SET name=%s, phone=%s, password=%s", (name, phone, email, password, name, phone, password))
            conn.commit()
        cur.close(); conn.close()
        return jsonify({"success": True})
    else:
        cur.close(); conn.close()
        return jsonify({"success": False, "message": "Wrong OTP"})

@app.route('/login', methods=['POST'])
def login():
    data=request.get_json()
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT id, name FROM users WHERE email=%s AND password=%s", (data.get('email'), data.get('password')))
    row=cur.fetchone(); cur.close(); conn.close()
    if row: return jsonify({"success": True, "user_id": row[0], "name": row[1]})
    else: return jsonify({"success": False, "message": "Galat password"})

@app.route('/admin-users')
def admin_users():
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT id, name, phone, email, password, created_at FROM users ORDER BY id DESC")
    rows=cur.fetchall(); cur.close(); conn.close()
    html_rows=""
    for r in rows:
        html_rows+=f"<tr><td>#{r[0]}</td><td>{r[1]}</td><td>{r[2] or '-'}</td><td>{r[3]}</td><td><span style='filter:blur(4px)'>{r[4]}</span></td><td>{r[5].strftime('%d %b %Y') if r[5] else ''}</td><td><span style='background:#e6f9ec;color:#00b831;padding:4px 10px;border-radius:15px;'>Active</span></td><td><a href='/admin-user/{r[0]}' style='background:#6e00ff;color:white;padding:6px 12px;border-radius:8px;text-decoration:none;'>View Detail</a></td></tr>"
    return f"<html><head><meta name='viewport' content='width=device-width'><style>body{{font-family:sans-serif;background:#f4f6f9;padding:15px}}.header{{background:linear-gradient(135deg,#6e00ff,#ff00a0);color:white;padding:20px;border-radius:15px}} table{{width:100%;background:white;border-radius:10px;border-collapse:collapse}} th,td{{padding:12px 10px;border-bottom:1px solid #eee;text-align:left;font-size:13px}} th{{color:#888}}</style></head><body><div class='header'><h2>REKAVO Admin Panel - Total Users: {len(rows)}</h2></div><div style='overflow-x:auto; margin-top:15px;'><table><tr><th>ID</th><th>Name</th><th>Mobile</th><th>Email</th><th>Password</th><th>Join Date</th><th>Status</th><th>Action</th></tr>{html_rows or '<tr><td colspan=8 style=text-align:center;padding:30px>No users yet</td></tr>'}</table></div></body></html>"

@app.route('/admin-user/<int:user_id>')
def admin_user_detail(user_id):
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT id, name, phone, email, created_at FROM users WHERE id=%s", (user_id,))
    user=cur.fetchone()
    cur.execute("SELECT id, product_name, amount, status, order_date FROM orders WHERE user_id=%s ORDER BY id DESC", (user_id,))
    orders=cur.fetchall()
    cur.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM orders WHERE user_id=%s", (user_id,))
    count, total = cur.fetchone()
    cur.close(); conn.close()
    order_html="".join([f"<tr><td>#{o[0]}</td><td>{o[1]}</td><td>₹{o[2]}</td><td>{o[3]}</td><td>{o[4].strftime('%d %b')}</td></tr>" for o in orders]) or "<tr><td colspan=5 style=text-align:center>Abhi koi order nahi hai</td></tr>"
    return f"<html><body style='font-family:sans-serif;background:#f4f6f9;padding:20px'><a href='/admin-users'>← Back</a><h2>Customer Detail - {user[1]} (ID: #{user[0]})</h2><p>Mobile: {user[2]} | Email: {user[3]}</p><div style='display:flex;gap:15px;margin:15px 0;'><div style='background:white;padding:15px;border-radius:10px;flex:1'>Total Orders: <b>{count}</b></div><div style='background:white;padding:15px;border-radius:10px;flex:1'>Total Spent: <b>₹{total}</b></div></div><table style='width:100%;background:white;border-radius:10px;border-collapse:collapse'><tr><th>Order ID</th><th>Product</th><th>Amount</th><th>Status</th><th>Date</th></tr>{order_html}</table></body></html>"

@app.route('/my-orders/<int:user_id>')
def my_orders(user_id):
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT product_name, amount, status, order_date FROM orders WHERE user_id=%s ORDER BY id DESC", (user_id,))
    rows=cur.fetchall(); cur.close(); conn.close()
    return jsonify([{"product": r[0], "amount": r[1], "status": r[2], "date": r[3].isoformat()} for r in rows])

@app.route('/')
def home(): return "REKAVO Full System Running"
