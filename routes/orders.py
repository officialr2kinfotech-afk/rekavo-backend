from flask import request, jsonify
from app import app
from database import get_db
import random

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
