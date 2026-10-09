from flask import Flask, request, jsonify
from flask_cors import CORS
import os, random
import psycopg2
from psycopg2.extras import RealDictCursor
import resend
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app, supports_credentials=True)

resend.api_key = os.environ.get('RESEND_API_KEY')
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

@app.route('/send-otp', methods=['POST'])
def send_otp():
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
            resend.Emails.send({"from": "REKAVO <otp@rekavo.in>","to": email,"subject": f"{otp} is your REKAVO OTP","html": f"<h1>{otp}</h1><p>Valid for 10 min.</p>"})
        except Exception as e: print(f"Resend error: {e}")
        return jsonify({"success": True, "message": "OTP sent"})
    except Exception as e:
        print(f"SEND-OTP ERROR: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    try:
        data = request.get_json() or {}
        email = data.get('email','').lower().strip()
        user_otp = str(data.get('otp') or '').strip()
        name, phone, password = data.get('name'), data.get('phone') or data.get('mobile'), data.get('password')
        if not email or not user_otp:
            return jsonify({"success": False, "error": "Email/OTP missing"}), 400
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT otp_code, expires_at FROM otps WHERE LOWER(email)=%s", (email,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            return jsonify({"success": False, "error": "OTP not sent, resend karo"}), 400
        db_otp, expiry = row
        try:
            if expiry and expiry.tzinfo is not None:
                expiry = expiry.replace(tzinfo=None)
        except: pass
        if expiry and datetime.now() > expiry:
            cur.close(); conn.close()
            return jsonify({"success": False, "error": "OTP expired, resend karo"}), 400
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
                return jsonify({"success": True, "user": {"id": u[0], "name": u[1], "phone": u[2], "email": u[3]}})
            cur.close(); conn.close()
            return jsonify({"success": True})
        else:
            cur.close(); conn.close()
            return jsonify({"success": False, "error": "Wrong OTP"}), 400
    except Exception as e:
        print(f"VERIFY-OTP ERROR: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json() or {}
        login_text = data.get('email','').strip().lower()
        password = data.get('password')
        if not login_text or not password: return jsonify({"success": False, "error": "Email/Phone and password required"}), 400
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT id, name, phone, email, password FROM users WHERE LOWER(email)=%s OR phone=%s", (login_text, login_text))
        row = cur.fetchone(); cur.close(); conn.close()
        if not row: return jsonify({"success": False, "error": "User not found"}), 404
        db_pass = row[4]
        is_ok = False
        try:
            if db_pass and (db_pass.startswith('scrypt:') or db_pass.startswith('pbkdf2:')):
                is_ok = check_password_hash(db_pass, password)
            else:
                is_ok = (db_pass == password)
        except: is_ok = (db_pass == password)
        if not is_ok: return jsonify({"success": False, "error": "Wrong password"}), 400
        return jsonify({"success": True, "user": {"id": row[0], "name": row[1], "phone": row[2], "email": row[3]}})
    except Exception as e:
        print(f"LOGIN ERROR: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/cart/get', methods=['GET'])
def cart_get():
    user_id = request.args.get('user_id'); email = request.args.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    try:
        if user_id:
            try: uid_int = int(user_id); cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE user_id=%s", (uid_int,))
            except: cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE user_id=%s OR LOWER(email)=%s", (user_id, email))
        else:
            if not email: cur.close(); conn.close(); return jsonify([])
            cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE LOWER(email)=%s", (email,))
        rows=cur.fetchall(); cleaned_dict = {}
        for r in rows:
            pid, name, price, qty, image = r
            if not pid: continue
            if qty is None: qty = 1
            if qty > 10: qty = 1
            if qty > 5: qty = 5
            if pid in cleaned_dict: cleaned_dict[pid]['qty'] = min(5, cleaned_dict[pid]['qty'] + qty)
            else: cleaned_dict[pid] = {"product_id": pid, "name": name, "price": price, "qty": qty, "image": image}
        result = list(cleaned_dict.values()); cur.close(); conn.close(); return jsonify(result)
    except Exception as e: print(e); cur.close(); conn.close(); return jsonify([])

@app.route('/cart/add', methods=['POST'])
def cart_add():
    d=request.get_json(); user_id = d.get('user_id'); email = (d.get('email') or '').lower(); product_id = d.get('product_id')
    if not product_id: return jsonify({"success": False, "error": "product_id required"}), 400
    req_qty = d.get('qty', 1)
    try: req_qty = int(req_qty)
    except: req_qty = 1
    if req_qty > 5 or req_qty < 1: req_qty = 1
    conn=get_db(); cur=conn.cursor()
    try:
        if user_id:
            try:
                uid_int = int(user_id)
                cur.execute("SELECT qty FROM carts WHERE user_id=%s AND product_id=%s", (uid_int, product_id)); r=cur.fetchone()
                if r:
                    old_qty = r[0] or 1
                    if old_qty > 10: old_qty = 0
                    new_qty = min(5, old_qty + req_qty)
                    cur.execute("UPDATE carts SET qty=%s, name=%s, price=%s, image=%s WHERE user_id=%s AND product_id=%s", (new_qty, d.get('name'), d.get('price'), d.get('image',''), uid_int, product_id))
                else: cur.execute("INSERT INTO carts (user_id, email, product_id, name, price, qty, image) VALUES (%s,%s,%s,%s,%s,%s,%s)", (uid_int, email, product_id, d.get('name'), d.get('price'), req_qty, d.get('image','')))
            except Exception as e:
                cur.execute("SELECT qty FROM carts WHERE user_id=%s AND product_id=%s", (user_id, product_id)); r=cur.fetchone()
                if r:
                    old_qty = r[0] or 1
                    if old_qty > 10: old_qty = 0
                    new_qty = min(5, old_qty + req_qty)
                    cur.execute("UPDATE carts SET qty=%s WHERE user_id=%s AND product_id=%s", (new_qty, user_id, product_id))
                else: cur.execute("INSERT INTO carts (user_id, email, product_id, name, price, qty, image) VALUES (%s,%s,%s,%s,%s,%s,%s)", (user_id, email, product_id, d.get('name'), d.get('price'), req_qty, d.get('image','')))
        else:
            if not email: cur.close(); conn.close(); return jsonify({"success": False}), 400
            cur.execute("SELECT qty FROM carts WHERE LOWER(email)=%s AND product_id=%s", (email, product_id)); r=cur.fetchone()
            if r:
                old_qty = r[0] or 1
                if old_qty > 10: old_qty = 0
                new_qty = min(5, old_qty + req_qty)
                cur.execute("UPDATE carts SET qty=%s WHERE LOWER(email)=%s AND product_id=%s", (new_qty, email, product_id))
            else: cur.execute("INSERT INTO carts (user_id, email, product_id, name, price, qty, image) VALUES (%s,%s,%s,%s,%s,%s,%s)", (None, email, product_id, d.get('name'), d.get('price'), req_qty, d.get('image','')))
        conn.commit(); cur.close(); conn.close(); return jsonify({"success": True})
    except Exception as e: print(f"cart/add error: {e}"); cur.close(); conn.close(); return jsonify({"success": False, "error": str(e)}), 500

@app.route('/cart/remove', methods=['POST'])
def cart_remove():
    d=request.get_json(); user_id = d.get('user_id'); email = d.get('email','').lower(); conn=get_db(); cur=conn.cursor()
    if user_id:
        try: uid_int = int(user_id); cur.execute("DELETE FROM carts WHERE user_id=%s AND product_id=%s", (uid_int, d['product_id']))
        except: cur.execute("DELETE FROM carts WHERE user_id=%s AND product_id=%s", (user_id, d['product_id']))
    else: cur.execute("DELETE FROM carts WHERE LOWER(email)=%s AND product_id=%s", (email, d['product_id']))
    conn.commit(); cur.close(); conn.close(); return jsonify({"success": True})

@app.route('/cart/clear', methods=['POST'])
def cart_clear():
    d=request.get_json(); user_id = d.get('user_id'); email = d.get('email','').lower(); conn=get_db(); cur=conn.cursor()
    if user_id:
        try: uid_int = int(user_id); cur.execute("DELETE FROM carts WHERE user_id=%s", (uid_int,))
        except: cur.execute("DELETE FROM carts WHERE user_id=%s", (user_id,))
    else: cur.execute("DELETE FROM carts WHERE LOWER(email)=%s", (email,))
    conn.commit(); cur.close(); conn.close(); return jsonify({"success": True})

@app.route('/wishlist/get', methods=['GET'])
def wishlist_get():
    user_id = request.args.get('user_id'); email=request.args.get('email','').lower(); conn=get_db(); cur=conn.cursor()
    if user_id:
        try: uid_int=int(user_id); cur.execute("SELECT product_id, name, price, image FROM wishlists WHERE user_id=%s", (uid_int,))
        except: cur.execute("SELECT product_id, name, price, image FROM wishlists WHERE user_id=%s", (user_id,))
    else: cur.execute("SELECT product_id, name, price, image FROM wishlists WHERE LOWER(email)=%s", (email,))
    rows=cur.fetchall(); cur.close(); conn.close(); return jsonify([{"product_id": r[0], "name": r[1], "price": r[2], "image": r[3]} for r in rows])

@app.route('/wishlist/toggle', methods=['POST'])
def wishlist_toggle():
    d=request.get_json(); user_id = d.get('user_id'); email=d.get('email','').lower(); conn=get_db(); cur=conn.cursor()
    if user_id:
        try: uid_int=int(user_id); cur.execute("SELECT id FROM wishlists WHERE user_id=%s AND product_id=%s", (uid_int, d['product_id']))
        except: cur.execute("SELECT id FROM wishlists WHERE user_id=%s AND product_id=%s", (user_id, d['product_id']))
    else: cur.execute("SELECT id FROM wishlists WHERE LOWER(email)=%s AND product_id=%s", (email, d['product_id']))
    r=cur.fetchone()
    if r:
        if user_id:
            try: cur.execute("DELETE FROM wishlists WHERE user_id=%s AND product_id=%s", (int(user_id), d['product_id']))
            except: cur.execute("DELETE FROM wishlists WHERE user_id=%s AND product_id=%s", (user_id, d['product_id']))
        else: cur.execute("DELETE FROM wishlists WHERE LOWER(email)=%s AND product_id=%s", (email, d['product_id']))
        action="removed"
    else:
        try: uid_int=int(user_id) if user_id else None
        except: uid_int=user_id
        cur.execute("INSERT INTO wishlists (user_id, email, product_id, name, price, image) VALUES (%s,%s,%s,%s,%s,%s)", (uid_int, email, d['product_id'], d['name'], d['price'], d.get('image',''))); action="added"
    conn.commit(); cur.close(); conn.close(); return jsonify({"success": True, "action": action})

@app.route('/orders/get', methods=['GET'])
def orders_get():
    user_id = request.args.get('user_id'); email=request.args.get('email','').lower(); conn=get_db(); cur=conn.cursor()
    if user_id:
        try: uid_int=int(user_id); cur.execute("SELECT order_id, product_name, amount, status, created_at FROM user_orders WHERE user_id=%s ORDER BY id DESC", (uid_int,))
        except: cur.execute("SELECT order_id, product_name, amount, status, created_at FROM user_orders WHERE user_id=%s ORDER BY id DESC", (user_id,))
    else: cur.execute("SELECT order_id, product_name, amount, status, created_at FROM user_orders WHERE LOWER(email)=%s ORDER BY id DESC", (email,))
    rows=cur.fetchall(); cur.close(); conn.close(); return jsonify([{"order_id": r[0], "product_name": r[1], "amount": r[2], "status": r[3], "date": str(r[4])} for r in rows])

@app.route('/place-order', methods=['POST'])
def place_order():
    d=request.get_json(); user_id = d.get('user_id'); email = (d.get('email') or '').lower()
    product_name = d.get('product_name') or d.get('full_name') or 'REKAVO Order'
    if d.get('items'):
        items = d.get('items')
        if isinstance(items, list) and len(items)>0:
            product_name = items[0].get('name','REKAVO Order')
            if len(items)>1: product_name = f"{product_name} + {len(items)-1} more"
    amount = d.get('amount') or d.get('total') or 0
    try: amount = int(amount)
    except: amount = 0
    conn=get_db(); cur=conn.cursor(); order_id = d.get('order_id') or f"REKAVO{random.randint(10000,99999)}"
    try: uid_int = int(user_id) if user_id else None
    except: uid_int = user_id
    cur.execute("INSERT INTO user_orders (user_id, email, order_id, product_name, amount, status) VALUES (%s,%s,%s,%s,%s,%s)", (uid_int, email, order_id, product_name, amount, 'Placed'))
    if user_id:
        try: cur.execute("DELETE FROM carts WHERE user_id=%s", (int(user_id),))
        except: cur.execute("DELETE FROM carts WHERE user_id=%s", (user_id,))
    else:
        if email: cur.execute("DELETE FROM carts WHERE LOWER(email)=%s", (email,))
    conn.commit(); cur.close(); conn.close(); return jsonify({"success": True, "order_id": order_id})

@app.route('/orders/add', methods=['POST'])
def orders_add(): return place_order()
@app.route('/orders/create', methods=['POST'])
def orders_create(): return place_order()

@app.route('/address/get', methods=['GET'])
def address_get():
    try:
        user_id = request.args.get('user_id')
        email = request.args.get('email','').lower().strip()
        conn=get_db(); cur=conn.cursor(cursor_factory=RealDictCursor)
        if email:
            cur.execute("SELECT id, user_id, email, full_name, phone, alt_phone, pincode, full_address, city, state, locality, line1, line2, landmark, type FROM user_addresses WHERE LOWER(email)=%s ORDER BY id DESC", (email,))
        elif user_id:
            try:
                cur.execute("SELECT id, user_id, email, full_name, phone, alt_phone, pincode, full_address, city, state, locality, line1, line2, landmark, type FROM user_addresses WHERE user_id=%s ORDER BY id DESC", (int(user_id),))
            except:
                cur.execute("SELECT id, user_id, email, full_name, phone, alt_phone, pincode, full_address, city, state, locality, line1, line2, landmark, type FROM user_addresses WHERE user_id::text=%s ORDER BY id DESC", (str(user_id),))
        else:
            cur.close(); conn.close()
            return jsonify([])
        rows=cur.fetchall(); cur.close(); conn.close()
        return jsonify(rows)
    except Exception as e:
        print("ADDRESS GET ERROR:", e)
        return jsonify([])

@app.route('/address/add', methods=['POST'])
def address_add():
    try:
        d=request.get_json() or {}
        user_id = d.get('user_id')
        email=(d.get('email') or '').lower().strip()
        try: uid_int=int(user_id) if user_id else None
        except: uid_int=None
        conn=get_db(); cur=conn.cursor()
        cur.execute("""
            INSERT INTO user_addresses (user_id, email, full_name, phone, alt_phone, pincode, full_address, city, state, locality, line1, line2, landmark, type)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (uid_int, email, d.get('full_name'), d.get('phone'), d.get('alt_phone'), d.get('pincode'), d.get('full_address'), d.get('city'), d.get('state'), d.get('locality'), d.get('line1'), d.get('line2'), d.get('landmark'), d.get('type','Home')))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print("ADDRESS ADD ERROR:", e)
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/address/update', methods=['POST'])
def address_update():
    try:
        d=request.get_json() or {}
        addr_id = d.get('id') or d.get('address_id')
        if not addr_id:
            return jsonify({"success": False, "error": "id missing"}), 400
        conn=get_db(); cur=conn.cursor()
        cur.execute("""
            UPDATE user_addresses SET
                full_name=%s, phone=%s, alt_phone=%s, pincode=%s, full_address=%s,
                city=%s, state=%s, locality=%s, line1=%s, line2=%s, landmark=%s, type=%s
            WHERE id=%s
        """, (d.get('full_name'), d.get('phone'), d.get('alt_phone'), d.get('pincode'), d.get('full_address'), d.get('city'), d.get('state'), d.get('locality'), d.get('line1'), d.get('line2'), d.get('landmark'), d.get('type','Home'), addr_id))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "message": "Address updated"})
    except Exception as e:
        print("ADDRESS UPDATE ERROR:", e)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/address/delete', methods=['POST'])
def address_delete():
    try:
        d=request.get_json(); conn=get_db(); cur=conn.cursor(); cur.execute("DELETE FROM user_addresses WHERE id=%s", (d.get('id') or d.get('address_id'),)); conn.commit(); cur.close(); conn.close(); return jsonify({"success": True})
    except Exception as e:
        print("DELETE ERR:", e)
        return jsonify({"success": False}), 500

@app.route('/user/update-name', methods=['POST'])
def update_name():
    d = request.get_json() or {}
    uid = d.get('user_id')
    name = (d.get('name') or '').strip()
    if not uid or not name: return jsonify({"success": False, "error":"name required"}), 400
    try: uid_int = int(uid)
    except: uid_int = uid
    conn=get_db(); cur=conn.cursor()
    cur.execute("UPDATE users SET name=%s WHERE id=%s", (name, uid_int))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True})

@app.route('/profile/request-change', methods=['POST'])
def profile_request_change():
    d = request.get_json() or {}
    old_email = (d.get('old_email') or '').lower().strip()
    new_email = (d.get('new_email') or '').lower().strip() or old_email
    new_phone = (d.get('new_phone') or '').strip()
    user_id = d.get('user_id')
    if not old_email: return jsonify({"success": False, "error":"email required"}), 400
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT phone FROM users WHERE id=%s OR LOWER(email)=%s LIMIT 1", (user_id, old_email))
    urow = cur.fetchone()
    old_phone = str(urow[0] if urow else '').strip() if urow else ''
    if old_email == new_email and old_phone == new_phone:
        cur.close(); conn.close()
        return jsonify({"success": False, "error":"No changes"}), 400
    if new_email!= old_email:
        cur.execute("SELECT id FROM users WHERE LOWER(email)=%s", (new_email,))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({"success": False, "error":"Ye email already registered hai"}), 400
    otp = str(random.randint(100000, 999999))
    expiry = datetime.now() + timedelta(minutes=10)
    cur.execute("INSERT INTO otps (email, otp_code, expires_at) VALUES (%s,%s,%s) ON CONFLICT (email) DO UPDATE SET otp_code=%s, expires_at=%s", (old_email, otp, expiry, otp, expiry))
    conn.commit(); cur.close(); conn.close()
    try:
        resend.Emails.send({"from": "REKAVO <otp@rekavo.in>","to": old_email,"subject": f"{otp} - Verify profile change","html": f"<h1>{otp}</h1><p>New Email: {new_email}<br>New Phone: {new_phone}<br>OTP 10 min valid.</p>"})
    except Exception as e: print(e)
    return jsonify({"success": True})

@app.route('/profile/verify-and-update', methods=['POST'])
def profile_verify_and_update():
    d = request.get_json() or {}
    uid = d.get('user_id')
    old_email = (d.get('old_email') or '').lower().strip()
    new_email = (d.get('new_email') or '').lower().strip() or old_email
    new_phone = (d.get('new_phone') or '').strip()
    new_name = (d.get('name') or '').strip()
    user_otp = str(d.get('otp') or '').strip()
    if not uid or not user_otp: return jsonify({"success": False, "error": "Missing fields"}), 400
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT otp_code, expires_at FROM otps WHERE LOWER(email)=%s", (old_email,))
    row = cur.fetchone()
    if not row: cur.close(); conn.close(); return jsonify({"success": False, "error": "OTP not sent"}), 400
    db_otp, expiry = row
    try:
        if expiry and expiry.tzinfo is not None:
            expiry = expiry.replace(tzinfo=None)
    except: pass
    if expiry and datetime.now() > expiry: cur.close(); conn.close(); return jsonify({"success": False, "error": "OTP expired"}), 400
    if str(db_otp).strip()!= user_otp: cur.close(); conn.close(); return jsonify({"success": False, "error": "Wrong OTP"}), 400
    if new_email!= old_email:
        cur.execute("SELECT id FROM users WHERE LOWER(email)=%s", (new_email,))
        if cur.fetchone(): cur.close(); conn.close(); return jsonify({"success": False, "error": "Email already used"}), 400
    try: uid_int = int(uid)
    except: uid_int = uid
    cur.execute("UPDATE users SET name=%s, phone=%s, email=%s WHERE id=%s", (new_name, new_phone, new_email, uid_int))
    if new_email!= old_email:
        cur.execute("UPDATE carts SET email=%s WHERE LOWER(email)=%s", (new_email, old_email))
        cur.execute("UPDATE wishlists SET email=%s WHERE LOWER(email)=%s", (new_email, old_email))
        cur.execute("UPDATE user_addresses SET email=%s WHERE LOWER(email)=%s", (new_email, old_email))
        cur.execute("UPDATE user_orders SET email=%s WHERE LOWER(email)=%s", (new_email, old_email))
    cur.execute("DELETE FROM otps WHERE LOWER(email)=%s", (old_email,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True, "message": "Profile updated"})

@app.route('/admin')
def admin_panel():
    if not is_admin_allowed():
        return "<h2>403 - Unauthorized</h2><p>Link me?key=REKAVO_KEY lagao.</p>", 403
    try:
        q = request.args.get('q','').strip().lower()
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT u.id, u.name, u.phone, u.email, u.password, u.created_at,
                   a.full_address, a.city, a.state, a.pincode
            FROM users u
            LEFT JOIN LATERAL (
                SELECT full_address, city, state, pincode FROM user_addresses
                WHERE LOWER(email)=LOWER(u.email) ORDER BY id DESC LIMIT 1
            ) a ON true
            ORDER BY u.id DESC
        """)
        rows = cur.fetchall(); cur.close(); conn.close()
        if q:
            rows = [r for r in rows if q in str(r['name']).lower() or q in str(r['email']).lower() or q in str(r['phone']).lower()]
        html_rows = ""
        for r in rows:
            city_state = f"{r['city'] or ''} {r['state'] or ''} {r['pincode'] or ''}".strip() or "<span style='color:#ff4d4d'>NO ADDR</span>"
            html_rows += f"""
            <tr>
                <td>#{r['id']}</td>
                <td><b>{r['name'] or '-'}</b></td>
                <td>{r['email'] or '-'}</td>
                <td class='mono'>{mask_mobile(r['phone'])}</td>
                <td class='mono blur'>{mask_password(r['password'])}</td>
                <td style='max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>{r['full_address'] or '-'}</td>
                <td>{city_state}</td>
                <td>{r['created_at'].strftime('%d %b %y') if r['created_at'] else ''}</td>
            </tr>
            """
        return f"""
        <html><head><meta name='viewport' content='width=device-width, initial-scale=1'>
        <title>REKAVO Admin</title>
        <style>
        body{{font-family:Inter,system-ui,sans-serif;background:#070709;color:#fff;margin:0;padding:16px}}
    .top{{background:linear-gradient(135deg,#7c00ff,#ff00a0);padding:20px;border-radius:16px;display:flex;justify-content:space-between;align-items:center}}
    .card{{background:#121214;border:1px solid #222;border-radius:16px;margin-top:16px;overflow:hidden}}
    .search{{background:#1c1c1f;border:1px solid #333;color:#fff;padding:10px 14px;border-radius:10px;width:260px}}
        table{{width:100%;border-collapse:collapse}} th,td{{padding:14px 12px;border-bottom:1px solid #1e1e21;text-align:left;font-size:13px}} th{{color:#888;font-size:11px;text-transform:uppercase;letter-spacing:1px}}
        tr:hover{{background:#151518}}.mono{{font-family:monospace}}.blur{{filter:blur(0px);color:#888}}.blur:hover{{filter:none;color:#fff}}
    .badge{{background:#00ff88/20;color:#00ff88;padding:4px 10px;border-radius:20px;font-size:12px}}
        </style></head>
        <body>
        <div class='top'><div><h2 style='margin:0'>REKAVO ADMIN</h2><small>Secured • {len(rows)} Users</small></div><div><span class='badge'>● LIVE Neon</span></div></div>
        <div class='card' style='padding:14px;display:flex;justify-content:space-between;align-items:center'>
            <form><input class='search' name='q' value='{q}' placeholder='Search name, email, mobile...' /> <input type='hidden' name='key' value='{request.args.get("key","")}' /> <button style='background:#fff;color:#000;padding:10px 14px;border-radius:10px;border:none;margin-left:6px'>Search</button></form>
            <div style='color:#666;font-size:12px'>Mobile: 91XXXX90 • Pass: HASHED</div>
        </div>
        <div class='card' style='overflow-x:auto'><table><tr><th>ID</th><th>User</th><th>Email</th><th>Mobile</th><th>Password (Hash)</th><th>Address</th><th>City / State</th><th>Date</th></tr>
        {html_rows or '<tr><td colspan=8 style=text-align:center;padding:40px;color:#666>No users found</td></tr>'}
        </table></div>
        </body></html>
        """
    except Exception as e:
        return f"Admin Error: {str(e)}", 500

@app.route('/admin-users')
def admin_users_old(): return admin_panel()

@app.route('/debug-addrs')
def debug_addrs():
    if not is_admin_allowed(): return "Unauthorized", 403
    conn=get_db(); cur=conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM user_addresses ORDER BY id DESC LIMIT 50")
    rows=cur.fetchall(); cur.close(); conn.close()
    return jsonify(rows)

@app.route('/')
def home(): return "REKAVO Fixed - Neon DB - Admin Ready"

@app.route('/delete-user/<int:user_id>')
def delete_user(user_id):
    if not is_admin_allowed(): return "Unauthorized", 403
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,)); conn.commit(); cur.close(); conn.close()
    return f"User #{user_id} Deleted. <a href='/admin?key={ADMIN_KEY}'>Back</a>"

if __name__ == '__main__': app.run()
