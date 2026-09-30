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
    cur.execute("CREATE TABLE IF NOT EXISTS otps (email VARCHAR(255) PRIMARY KEY, otp_code VARCHAR(6), expires_at TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name VARCHAR(255), email VARCHAR(255) UNIQUE, password VARCHAR(255), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, user_id INTEGER, product_name VARCHAR(255), amount INTEGER, status VARCHAR(50) DEFAULT 'Pending', order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);")
    # === NAYA TABLES - CROSS DEVICE KE LIYE ===
    cur.execute("CREATE TABLE IF NOT EXISTS carts (id SERIAL PRIMARY KEY, email VARCHAR(255), product_id VARCHAR(255), name TEXT, price INTEGER, qty INTEGER DEFAULT 1, image TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS wishlists (id SERIAL PRIMARY KEY, email VARCHAR(255), product_id VARCHAR(255), name TEXT, price INTEGER, image TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS user_addresses (id SERIAL PRIMARY KEY, email VARCHAR(255), full_name VARCHAR(255), phone VARCHAR(20), pincode VARCHAR(20), full_address TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS user_orders (id SERIAL PRIMARY KEY, email VARCHAR(255), order_id VARCHAR(100), product_name TEXT, amount INTEGER, status VARCHAR(50) DEFAULT 'Pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    conn.commit()
    cur.close()
    conn.close()
    return "REKAVO FIXED - All tables ready + Cart/Wishlist/Orders/Address ready"

@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({"success": False, "error": "Email required"}), 400
    otp = str(random.randint(100000, 999999))
    expiry = datetime.now() + timedelta(minutes=10)
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO otps (email, otp_code, expires_at) VALUES (%s, %s, %s) ON CONFLICT (email) DO UPDATE SET otp_code=%s, expires_at=%s", (email, otp, expiry, otp, expiry))
    conn.commit(); cur.close(); conn.close()
    try:
        resend.Emails.send({"from": "REKAVO <otp@rekavo.in>","to": email,"subject": f"{otp} is your REKAVO OTP","html": f"<h1>{otp}</h1><p>Valid for 10 min. Don't share.</p>"})
    except Exception as e:
        print(f"Resend error: {e}")
    return jsonify({"success": True, "message": "OTP sent"})

@app.route('/check-otp', methods=['POST'])
def check_otp():
    data = request.get_json()
    email = data.get('email')
    user_otp = str(data.get('otp')).strip()
    if not email or not user_otp:
        return jsonify({"success": False, "error": "Email and OTP required"}), 400
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT otp_code, expires_at FROM otps WHERE email=%s", (email,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return jsonify({"success": False, "error": "No OTP found. Please resend."}), 400
    db_otp, expiry = row
    if datetime.now() > expiry:
        cur.execute("DELETE FROM otps WHERE email=%s", (email,))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"success": False, "error": "OTP expired. Resend again."}), 400
    if str(db_otp).strip()!= user_otp:
        cur.close(); conn.close()
        return jsonify({"success": False, "error": "Invalid OTP. Check email."}), 400
    cur.close(); conn.close()
    return jsonify({"success": True, "message": "OTP verified"})

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email, user_otp = data.get('email'), str(data.get('otp')).strip()
    name, phone, password = data.get('name'), data.get('phone'), data.get('password')
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT otp_code, expires_at FROM otps WHERE email=%s", (email,))
    row = cur.fetchone()
    if not row: cur.close(); conn.close(); return jsonify({"success": False, "error": "OTP not sent"}), 400
    db_otp, expiry = row
    if datetime.now() > expiry: cur.close(); conn.close(); return jsonify({"success": False, "error": "OTP expired"}), 400
    if str(db_otp).strip() == user_otp:
        if name and password:
            cur.execute("INSERT INTO users (name, phone, email, password) VALUES (%s, %s, %s, %s) ON CONFLICT (email) DO UPDATE SET name=%s, phone=%s, password=%s", (name, phone, email, password, name, phone, password))
            conn.commit()
            cur.execute("SELECT id, name, phone, email FROM users WHERE email=%s", (email,))
            u = cur.fetchone()
            cur.execute("DELETE FROM otps WHERE email=%s", (email,))
            conn.commit()
            cur.close(); conn.close()
            return jsonify({"success": True, "user": {"id": u[0], "name": u[1], "phone": u[2], "email": u[3]}})
        cur.close(); conn.close()
        return jsonify({"success": True})
    else:
        cur.close(); conn.close()
        return jsonify({"success": False, "error": "Wrong OTP"}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id, name, phone, email, password FROM users WHERE email=%s OR phone=%s", (email, email))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row: return jsonify({"success": False, "error": "User not found. Please register."}), 400
    if row[4]!= password: return jsonify({"success": False, "error": "Wrong password"}), 400
    return jsonify({"success": True, "user": {"id": row[0], "name": row[1], "phone": row[2], "email": row[3]}})

@app.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    email, otp, new_pass = data.get('email'), str(data.get('otp')).strip(), data.get('new_password')
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT otp_code, expires_at FROM otps WHERE email=%s", (email,))
    row = cur.fetchone()
    if not row: cur.close(); conn.close(); return jsonify({"success": False, "error": "No OTP found"}), 400
    db_otp, expiry = row
    if datetime.now() > expiry: cur.close(); conn.close(); return jsonify({"success": False, "error": "OTP expired"}), 400
    if str(db_otp).strip()!= otp: cur.close(); conn.close(); return jsonify({"success": False, "error": "Invalid OTP"}), 400
    cur.execute("UPDATE users SET password=%s WHERE email=%s", (new_pass, email))
    cur.execute("DELETE FROM otps WHERE email=%s", (email,))
    conn.commit()
    cur.close(); conn.close()
    return jsonify({"success": True, "message": "Password updated"})

# ========= NAYA REAL CART / WISHLIST / ADDRESS / ORDERS API - CROSS DEVICE =========

@app.route('/cart/get', methods=['GET'])
def cart_get():
    email = request.args.get('email','').lower()
    if not email: return jsonify([])
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE email=%s", (email,))
    rows=cur.fetchall(); cur.close(); conn.close()
    return jsonify([{"product_id": r[0], "name": r[1], "price": r[2], "qty": r[3], "image": r[4]} for r in rows])

@app.route('/cart/add', methods=['POST'])
def cart_add():
    d=request.get_json(); email=d.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT qty FROM carts WHERE email=%s AND product_id=%s", (email, d['product_id']))
    r=cur.fetchone()
    if r:
        cur.execute("UPDATE carts SET qty=qty+%s WHERE email=%s AND product_id=%s", (d.get('qty',1), email, d['product_id']))
    else:
        cur.execute("INSERT INTO carts (email, product_id, name, price, qty, image) VALUES (%s,%s,%s,%s,%s,%s)", (email, d['product_id'], d['name'], d['price'], d.get('qty',1), d.get('image','')))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True})

@app.route('/cart/remove', methods=['POST'])
def cart_remove():
    d=request.get_json(); email=d.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    cur.execute("DELETE FROM carts WHERE email=%s AND product_id=%s", (email, d['product_id']))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True})

@app.route('/wishlist/get', methods=['GET'])
def wishlist_get():
    email=request.args.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT product_id, name, price, image FROM wishlists WHERE email=%s", (email,))
    rows=cur.fetchall(); cur.close(); conn.close()
    return jsonify([{"product_id": r[0], "name": r[1], "price": r[2], "image": r[3]} for r in rows])

@app.route('/wishlist/toggle', methods=['POST'])
def wishlist_toggle():
    d=request.get_json(); email=d.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT id FROM wishlists WHERE email=%s AND product_id=%s", (email, d['product_id']))
    r=cur.fetchone()
    if r:
        cur.execute("DELETE FROM wishlists WHERE email=%s AND product_id=%s", (email, d['product_id']))
        action="removed"
    else:
        cur.execute("INSERT INTO wishlists (email, product_id, name, price, image) VALUES (%s,%s,%s,%s,%s)", (email, d['product_id'], d['name'], d['price'], d.get('image','')))
        action="added"
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True, "action": action})

@app.route('/orders/get', methods=['GET'])
def orders_get():
    email=request.args.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT order_id, product_name, amount, status, created_at FROM user_orders WHERE email=%s ORDER BY id DESC", (email,))
    rows=cur.fetchall(); cur.close(); conn.close()
    return jsonify([{"order_id": r[0], "product_name": r[1], "amount": r[2], "status": r[3], "date": str(r[4])} for r in rows])

@app.route('/address/get', methods=['GET'])
def address_get():
    email=request.args.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT id, full_name, phone, pincode, full_address FROM user_addresses WHERE email=%s", (email,))
    rows=cur.fetchall(); cur.close(); conn.close()
    return jsonify([{"id": r[0], "full_name": r[1], "phone": r[2], "pincode": r[3], "full_address": r[4]} for r in rows])

@app.route('/address/add', methods=['POST'])
def address_add():
    d=request.get_json(); email=d.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    cur.execute("INSERT INTO user_addresses (email, full_name, phone, pincode, full_address) VALUES (%s,%s,%s,%s,%s)", (email, d['full_name'], d['phone'], d['pincode'], d['full_address']))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True})

@app.route('/admin-users')
def admin_users():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT id, name, phone, email, password, created_at FROM users ORDER BY id DESC")
        rows = cur.fetchall(); cur.close(); conn.close()
        html_rows = ""
        for r in rows:
            html_rows += f"<tr><td>#{r[0]}</td><td>{r[1]}</td><td>{r[2] or '-'}</td><td>{r[3]}</td><td><span style='filter:blur(4px)'>{r[4]}</span></td><td>{r[5].strftime('%d %b') if r[5] else ''}</td><td><a href='/admin-user/{r[0]}' style='background:#6e00ff;color:white;padding:6px 12px;border-radius:8px;text-decoration:none;'>View</a></td></tr>"
        return f"<html><head><meta name='viewport' content='width=device-width'><style>body{{font-family:sans-serif;background:#f4f6f9;padding:15px}}.header{{background:linear-gradient(135deg,#6e00ff,#ff00a0);color:white;padding:20px;border-radius:15px}} table{{width:100%;background:white;border-radius:10px;border-collapse:collapse}} th,td{{padding:12px 10px;border-bottom:1px solid #eee;text-align:left;font-size:12px}}</style></head><body><div class='header'><h2>REKAVO Admin - Total: {len(rows)}</h2></div><div style='overflow-x:auto;margin-top:15px;'><table><tr><th>ID</th><th>Name</th><th>Mobile</th><th>Email</th><th>Pass</th><th>Date</th><th>Action</th></tr>{html_rows or '<tr><td colspan=7 style=text-align:center;padding:30px>No users</td></tr>'}</table></div></body></html>"
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/')
def home(): return "REKAVO Fixed - OTP Lock Enabled + Cart/Wishlist Ready"

@app.route('/delete-user/<int:user_id>')
def delete_user(user_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM orders WHERE user_id=%s", (user_id,))
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit(); cur.close(); conn.close()
    return f"User #{user_id} Deleted. <a href='/admin-users'>Back</a>"

@app.route('/admin-user/<int:user_id>')
def admin_user_detail(user_id):
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT id, name, phone, email FROM users WHERE id=%s", (user_id,))
    user=cur.fetchone()
    cur.execute("SELECT id, product_name, amount, status FROM orders WHERE user_id=%s", (user_id,))
    orders=cur.fetchall()
    cur.close(); conn.close()
    return f"<html><body style='font-family:sans-serif;padding:20px'><a href='/admin-users'>Back</a><h2>{user[1]} (#{user[0]})</h2><p>{user[3]} | {user[2]}</p><h3>Orders: {len(orders)}</h3></body></html>"
