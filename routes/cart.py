from flask import request, jsonify
from app import app
from database import get_db

def get_conn_cur():
    conn = get_db()
    return conn, conn.cursor()

def safe_int(val):
    try: return int(val)
    except: return val

@app.route('/cart/get', methods=['GET'])
def cart_get():
    user_id = request.args.get('user_id')
    email = (request.args.get('email') or '').strip()
    conn, cur = get_conn_cur()
    try:
        rows = []
        if user_id:
            uid = safe_int(user_id)
            cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE user_id=%s AND price IS NOT NULL", (uid,))
            rows = cur.fetchall()
            if not rows and email:
                cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE email ILIKE %s AND price IS NOT NULL", (email,))
                rows = cur.fetchall()
        elif email:
            cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE email ILIKE %s AND price IS NOT NULL", (email,))
            rows = cur.fetchall()
        else:
            return jsonify([])

        cleaned_dict = {}
        for r in rows:
            pid, name, price, qty, image = r
            if not pid: continue
            if price is None: continue
            try: price = int(float(price))
            except: price = 0
            if price <=0: continue
            try: qty = int(qty or 1)
            except: qty = 1
            if qty < 1: qty = 1
            if qty > 5: qty = 5
            if pid in cleaned_dict:
                cleaned_dict[pid]['qty'] = min(5, cleaned_dict[pid]['qty'] + qty)
            else:
                cleaned_dict[pid] = {"product_id": pid, "name": name, "price": price, "qty": qty, "image": image}

        return jsonify(list(cleaned_dict.values()))
    except Exception as e:
        print(f"cart/get error: {e}")
        return jsonify([])
    finally:
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass

@app.route('/cart/add', methods=['POST'])
def cart_add():
    d=request.get_json() or {}
    user_id = d.get('user_id')
    email = (d.get('email') or '').lower().strip()
    product_id = d.get('product_id')
    if not product_id: return jsonify({"success": False, "error": "no product_id"}), 400

    req_qty = d.get('qty', 1)
    try: req_qty = int(req_qty)
    except: req_qty = 1
    if req_qty <1: req_qty=1
    if req_qty >5: req_qty=5

    # price validation - seller dashboard se bhi null aaya toh 0 nahi, error dega
    price = d.get('price')
    try: price = int(float(price))
    except: return jsonify({"success": False, "error": "invalid price"}), 400
    if price <=0: return jsonify({"success": False, "error": "price zero"}), 400

    conn, cur = get_conn_cur()
    try:
        if user_id:
            uid=safe_int(user_id)
            cur.execute("SELECT qty FROM carts WHERE user_id=%s AND product_id=%s", (uid, product_id))
            r=cur.fetchone()
            if r:
                cur.execute("UPDATE carts SET qty=%s, name=%s, price=%s, image=%s WHERE user_id=%s AND product_id=%s", (min(5,(r[0] or 1)+req_qty), d.get('name'), price, d.get('image',''), uid, product_id))
            else:
                cur.execute("INSERT INTO carts (user_id, email, product_id, name, price, qty, image) VALUES (%s,%s,%s,%s,%s,%s,%s)", (uid, email, product_id, d.get('name'), price, req_qty, d.get('image','')))
        else:
            if not email: return jsonify({"success": False, "error": "no user"}), 400
            cur.execute("SELECT qty FROM carts WHERE email ILIKE %s AND product_id=%s", (email, product_id))
            r=cur.fetchone()
            if r:
                cur.execute("UPDATE carts SET qty=%s, name=%s, price=%s, image=%s WHERE email ILIKE %s AND product_id=%s", (min(5,(r[0] or 1)+req_qty), d.get('name'), price, d.get('image',''), email, product_id))
            else:
                cur.execute("INSERT INTO carts (user_id, email, product_id, name, price, qty, image) VALUES (%s,%s,%s,%s,%s,%s,%s)", (None, email, product_id, d.get('name'), price, req_qty, d.get('image','')))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        print(f"cart/add error: {e}")
        return jsonify({"success": False}), 500
    finally:
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass

@app.route('/cart/remove', methods=['POST'])
def cart_remove():
    d=request.get_json() or {}
    conn,cur=get_conn_cur()
    try:
        pid = d.get('product_id')
        if not pid: return jsonify({"success": False}), 400
        if d.get('user_id'):
            cur.execute("DELETE FROM carts WHERE user_id=%s AND product_id=%s", (safe_int(d.get('user_id')), pid))
        else:
            cur.execute("DELETE FROM carts WHERE email ILIKE %s AND product_id=%s", (d.get('email','').lower().strip(), pid))
        conn.commit()
        return jsonify({"success": True})
    finally:
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass

@app.route('/cart/clear', methods=['POST'])
def cart_clear():
    d=request.get_json() or {}
    conn,cur=get_conn_cur()
    try:
        if d.get('user_id'):
            cur.execute("DELETE FROM carts WHERE user_id=%s", (safe_int(d.get('user_id')),))
        else:
            cur.execute("DELETE FROM carts WHERE email ILIKE %s", (d.get('email','').lower().strip(),))
        conn.commit()
        return jsonify({"success": True})
    finally:
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass
