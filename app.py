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
    cur.execute("CREATE TABLE IF NOT EXISTS carts (id SERIAL PRIMARY KEY, user_id INTEGER, email VARCHAR(255), product_id VARCHAR(255), name TEXT, price INTEGER, qty INTEGER DEFAULT 1, image TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS wishlists (id SERIAL PRIMARY KEY, user_id INTEGER, email VARCHAR(255), product_id VARCHAR(255), name TEXT, price INTEGER, image TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS user_addresses (id SERIAL PRIMARY KEY, user_id INTEGER, email VARCHAR(255), full_name VARCHAR(255), phone VARCHAR(20), pincode VARCHAR(20), full_address TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("CREATE TABLE IF NOT EXISTS user_orders (id SERIAL PRIMARY KEY, user_id INTEGER, email VARCHAR(255), order_id VARCHAR(100), product_name TEXT, amount INTEGER, status VARCHAR(50) DEFAULT 'Pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute("ALTER TABLE carts ADD COLUMN IF NOT EXISTS user_id INTEGER;")
    cur.execute("ALTER TABLE wishlists ADD COLUMN IF NOT EXISTS user_id INTEGER;")
    cur.execute("ALTER TABLE user_addresses ADD COLUMN IF NOT EXISTS user_id INTEGER;")
    cur.execute("ALTER TABLE user_orders ADD COLUMN IF NOT EXISTS user_id INTEGER;")
    conn.commit()
    cur.close()
    conn.close()
    return "REKAVO FIXED - Neon DB Ready with user_id"

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
    login_text = data.get('email','').strip().lower()
    password = data.get('password')
    if not login_text or not password:
        return jsonify({"success": False, "error": "Email/Phone and password required"}), 400
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id, name, phone, email, password FROM users WHERE LOWER(email)=%s OR phone=%s", (login_text, login_text))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        return jsonify({"success": False, "error": "User not found"}), 404
    if row[4]!= password:
        return jsonify({"success": False, "error": "Wrong password"}), 400
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

# ========== CART - FIXED (172 BUG KHATAM) ==========
@app.route('/cart/get', methods=['GET'])
def cart_get():
    user_id = request.args.get('user_id')
    email = request.args.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    try:
        if user_id:
            # user_id int ho sakta hai, safe cast
            try:
                uid_int = int(user_id)
                cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE user_id=%s", (uid_int,))
            except:
                cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE user_id=%s OR LOWER(email)=%s", (user_id, email))
        else:
            if not email:
                cur.close(); conn.close()
                return jsonify([])
            cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE LOWER(email)=%s", (email,))
        rows=cur.fetchall()

        # CLEANING: 171 ko 1 bana do, duplicate merge
        cleaned_dict = {}
        for r in rows:
            pid, name, price, qty, image = r
            if not pid:
                continue
            # 171 wala bug fix
            if qty is None:
                qty = 1
            if qty > 10:
                qty = 1
            if qty > 5:
                qty = 5
            if pid in cleaned_dict:
                # merge but max 5
                old_qty = cleaned_dict[pid]['qty']
                new_qty = min(5, old_qty + qty)
                cleaned_dict[pid]['qty'] = new_qty
            else:
                cleaned_dict[pid] = {"product_id": pid, "name": name, "price": price, "qty": qty, "image": image}

        result = list(cleaned_dict.values())
        cur.close(); conn.close()
        return jsonify(result)
    except Exception as e:
        print(e)
        cur.close(); conn.close()
        return jsonify([])

@app.route('/cart/add', methods=['POST'])
def cart_add():
    d=request.get_json()
    user_id = d.get('user_id')
    email = (d.get('email') or '').lower()
    product_id = d.get('product_id')
    if not product_id:
        return jsonify({"success": False, "error": "product_id required"}), 400

    # qty ko limit karo
    req_qty = d.get('qty', 1)
    try:
        req_qty = int(req_qty)
    except:
        req_qty = 1
    if req_qty > 5 or req_qty < 1:
        req_qty = 1

    conn=get_db(); cur=conn.cursor()
    try:
        # existing check - user_id se
        if user_id:
            try:
                uid_int = int(user_id)
                cur.execute("SELECT qty FROM carts WHERE user_id=%s AND product_id=%s", (uid_int, product_id))
                r=cur.fetchone()
                if r:
                    old_qty = r[0] or 1
                    # agar old 171 hai to reset
                    if old_qty > 10:
                        old_qty = 0
                    new_qty = old_qty + req_qty
                    if new_qty > 5:
                        new_qty = 5
                    cur.execute("UPDATE carts SET qty=%s, name=%s, price=%s, image=%s WHERE user_id=%s AND product_id=%s", (new_qty, d.get('name'), d.get('price'), d.get('image',''), uid_int, product_id))
                else:
                    cur.execute("INSERT INTO carts (user_id, email, product_id, name, price, qty, image) VALUES (%s,%s,%s,%s,%s,%s,%s)", (uid_int, email, product_id, d.get('name'), d.get('price'), req_qty, d.get('image','')))
            except Exception as e:
                # fallback if user_id not int
                cur.execute("SELECT qty FROM carts WHERE user_id=%s AND product_id=%s", (user_id, product_id))
                r=cur.fetchone()
                if r:
                    old_qty = r[0] or 1
                    if old_qty > 10: old_qty = 0
                    new_qty = min(5, old_qty + req_qty)
                    cur.execute("UPDATE carts SET qty=%s WHERE user_id=%s AND product_id=%s", (new_qty, user_id, product_id))
                else:
                    cur.execute("INSERT INTO carts (user_id, email, product_id, name, price, qty, image) VALUES (%s,%s,%s,%s,%s,%s,%s)", (user_id, email, product_id, d.get('name'), d.get('price'), req_qty, d.get('image','')))
        else:
            if not email:
                cur.close(); conn.close()
                return jsonify({"success": False}), 400
            cur.execute("SELECT qty FROM carts WHERE LOWER(email)=%s AND product_id=%s", (email, product_id))
            r=cur.fetchone()
            if r:
                old_qty = r[0] or 1
                if old_qty > 10: old_qty = 0
                new_qty = min(5, old_qty + req_qty)
                cur.execute("UPDATE carts SET qty=%s WHERE LOWER(email)=%s AND product_id=%s", (new_qty, email, product_id))
            else:
                cur.execute("INSERT INTO carts (user_id, email, product_id, name, price, qty, image) VALUES (%s,%s,%s,%s,%s,%s,%s)", (None, email, product_id, d.get('name'), d.get('price'), req_qty, d.get('image','')))

        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print(f"cart/add error: {e}")
        cur.close(); conn.close()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/cart/remove', methods=['POST'])
def cart_remove():
    d=request.get_json()
    user_id = d.get('user_id')
    email = d.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    if user_id:
        try:
            uid_int = int(user_id)
            cur.execute("DELETE FROM carts WHERE user_id=%s AND product_id=%s", (uid_int, d['product_id']))
        except:
            cur.execute("DELETE FROM carts WHERE user_id=%s AND product_id=%s", (user_id, d['product_id']))
    else:
        cur.execute("DELETE FROM carts WHERE LOWER(email)=%s AND product_id=%s", (email, d['product_id']))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True})

@app.route('/cart/clear', methods=['POST'])
def cart_clear():
    d=request.get_json()
    user_id = d.get('user_id')
    email = d.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    if user_id:
        try:
            uid_int = int(user_id)
            cur.execute("DELETE FROM carts WHERE user_id=%s", (uid_int,))
        except:
            cur.execute("DELETE FROM carts WHERE user_id=%s", (user_id,))
    else:
        cur.execute("DELETE FROM carts WHERE LOWER(email)=%s", (email,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True})

# FIX CART - ek baar 172 ko saaf karne ke liye
@app.route('/cart/fix', methods=['POST'])
def cart_fix():
    d=request.get_json()
    user_id = d.get('user_id')
    email = d.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    if user_id:
        try: uid_int = int(user_id)
        except: uid_int = user_id
        cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE user_id=%s", (uid_int,))
    else:
        cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE LOWER(email)=%s", (email,))
    rows=cur.fetchall()
    # merge
    merged={}
    for r in rows:
        pid=r[0]
        qty=r[3] or 1
        if qty>10: qty=1
        if qty>5: qty=5
        if pid in merged:
            merged[pid]=(merged[pid][0], merged[pid][1], merged[pid][2], min(5, merged[pid][3]+qty), merged[pid][4])
        else:
            merged[pid]=(r[0], r[1], r[2], qty, r[4])
    # delete and re-insert
    if user_id:
        cur.execute("DELETE FROM carts WHERE user_id=%s", (uid_int,))
        for v in merged.values():
            cur.execute("INSERT INTO carts (user_id, email, product_id, name, price, qty, image) VALUES (%s,%s,%s,%s,%s,%s,%s)", (uid_int, email, v[0], v[1], v[2], v[3], v[4]))
    else:
        cur.execute("DELETE FROM carts WHERE LOWER(email)=%s", (email,))
        for v in merged.values():
            cur.execute("INSERT INTO carts (user_id, email, product_id, name, price, qty, image) VALUES (%s,%s,%s,%s,%s,%s,%s)", (None, email, v[0], v[1], v[2], v[3], v[4]))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"fixed": list(merged.values())})

@app.route('/wishlist/get', methods=['GET'])
def wishlist_get():
    user_id = request.args.get('user_id')
    email=request.args.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    if user_id:
        try:
            uid_int=int(user_id)
            cur.execute("SELECT product_id, name, price, image FROM wishlists WHERE user_id=%s", (uid_int,))
        except:
            cur.execute("SELECT product_id, name, price, image FROM wishlists WHERE user_id=%s", (user_id,))
    else:
        cur.execute("SELECT product_id, name, price, image FROM wishlists WHERE LOWER(email)=%s", (email,))
    rows=cur.fetchall(); cur.close(); conn.close()
    return jsonify([{"product_id": r[0], "name": r[1], "price": r[2], "image": r[3]} for r in rows])

@app.route('/wishlist/toggle', methods=['POST'])
def wishlist_toggle():
    d=request.get_json()
    user_id = d.get('user_id')
    email=d.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    if user_id:
        try:
            uid_int=int(user_id)
            cur.execute("SELECT id FROM wishlists WHERE user_id=%s AND product_id=%s", (uid_int, d['product_id']))
        except:
            cur.execute("SELECT id FROM wishlists WHERE user_id=%s AND product_id=%s", (user_id, d['product_id']))
    else:
        cur.execute("SELECT id FROM wishlists WHERE LOWER(email)=%s AND product_id=%s", (email, d['product_id']))
    r=cur.fetchone()
    if r:
        if user_id:
            try: cur.execute("DELETE FROM wishlists WHERE user_id=%s AND product_id=%s", (int(user_id), d['product_id']))
            except: cur.execute("DELETE FROM wishlists WHERE user_id=%s AND product_id=%s", (user_id, d['product_id']))
        else:
            cur.execute("DELETE FROM wishlists WHERE LOWER(email)=%s AND product_id=%s", (email, d['product_id']))
        action="removed"
    else:
        try: uid_int=int(user_id) if user_id else None
        except: uid_int=user_id
        cur.execute("INSERT INTO wishlists (user_id, email, product_id, name, price, image) VALUES (%s,%s,%s,%s,%s,%s)", (uid_int, email, d['product_id'], d['name'], d['price'], d.get('image','')))
        action="added"
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True, "action": action})

@app.route('/orders/get', methods=['GET'])
def orders_get():
    user_id = request.args.get('user_id')
    email=request.args.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    if user_id:
        try:
            uid_int=int(user_id)
            cur.execute("SELECT order_id, product_name, amount, status, created_at FROM user_orders WHERE user_id=%s ORDER BY id DESC", (uid_int,))
        except:
            cur.execute("SELECT order_id, product_name, amount, status, created_at FROM user_orders WHERE user_id=%s ORDER BY id DESC", (user_id,))
    else:
        cur.execute("SELECT order_id, product_name, amount, status, created_at FROM user_orders WHERE LOWER(email)=%s ORDER BY id DESC", (email,))
    rows=cur.fetchall(); cur.close(); conn.close()
    return jsonify([{"order_id": r[0], "product_name": r[1], "amount": r[2], "status": r[3], "date": str(r[4])} for r in rows])

@app.route('/place-order', methods=['POST'])
def place_order():
    d=request.get_json()
    user_id = d.get('user_id')
    email = (d.get('email') or '').lower()
    # checkout wala naya format handle
    product_name = d.get('product_name') or d.get('full_name') or 'REKAVO Order'
    if d.get('items'):
        # items array hai to first item ka naam + count
        items = d.get('items')
        if isinstance(items, list) and len(items)>0:
            product_name = items[0].get('name','REKAVO Order')
            if len(items)>1:
                product_name = f"{product_name} + {len(items)-1} more"
    amount = d.get('amount') or d.get('total') or 0
    try: amount = int(amount)
    except: amount = 0

    conn=get_db(); cur=conn.cursor()
    order_id = d.get('order_id') or f"REKAVO{random.randint(10000,99999)}"
    try:
        uid_int = int(user_id) if user_id else None
    except:
        uid_int = user_id
    cur.execute("INSERT INTO user_orders (user_id, email, order_id, product_name, amount, status) VALUES (%s,%s,%s,%s,%s,%s)", (uid_int, email, order_id, product_name, amount, 'Placed'))
    if user_id:
        try: cur.execute("DELETE FROM carts WHERE user_id=%s", (int(user_id),))
        except: cur.execute("DELETE FROM carts WHERE user_id=%s", (user_id,))
    else:
        if email:
            cur.execute("DELETE FROM carts WHERE LOWER(email)=%s", (email,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True, "order_id": order_id})

# ALIAS for checkout.html - ye missing tha isliye order nahi lag raha tha
@app.route('/orders/add', methods=['POST'])
def orders_add():
    return place_order()

@app.route('/orders/create', methods=['POST'])
def orders_create():
    return place_order()

@app.route('/address/get', methods=['GET'])
def address_get():
    user_id = request.args.get('user_id')
    email=request.args.get('email','').lower()
    conn=get_db(); cur=conn.cursor()
    if user_id:
        try:
            cur.execute("SELECT id, full_name, phone, pincode, full_address FROM user_addresses WHERE user_id=%s ORDER BY id DESC", (int(user_id),))
        except:
            cur.execute("SELECT id, full_name, phone, pincode, full_address FROM user_addresses WHERE user_id=%s ORDER BY id DESC", (user_id,))
    else:
        cur.execute("SELECT id, full_name, phone, pincode, full_address FROM user_addresses WHERE LOWER(email)=%s ORDER BY id DESC", (email,))
    rows=cur.fetchall(); cur.close(); conn.close()
    return jsonify([{"id": r[0], "full_name": r[1], "phone": r[2], "pincode": r[3], "full_address": r[4]} for r in rows])

@app.route('/address/add', methods=['POST'])
def address_add():
    d=request.get_json()
    user_id = d.get('user_id')
    email=(d.get('email') or '').lower()
    conn=get_db(); cur=conn.cursor()
    try: uid_int=int(user_id) if user_id else None
    except: uid_int=user_id
    cur.execute("INSERT INTO user_addresses (user_id, email, full_name, phone, pincode, full_address) VALUES (%s,%s,%s,%s,%s,%s)", (uid_int, email, d.get('full_name'), d.get('phone'), d.get('pincode'), d.get('full_address')))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True})

@app.route('/address/delete', methods=['POST'])
def address_delete():
    d=request.get_json()
    conn=get_db(); cur=conn.cursor()
    cur.execute("DELETE FROM user_addresses WHERE id=%s", (d.get('id'),))
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
def home(): return "REKAVO Fixed - Neon DB - Cross Device Ready - 172 Bug Fixed"

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

if __name__ == '__main__':
    app.run()
