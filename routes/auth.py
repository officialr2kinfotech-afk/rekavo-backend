from flask import request, jsonify
from app import app
import random, os, json, jwt
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2.extras import RealDictCursor
import resend

resend.api_key = os.getenv("RESEND_API_KEY")
SECRET_KEY = os.getenv("SELLER_SECRET", "rekavo-seller-secret-2024")
from database import get_db

def get_otp_html(otp, purpose="REKAVO Verification"):
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #eee; border-radius: 12px; overflow: hidden;">
        <div style="background: #111; padding: 20px; text-align: center;"><h1 style="color: #fff; margin: 0; letter-spacing: 2px;">REKAVO</h1></div>
        <div style="padding: 30px;"><h2 style="color: #111; margin-top: 0;">{purpose}</h2>
            <p>Your OTP is:</p>
            <div style="background: #f7f7f7; border: 2px dashed #111; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
                <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #111;">{otp}</span>
            </div>
            <p>Valid for 10 minutes.</p>
        </div>
    </div>
    """

@app.route('/create-table')
def create_table():
    conn = get_db(); cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS otps (email VARCHAR(255) PRIMARY KEY, otp_code VARCHAR(6), expires_at TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name VARCHAR(255), email VARCHAR(255) UNIQUE, password VARCHAR(255), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, user_id INTEGER, product_name VARCHAR(255), amount INTEGER, status VARCHAR(50) DEFAULT 'Pending', order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS carts (id SERIAL PRIMARY KEY, user_id INTEGER, email VARCHAR(255), product_id VARCHAR(255), name TEXT, price INTEGER, qty INTEGER DEFAULT 1, image TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS wishlists (id SERIAL PRIMARY KEY, user_id INTEGER, email VARCHAR(255), product_id VARCHAR(255), name TEXT, price INTEGER, image TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS user_addresses (id SERIAL PRIMARY KEY, user_id INTEGER, email VARCHAR(255), full_name VARCHAR(255), phone VARCHAR(20), pincode VARCHAR(20), full_address TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS user_orders (id SERIAL PRIMARY KEY, user_id INTEGER, email VARCHAR(255), order_id VARCHAR(100), product_name TEXT, amount INTEGER, status VARCHAR(50) DEFAULT 'Pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS sellers (id SERIAL PRIMARY KEY, store_name TEXT NOT NULL, owner_name TEXT, email TEXT UNIQUE NOT NULL, phone TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, gstin TEXT, bank_account TEXT, ifsc TEXT, created_at TIMESTAMPTZ DEFAULT NOW());")
    cur.execute("CREATE TABLE IF NOT EXISTS products (id SERIAL PRIMARY KEY, dealer_id TEXT, title TEXT, brand TEXT, sku TEXT, category TEXT, sub_category TEXT, product_type TEXT, description TEXT, bullets TEXT, main_image TEXT, gallery TEXT, mrp INTEGER, selling_price INTEGER, gst INTEGER, total_stock INTEGER, variant_attributes TEXT, variants TEXT, specs TEXT, weight INTEGER, status TEXT, created_at TIMESTAMP);")
    conn.commit(); cur.close(); conn.close()
    return "REKAVO FIXED - All Tables Ready"

# ===== SELLER OTP =====
@app.route('/seller-send-otp', methods=['POST', 'OPTIONS'])
def seller_send_otp():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    try:
        data = request.get_json() or {}
        email = data.get('email','').lower().strip()
        if not email: return jsonify({"success": False, "error": "Email required"}), 400
        otp = str(random.randint(100000, 999999))
        expiry = datetime.now() + timedelta(minutes=10)
        conn = get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO otps (email, otp_code, expires_at) VALUES (%s, %s, %s) ON CONFLICT (email) DO UPDATE SET otp_code=%s, expires_at=%s", (email, otp, expiry, otp, expiry))
        conn.commit(); cur.close(); conn.close()
        try:
            resend.Emails.send({"from": "REKAVO <otp@rekavo.in>","to": [email],"subject": f"{otp} is your REKAVO Seller OTP","html": get_otp_html(otp, "Seller Verification")})
        except Exception as e:
            print(f"Resend seller error: {e}")
        return jsonify({"success": True, "message": "Seller OTP sent"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/seller-verify-otp', methods=['POST', 'OPTIONS'])
def seller_verify_otp():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    try:
        data = request.get_json() or {}
        email = data.get('email','').lower().strip()
        user_otp = str(data.get('otp') or '').strip()
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT otp_code, expires_at FROM otps WHERE LOWER(email)=%s", (email,))
        row = cur.fetchone()
        if not row: cur.close(); conn.close(); return jsonify({"success": False, "error": "OTP not found"}), 400
        db_otp, expiry = row
        if expiry and expiry.tzinfo: expiry = expiry.replace(tzinfo=None)
        if expiry and datetime.now() > expiry: cur.close(); conn.close(); return jsonify({"success": False, "error": "OTP expired"}), 400
        if str(db_otp).strip() == user_otp:
            cur.execute("DELETE FROM otps WHERE LOWER(email)=%s", (email,))
            conn.commit(); cur.close(); conn.close()
            return jsonify({"success": True})
        else:
            cur.close(); conn.close()
            return jsonify({"success": False, "error": "Invalid OTP"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== SELLER REGISTER/LOGIN =====
@app.route('/seller-register', methods=['POST'])
def seller_register():
    data = request.get_json()
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id FROM sellers WHERE email=%s OR phone=%s", (data['email'], data['phone']))
        if cur.fetchone(): cur.close(); conn.close(); return jsonify({"error": "Email or Phone already registered"}), 400
        hashed = generate_password_hash(data['password'])
        cur.execute("INSERT INTO sellers (store_name, owner_name, email, phone, password_hash, gstin, bank_account, ifsc) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;", (data.get('store_name'), data.get('owner_name'), data.get('email'), data.get('phone'), hashed, data.get('gstin', ''), data.get('bank_account', ''), data.get('ifsc', '')))
        seller_id = cur.fetchone()['id']
        conn.commit(); cur.close(); conn.close()
        return jsonify({"message": "Seller registered!", "seller_id": seller_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/seller-login', methods=['POST'])
def seller_login():
    data = request.get_json()
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM sellers WHERE email=%s OR phone=%s", (data['email'], data.get('email')))
    seller = cur.fetchone(); cur.close(); conn.close()
    if seller and check_password_hash(seller['password_hash'], data['password']):
        payload = {"seller_id": seller['id'], "email": seller['email'], "exp": datetime.utcnow() + timedelta(days=7)}
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        resp = jsonify({"message": "Login success"}); resp.set_cookie('seller_token', token, httponly=True, secure=True, samesite='None', max_age=604800, path='/'); return resp
    else:
        return jsonify({"error": "Invalid email or password"}), 401

# ===== CUSTOMER OTP =====
@app.route('/send-otp', methods=['POST', 'OPTIONS'])
def send_otp():
    if request.method == 'OPTIONS': return jsonify({"success": True}), 200
    try:
        data = request.get_json() or {}
        email = data.get('email','').lower().strip()
        if not email: return jsonify({"success": False, "error": "Email required"}), 400
        otp = str(random.randint(100000, 999999))
        expiry = datetime.now() + timedelta(minutes=10)
        conn = get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO otps (email, otp_code, expires_at) VALUES (%s, %s, %s) ON CONFLICT (email) DO UPDATE SET otp_code=%s, expires_at=%s", (email, otp, expiry, otp, expiry))
        conn.commit(); cur.close(); conn.close()
        try:
            resend.Emails.send({"from": "REKAVO <otp@rekavo.in>","to": [email],"subject": f"{otp} is your REKAVO OTP","html": get_otp_html(otp, "Email Verification")})
        except Exception as e: print(f"Resend error: {e}")
        return jsonify({"success": True, "message": "OTP sent"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/verify-otp', methods=['POST', 'OPTIONS'])
@app.route('/check-otp', methods=['POST', 'OPTIONS'])
def verify_otp():
    if request.method == 'OPTIONS': return jsonify({"success": True}), 200
    try:
        data = request.get_json() or {}
        email = data.get('email','').lower().strip()
        user_otp = str(data.get('otp') or '').strip()
        name, phone, password = data.get('name'), data.get('phone') or data.get('mobile'), data.get('password')
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT otp_code, expires_at FROM otps WHERE LOWER(email)=%s", (email,))
        row = cur.fetchone()
        if not row: cur.close(); conn.close(); return jsonify({"success": False, "error": "OTP not found"}), 400
        db_otp, expiry = row
        if expiry and expiry.tzinfo: expiry = expiry.replace(tzinfo=None)
        if expiry and datetime.now() > expiry: cur.close(); conn.close(); return jsonify({"success": False, "error": "OTP expired"}), 400
        if str(db_otp).strip() == user_otp:
            if name and password:
                hashed = generate_password_hash(password)
                cur.execute("INSERT INTO users (name, phone, email, password) VALUES (%s, %s, %s, %s) ON CONFLICT (email) DO UPDATE SET name=%s, phone=%s, password=%s", (name, phone, email, hashed, name, phone, hashed))
                conn.commit()
                cur.execute("SELECT id, name, phone, email FROM users WHERE LOWER(email)=%s", (email,))
                u = cur.fetchone()
                cur.execute("DELETE FROM otps WHERE LOWER(email)=%s", (email,))
                conn.commit(); cur.close(); conn.close()
                return jsonify({"success": True, "user": {"id": u[0], "name": u[1], "phone": u[2], "email": u[3]}})
            cur.close(); conn.close()
            return jsonify({"success": True, "message": "OTP verified"})
        else:
            cur.close(); conn.close()
            return jsonify({"success": False, "error": "Invalid OTP"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS': return jsonify({"success": True}), 200
    try:
        data = request.get_json() or {}
        login_text = data.get('email','').strip(); password = data.get('password')
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT id, name, phone, email, password FROM users WHERE LOWER(TRIM(email))=%s OR TRIM(phone)=%s", (login_text.lower(), login_text))
        row = cur.fetchone(); cur.close(); conn.close()
        if not row: return jsonify({"success": False, "error": "User not found"}), 404
        db_pass = row[4]
        is_ok = check_password_hash(db_pass, password) if db_pass.startswith('scrypt:') or db_pass.startswith('pbkdf2:') else (db_pass == password)
        if not is_ok: return jsonify({"success": False, "error": "Incorrect password"}), 400
        return jsonify({"success": True, "user": {"id": row[0], "name": row[1], "phone": row[2], "email": row[3]}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Baki profile wale routes same rakhe hai
@app.route('/user/update-name', methods=['POST', 'OPTIONS'])
def update_name():
    if request.method == 'OPTIONS': return jsonify({"success": True}), 200
    d = request.get_json() or {}; conn=get_db(); cur=conn.cursor()
    cur.execute("UPDATE users SET name=%s WHERE id=%s", (d.get('name'), d.get('user_id'))); conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True})

@app.route('/profile/request-change', methods=['POST', 'OPTIONS'])
def profile_request_change():
    if request.method == 'OPTIONS': return jsonify({"success": True}), 200
    d = request.get_json() or {}; old_email = (d.get('old_email') or '').lower().strip(); otp = str(random.randint(100000, 999999)); expiry = datetime.now() + timedelta(minutes=10)
    conn=get_db(); cur=conn.cursor(); cur.execute("INSERT INTO otps (email, otp_code, expires_at) VALUES (%s,%s,%s) ON CONFLICT (email) DO UPDATE SET otp_code=%s, expires_at=%s", (old_email, otp, expiry, otp, expiry)); conn.commit(); cur.close(); conn.close()
    try: resend.Emails.send({"from": "REKAVO <otp@rekavo.in>","to": [old_email],"subject": f"{otp} - Verify profile change","html": get_otp_html(otp, "Profile Change")})
    except: pass
    return jsonify({"success": True, "message": "OTP sent to current email"})

@app.route('/profile/verify-and-update', methods=['POST', 'OPTIONS'])
def profile_verify_and_update():
    if request.method == 'OPTIONS': return jsonify({"success": True}), 200
    d = request.get_json() or {}; uid = d.get('user_id'); old_email = (d.get('old_email') or '').lower().strip(); new_email = (d.get('new_email') or '').lower().strip() or old_email; new_phone = (d.get('new_phone') or '').strip(); new_name = (d.get('name') or '').strip(); user_otp = str(d.get('otp') or '').strip()
    conn = get_db(); cur = conn.cursor(); cur.execute("SELECT otp_code, expires_at FROM otps WHERE LOWER(email)=%s", (old_email,)); row = cur.fetchone()
    if not row: cur.close(); conn.close(); return jsonify({"success": False, "error": "OTP not found"}), 400
    db_otp, expiry = row
    if expiry and expiry.tzinfo: expiry = expiry.replace(tzinfo=None)
    if expiry and datetime.now() > expiry: cur.close(); conn.close(); return jsonify({"success": False, "error": "OTP expired"}), 400
    if str(db_otp).strip()!= user_otp: cur.close(); conn.close(); return jsonify({"success": False, "error": "Invalid OTP"}), 400
    cur.execute("UPDATE users SET name=%s, phone=%s, email=%s WHERE id=%s", (new_name, new_phone, new_email, uid)); cur.execute("DELETE FROM otps WHERE LOWER(email)=%s", (old_email,)); conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True, "message": "Profile updated"})
