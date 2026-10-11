from flask import request, jsonify
from app import app
from database import get_db

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
