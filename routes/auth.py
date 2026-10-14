from flask import request, jsonify
from app import app
import random, os, psycopg2
from psycopg2.extras import RealDictCursor
import resend
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db
from email_service import send_welcome_email

@app.route('/create-table')
def create_table():
    conn = get_db(); cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS otps (email VARCHAR(255) PRIMARY KEY, otp_code VARCHAR(6), expires_at TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name VARCHAR(255), email VARCHAR(255) UNIQUE, password VARCHAR(255), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, user_id INTEGER, product_name VARCHAR(255), amount INTEGER, status VARCHAR(50) DEFAULT 'Pending', order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);")
    cur.execute("CREATE TABLE IF NOT EXISTS carts (id SERIAL PRIMARY KEY, user_id INTEGER, email VARCHAR(255), product_id VARCHAR(255), name TEXT, price INTEGER, qty INTEGER DEFAULT 1, image TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS wishlists (id SERIAL PRIMARY KEY, user_id INTEGER, email VARCHAR(255), product_id VARCHAR(255), name TEXT, price INTEGER, image TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS user_addresses (id SERIAL PRIMARY KEY, user_id INTEGER, email VARCHAR(255), full_name VARCHAR(255), phone VARCHAR(20), pincode VARCHAR(20), full_address TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS user_orders (id SERIAL PRIMARY KEY, user_id INTEGER, email VARCHAR(255), order_id VARCHAR(100), product_name TEXT, amount INTEGER, status VARCHAR(50) DEFAULT 'Pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("ALTER TABLE user_addresses ADD COLUMN IF NOT EXISTS city VARCHAR(100);")
    cur.execute("ALTER TABLE user_addresses ADD COLUMN IF NOT EXISTS state VARCHAR(100);")
    cur.execute("ALTER TABLE user_addresses ADD COLUMN IF NOT EXISTS locality VARCHAR(255);")
    cur.execute("CREATE TABLE IF NOT EXISTS sellers (id SERIAL PRIMARY KEY, store_name TEXT NOT NULL, owner_name TEXT, email TEXT UNIQUE NOT NULL, phone TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, gstin TEXT, bank_account TEXT, ifsc TEXT, created_at TIMESTAMPTZ DEFAULT NOW());")
    cur.execute("ALTER TABLE user_addresses ADD COLUMN IF NOT EXISTS alt_phone VARCHAR(20);")
    cur.execute("ALTER TABLE user_addresses ADD COLUMN IF NOT EXISTS line1 VARCHAR(255);")
    cur.execute("ALTER TABLE user_addresses ADD COLUMN IF NOT EXISTS line2 VARCHAR(255);")
    cur.execute("ALTER TABLE user_addresses ADD COLUMN IF NOT EXISTS landmark VARCHAR(255);")
    cur.execute("ALTER TABLE user_addresses ADD COLUMN IF NOT EXISTS type VARCHAR(20) DEFAULT 'Home';")
    cur.execute("ALTER TABLE carts ADD COLUMN IF NOT EXISTS user_id INTEGER;")
    cur.execute("ALTER TABLE wishlists ADD COLUMN IF NOT EXISTS user_id INTEGER;")
    cur.execute("ALTER TABLE user_addresses ADD COLUMN IF NOT EXISTS user_id INTEGER;")
    cur.execute("ALTER TABLE user_orders ADD COLUMN IF NOT EXISTS user_id INTEGER;")
    conn.commit(); cur.close(); conn.close()
    return "REKAVO FIXED - Neon DB Ready"
    
# ===== FINAL SELLER AUTH - SINGLE ROUTE, 8 FIELDS, SECURE =====
import jwt
from datetime import datetime, timedelta
SECRET_KEY = "rekavo-seller-secret-2024-change-later-in-env"

@app.route('/seller-register', methods=['POST'])
def seller_register():
    data = request.get_json()
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id FROM sellers WHERE email=%s OR phone=%s", (data['email'], data['phone']))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({"error": "Email or Phone already registered"}), 400

        hashed = generate_password_hash(data['password'])
        cur.execute(
            """INSERT INTO sellers 
               (store_name, owner_name, email, phone, password_hash, gstin, bank_account, ifsc) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;""",
            (
                data.get('store_name'), 
                data.get('owner_name'), 
                data.get('email'), 
                data.get('phone'), 
                hashed,
                data.get('gstin', ''), 
                data.get('bank_account', ''), 
                data.get('ifsc', '')
            )
        )
        seller_id = cur.fetchone()['id']
        conn.commit(); cur.close(); conn.close()
        return jsonify({"message": "Seller registered!", "seller_id": seller_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/seller-login', methods=['POST'])
def seller_login():
    data = request.get_json()
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM sellers WHERE email=%s OR phone=%s", (data['email'], data.get('email')))
    seller = cur.fetchone()
    cur.close(); conn.close()
    
    if seller and check_password_hash(seller['password_hash'], data['password']):
        # Secure JWT Cookie - koi localStorage nahi
        payload = {
            "seller_id": seller['id'], 
            "email": seller['email'], 
            "exp": datetime.utcnow() + timedelta(days=7)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        resp = jsonify({"message": "Login success"})
        resp.set_cookie('seller_token', token, httponly=True, secure=True, samesite='None', max_age=604800, path='/')
        return resp
    else:
        return jsonify({"error": "Invalid email or password"}), 401

@app.route('/seller-verify', methods=['GET'])
def seller_verify():
    token = request.cookies.get('seller_token')
    if not token:
        return jsonify({"logged_in": False}), 401
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, store_name, owner_name, email, phone, gstin FROM sellers WHERE id=%s", (data['seller_id'],))
        seller = cur.fetchone()
        cur.close(); conn.close()
        if seller:
            return jsonify({"logged_in": True, "seller": seller}), 200
        return jsonify({"logged_in": False}), 401
    except:
        return jsonify({"logged_in": False}), 401

@app.route('/seller-logout', methods=['POST'])
def seller_logout():
    resp = jsonify({"message": "Logged out"})
    resp.delete_cookie('seller_token', path='/')
    return resp
@app.route('/send-otp', methods=['POST', 'OPTIONS'])
def send_otp():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    try:
        data = request.get_json() or {}
        email = data.get('email','').lower().strip()
        if not email: return jsonify({"success": False, "error": "Email is required"}), 400
        otp = str(random.randint(100000, 999999))
        expiry = datetime.now() + timedelta(minutes=10)
        conn = get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO otps (email, otp_code, expires_at) VALUES (%s, %s, %s) ON CONFLICT (email) DO UPDATE SET otp_code=%s, expires_at=%s", (email, otp, expiry, otp, expiry))
        conn.commit(); cur.close(); conn.close()
        try:
            resend.Emails.send({"from": "REKAVO <otp@rekavo.in>","to": email,"subject": f"{otp} is your REKAVO OTP","html": f"<h1>{otp}</h1><p>Valid for 10 min.</p>"})
        except Exception as e: print(f"Resend error: {e}")
        return jsonify({"success": True, "message": "OTP has been sent to your email"})
    except Exception as e:
        print(f"SEND-OTP ERROR: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/check-otp', methods=['POST', 'OPTIONS'])
@app.route('/verify-otp', methods=['POST', 'OPTIONS'])
def verify_otp():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    try:
        data = request.get_json() or {}
        email = data.get('email','').lower().strip()
        user_otp = str(data.get('otp') or '').strip()
        name, phone, password = data.get('name'), data.get('phone') or data.get('mobile'), data.get('password')
        if not email or not user_otp:
            return jsonify({"success": False, "error": "Email and OTP are required"}), 400
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT otp_code, expires_at FROM otps WHERE LOWER(email)=%s", (email,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            return jsonify({"success": False, "error": "OTP not found. Please resend OTP."}), 400
        db_otp, expiry = row
        try:
            if expiry and expiry.tzinfo is not None:
                expiry = expiry.replace(tzinfo=None)
        except: pass
        if expiry and datetime.now() > expiry:
            cur.close(); conn.close()
            return jsonify({"success": False, "error": "OTP has expired. Please resend OTP."}), 400
        if str(db_otp).strip() == user_otp:
            if name and password:
                hashed = generate_password_hash(password)
                cur.execute("INSERT INTO users (name, phone, email, password) VALUES (%s, %s, %s, %s) ON CONFLICT (email) DO UPDATE SET name=%s, phone=%s, password=%s", (name, phone, email, hashed, name, phone, hashed))
                conn.commit()
                cur.execute("SELECT id, name, phone, email FROM users WHERE LOWER(email)=%s", (email,))
                u = cur.fetchone()
                cur.execute("DELETE FROM otps WHERE LOWER(email)=%s", (email,))
                conn.commit()
                cur.close(); conn.close()
                try:
                    send_welcome_email(email, name or "there")
                except Exception as e:
                    print(f"Welcome mail failed but user created: {e}")
                return jsonify({"success": True, "user": {"id": u[0], "name": u[1], "phone": u[2], "email": u[3]}})
            cur.close(); conn.close()
            return jsonify({"success": True, "message": "OTP verified successfully"})
        else:
            cur.close(); conn.close()
            return jsonify({"success": False, "error": "Invalid OTP. Please try again."}), 400
    except Exception as e:
        print(f"VERIFY-OTP ERROR: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500

@app.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    try:
        data = request.get_json() or {}
        login_text = data.get('email','').strip()
        password = data.get('password')
        if not login_text or not password: return jsonify({"success": False, "error": "Email/Phone and password are required"}), 400
        conn = get_db(); cur = conn.cursor()
        # FIX: Login with new email OR new phone both will work
        cur.execute("SELECT id, name, phone, email, password FROM users WHERE LOWER(TRIM(email))=%s OR TRIM(phone)=%s", (login_text.lower(), login_text))
        row = cur.fetchone(); cur.close(); conn.close()
        if not row: return jsonify({"success": False, "error": "User not found. Please check your email or phone number."}), 404
        db_pass = row[4]
        is_ok = False
        try:
            if db_pass and (db_pass.startswith('scrypt:') or db_pass.startswith('pbkdf2:')):
                is_ok = check_password_hash(db_pass, password)
            else:
                is_ok = (db_pass == password)
        except: is_ok = (db_pass == password)
        if not is_ok: return jsonify({"success": False, "error": "Incorrect password. Please try again."}), 400
        return jsonify({"success": True, "user": {"id": row[0], "name": row[1], "phone": row[2], "email": row[3]}})
    except Exception as e:
        print(f"LOGIN ERROR: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/user/update-name', methods=['POST', 'OPTIONS'])
def update_name():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    d = request.get_json() or {}
    uid = d.get('user_id')
    name = (d.get('name') or '').strip()
    if not uid or not name: return jsonify({"success": False, "error":"Name is required"}), 400
    try: uid_int = int(uid)
    except: uid_int = uid
    conn=get_db(); cur=conn.cursor()
    cur.execute("UPDATE users SET name=%s WHERE id=%s", (name, uid_int))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True, "message": "Name updated successfully"})

@app.route('/profile/request-change', methods=['POST', 'OPTIONS'])
def profile_request_change():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    d = request.get_json() or {}
    old_email = (d.get('old_email') or '').lower().strip()
    new_email = (d.get('new_email') or '').lower().strip() or old_email
    new_phone = (d.get('new_phone') or '').strip()
    user_id = d.get('user_id')
    if not old_email: return jsonify({"success": False, "error":"Current email is required"}), 400
    conn=get_db(); cur=conn.cursor()
    try: uid_int = int(user_id)
    except: uid_int = user_id

    cur.execute("SELECT phone FROM users WHERE id=%s OR LOWER(email)=%s LIMIT 1", (uid_int, old_email))
    urow = cur.fetchone()
    old_phone = str(urow[0] if urow else '').strip() if urow else ''

    if old_email == new_email and old_phone == new_phone:
        cur.close(); conn.close()
        return jsonify({"success": False, "error":"No changes detected"}), 400

    # CHECK: Email already exists
    if new_email!= old_email:
        cur.execute("SELECT id FROM users WHERE LOWER(email)=%s AND id!= %s", (new_email, uid_int))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({"success": False, "error":"This email is already registered. Please use a different email."}), 400

    # CHECK: Phone already exists - NEW ADDED
    if new_phone and new_phone!= old_phone:
        cur.execute("SELECT id FROM users WHERE TRIM(phone)=%s AND id!= %s", (new_phone, uid_int))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({"success": False, "error":"This phone number is already registered. Please use a different phone number."}), 400

    otp = str(random.randint(100000, 999999))
    expiry = datetime.now() + timedelta(minutes=10)
    cur.execute("INSERT INTO otps (email, otp_code, expires_at) VALUES (%s,%s,%s) ON CONFLICT (email) DO UPDATE SET otp_code=%s, expires_at=%s", (old_email, otp, expiry, otp, expiry))
    conn.commit(); cur.close(); conn.close()
    try:
        resend.Emails.send({"from": "REKAVO <otp@rekavo.in>","to": old_email,"subject": f"{otp} - Verify profile change","html": f"<h1>{otp}</h1><p>New Email: {new_email}<br>New Phone: {new_phone}<br>OTP is valid for 10 minutes.</p>"})
    except Exception as e: print(e)
    return jsonify({"success": True, "message": "OTP has been sent to your current email for verification."})

@app.route('/profile/verify-and-update', methods=['POST', 'OPTIONS'])
def profile_verify_and_update():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    d = request.get_json() or {}
    uid = d.get('user_id')
    old_email = (d.get('old_email') or '').lower().strip()
    new_email = (d.get('new_email') or '').lower().strip() or old_email
    new_phone = (d.get('new_phone') or '').strip()
    new_name = (d.get('name') or '').strip()
    user_otp = str(d.get('otp') or '').strip()
    if not uid or not user_otp: return jsonify({"success": False, "error": "OTP is required"}), 400
    conn = get_db(); cur = conn.cursor()
    try: uid_int = int(uid)
    except: uid_int = uid

    cur.execute("SELECT otp_code, expires_at FROM otps WHERE LOWER(email)=%s", (old_email,))
    row = cur.fetchone()
    if not row: cur.close(); conn.close(); return jsonify({"success": False, "error": "OTP not found. Please request a new OTP."}), 400
    db_otp, expiry = row
    try:
        if expiry and expiry.tzinfo is not None:
            expiry = expiry.replace(tzinfo=None)
    except: pass
    if expiry and datetime.now() > expiry: cur.close(); conn.close(); return jsonify({"success": False, "error": "OTP has expired. Please request a new OTP."}), 400
    if str(db_otp).strip()!= user_otp: cur.close(); conn.close(); return jsonify({"success": False, "error": "Invalid OTP. Please try again."}), 400

    if new_email!= old_email:
        cur.execute("SELECT id FROM users WHERE LOWER(email)=%s AND id!= %s", (new_email, uid_int))
        if cur.fetchone(): cur.close(); conn.close(); return jsonify({"success": False, "error": "This email is already registered."}), 400

    if new_phone:
        cur.execute("SELECT id FROM users WHERE TRIM(phone)=%s AND id!= %s", (new_phone, uid_int))
        if cur.fetchone(): cur.close(); conn.close(); return jsonify({"success": False, "error": "This phone number is already registered."}), 400

    cur.execute("UPDATE users SET name=%s, phone=%s, email=%s WHERE id=%s", (new_name, new_phone, new_email, uid_int))
    if new_email!= old_email:
        cur.execute("UPDATE carts SET email=%s WHERE LOWER(email)=%s", (new_email, old_email))
        cur.execute("UPDATE wishlists SET email=%s WHERE LOWER(email)=%s", (new_email, old_email))
        cur.execute("UPDATE user_addresses SET email=%s WHERE LOWER(email)=%s", (new_email, old_email))
        cur.execute("UPDATE user_orders SET email=%s WHERE LOWER(email)=%s", (new_email, old_email))
    cur.execute("DELETE FROM otps WHERE LOWER(email)=%s", (old_email,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True, "message": "Profile updated successfully"})

import jwt
import json
from functools import wraps
from datetime import datetime
SECRET_KEY = "rekavo-seller-secret-2024-change-later-in-env"

def seller_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('seller_token')
        if not token:
            return jsonify({"error": "Login required"}), 401
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.seller_id = data['seller_id']
        except:
            return jsonify({"error": "Invalid session"}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/products/add', methods=['POST'])
@seller_required
def add_product():
    try:
        from database import get_db
        data = request.json
        conn = get_db()
        cur = conn.cursor()
        # LOCK: dealer_id ab frontend se nahi, secure cookie se ayega
        real_dealer_id = str(request.seller_id)
        cur.execute("""
            INSERT INTO products
            (dealer_id, title, brand, sku, category, sub_category, product_type, description, bullets, main_image, gallery, mrp, selling_price, gst, total_stock, variant_attributes, variants, specs, weight, status, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            real_dealer_id,
            data.get('title'), data.get('brand'), data.get('sku'),
            data.get('category'), data.get('sub_category'),
            data.get('product_type'), data.get('description'),
            json.dumps(data.get('bullets',[])),
            data.get('main_image'),
            json.dumps(data.get('gallery',[])),
            data.get('mrp'), data.get('selling_price'), data.get('gst'),
            data.get('total_stock',0),
            json.dumps(data.get('variant_attributes',[])),
            json.dumps(data.get('variants',[])),
            json.dumps(data.get('specs',[])),
            data.get('weight',0),
            data.get('status','pending'),
            datetime.now()
        ))
        pid = cur.fetchone()[0]
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"message":"Product saved", "id": pid})
    except Exception as e:
        print("ADD ERROR:", e)
        return jsonify({"error": str(e)}), 500

@app.route('/products/get', methods=['GET'])
def get_products():
    try:
        from database import get_db
        from psycopg2.extras import RealDictCursor
        status = request.args.get('status','active')
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM products WHERE status=%s ORDER BY id DESC", (status,))
        products = cur.fetchall()
        cur.close(); conn.close()
        return jsonify(products)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
