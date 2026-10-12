from flask import request, jsonify
from app import app
from database import get_db

def get_conn_cur():
    conn = get_db()
    return conn, conn.cursor()

def safe_int(val):
    try:
        return int(val)
    except:
        return val

# ========= CART GET - MAIN FIX YAHI HAI =========
@app.route('/cart/get', methods=['GET'])
def cart_get():
    user_id = request.args.get('user_id')
    email = (request.args.get('email') or '').strip().lower()
    conn, cur = get_conn_cur()
    try:
        if user_id:
            uid = safe_int(user_id)
            # INT wale user_id ke liye sirf user_id se search - sabse fast
            if isinstance(uid, int):
                cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE user_id=%s", (uid,))
            else:
                # String wale ke liye ILIKE use kiya, LOWER hataya
                if email:
                    cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE user_id=%s OR email ILIKE %s", (user_id, email))
                else:
                    cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE user_id=%s", (user_id,))
        else:
            if not email:
                return jsonify([])
            # LOWER hataya, ILIKE lagaya - Index use hoga
            cur.execute("SELECT product_id, name, price, qty, image FROM carts WHERE email ILIKE %s", (email,))

        rows = cur.fetchall()
        cleaned_dict = {}
        for r in rows:
            pid, name, price, qty, image = r
            if not pid: continue
            if qty is None: qty = 1
            try: qty = int(qty)
            except: qty = 1
            if qty > 10: qty = 1
            if qty > 5: qty = 5
            if qty < 1: qty = 1

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
    d=request.get_json(); user_id = d.get('user_id'); email = (d.get('email') or '').lower(); product_id = d.get('product_id')
    if not product_id: return jsonify({"success": False, "error": "product_id required"}), 400
    req_qty = d.get('qty', 1)
    try: req_qty = int(req_qty)
    except: req_qty = 1
    if req_qty > 5 or req_qty < 1: req_qty = 1
    conn, cur = get_conn_cur()
    try:
        if user_id:
            uid = safe_int(user_id)
            if isinstance(uid, int):
                cur.execute("SELECT qty FROM carts WHERE user_id=%s AND product_id=%s", (uid, product_id)); r=cur.fetchone()
                if r:
                    old_qty = r[0] or 1
                    if old_qty > 10: old_qty = 0
                    new_qty = min(5, old_qty + req_qty)
                    cur.execute("UPDATE carts SET qty=%s, name=%s, price=%s, image=%s WHERE user_id=%s AND product_id=%s", (new_qty, d.get('name'), d.get('price'), d.get('image',''), uid, product_id))
                else: cur.execute("INSERT INTO carts (user_id, email, product_id, name, price, qty, image) VALUES (%s,%s,%s,%s,%s,%s,%s)", (uid, email, product_id, d.get('name'), d.get('price'), req_qty, d.get('image','')))
            else:
                cur.execute("SELECT qty FROM carts WHERE user_id=%s AND product_id=%s", (user_id, product_id)); r=cur.fetchone()
                if r:
                    old_qty = r[0] or 1
                    if old_qty > 10: old_qty = 0
                    new_qty = min(5, old_qty + req_qty)
                    cur.execute("UPDATE carts SET qty=%s WHERE user_id=%s AND product_id=%s", (new_qty, user_id, product_id))
                else: cur.execute("INSERT INTO carts (user_id, email, product_id, name, price, qty, image) VALUES (%s,%s,%s,%s,%s,%s,%s)", (user_id, email, product_id, d.get('name'), d.get('price'), req_qty, d.get('image','')))
        else:
            if not email: return jsonify({"success": False}), 400
            cur.execute("SELECT qty FROM carts WHERE email ILIKE %s AND product_id=%s", (email, product_id)); r=cur.fetchone()
            if r:
                old_qty = r[0] or 1
                if old_qty > 10: old_qty = 0
                new_qty = min(5, old_qty + req_qty)
                cur.execute("UPDATE carts SET qty=%s WHERE email ILIKE %s AND product_id=%s", (new_qty, email, product_id))
            else: cur.execute("INSERT INTO carts (user_id, email, product_id, name, price, qty, image) VALUES (%s,%s,%s,%s,%s,%s,%s)", (None, email, product_id, d.get('name'), d.get('price'), req_qty, d.get('image','')))
        conn.commit(); return jsonify({"success": True})
    except Exception as e:
        print(f"cart/add error: {e}"); return jsonify({"success": False, "error": str(e)}), 500
    finally:
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass

@app.route('/cart/remove', methods=['POST'])
def cart_remove():
    d=request.get_json(); user_id = d.get('user_id'); email = (d.get('email') or '').lower()
    conn, cur = get_conn_cur()
    try:
        if user_id:
            uid = safe_int(user_id)
            cur.execute("DELETE FROM carts WHERE user_id=%s AND product_id=%s", (uid, d['product_id']))
        else: cur.execute("DELETE FROM carts WHERE email ILIKE %s AND product_id=%s", (email, d['product_id']))
        conn.commit(); return jsonify({"success": True})
    finally:
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass

@app.route('/cart/clear', methods=['POST'])
def cart_clear():
    d=request.get_json(); user_id = d.get('user_id'); email = (d.get('email') or '').lower()
    conn, cur = get_conn_cur()
    try:
        if user_id:
            uid = safe_int(user_id)
            cur.execute("DELETE FROM carts WHERE user_id=%s", (uid,))
        else: cur.execute("DELETE FROM carts WHERE email ILIKE %s", (email,))
        conn.commit(); return jsonify({"success": True})
    finally:
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass

# Wishlist me bhi same fix laga diya
@app.route('/wishlist/get', methods=['GET'])
def wishlist_get():
    user_id = request.args.get('user_id'); email=(request.args.get('email') or '').lower()
    conn, cur = get_conn_cur()
    try:
        if user_id:
            uid = safe_int(user_id)
            cur.execute("SELECT product_id, name, price, image FROM wishlists WHERE user_id=%s", (uid,))
        else: cur.execute("SELECT product_id, name, price, image FROM wishlists WHERE email ILIKE %s", (email,))
        rows=cur.fetchall(); return jsonify([{"product_id": r[0], "name": r[1], "price": r[2], "image": r[3]} for r in rows])
    finally:
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass

@app.route('/wishlist/toggle', methods=['POST'])
def wishlist_toggle():
    d=request.get_json(); user_id = d.get('user_id'); email=(d.get('email') or '').lower()
    conn, cur = get_conn_cur()
    try:
        uid = safe_int(user_id) if user_id else None
        if user_id:
            cur.execute("SELECT id FROM wishlists WHERE user_id=%s AND product_id=%s", (uid, d['product_id']))
        else: cur.execute("SELECT id FROM wishlists WHERE email ILIKE %s AND product_id=%s", (email, d['product_id']))
        r=cur.fetchone()
        if r:
            if user_id: cur.execute("DELETE FROM wishlists WHERE user_id=%s AND product_id=%s", (uid, d['product_id']))
            else: cur.execute("DELETE FROM wishlists WHERE email ILIKE %s AND product_id=%s", (email, d['product_id']))
            action="removed"
        else:
            cur.execute("INSERT INTO wishlists (user_id, email, product_id, name, price, image) VALUES (%s,%s,%s,%s,%s,%s)", (uid, email, d['product_id'], d['name'], d['price'], d.get('image',''))); action="added"
        conn.commit(); return jsonify({"success": True, "action": action})
    finally:
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass
