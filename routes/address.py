from flask import request, jsonify
from app import app
from database import get_db
from psycopg2.extras import RealDictCursor

# Token import - dono setup ke liye safe
try:
    from routes.auth import token_required
except:
    from auth import token_required

@app.route('/address/get', methods=['GET', 'OPTIONS'])
@token_required
def address_get(current_user):
    try:
        user_id = current_user.get('id') or current_user.get('user_id')
        email = (current_user.get('email') or '').lower().strip()
        
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Sirf isi user ka address aayega, token se verify hoke - yahi 100% security hai
        cur.execute("""
            SELECT id, user_id, email, full_name, phone, alt_phone, pincode, full_address, city, state, locality, line1, line2, landmark, type 
            FROM user_addresses 
            WHERE user_id = %s OR LOWER(email) = %s
            ORDER BY id DESC
        """, (user_id, email))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        print("ADDRESS GET ERROR:", e)
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/address/add', methods=['POST', 'OPTIONS'])
@token_required
def address_add(current_user):
    try:
        d = request.get_json() or {}
        user_id = current_user.get('id') or current_user.get('user_id')
        email = (current_user.get('email') or '').lower().strip()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_addresses (user_id, email, full_name, phone, alt_phone, pincode, full_address, city, state, locality, line1, line2, landmark, type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, email,
            d.get('full_name'), d.get('phone'), d.get('alt_phone'),
            d.get('pincode'), d.get('full_address'), d.get('city'),
            d.get('state'), d.get('locality'), d.get('line1'),
            d.get('line2'), d.get('landmark'), d.get('type', 'Home')
        ))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Address added"})
    except Exception as e:
        print("ADDRESS ADD ERROR:", e)
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/address/update', methods=['POST', 'PUT', 'OPTIONS'])
@token_required
def address_update(current_user):
    try:
        d = request.get_json() or {}
        addr_id = d.get('id') or d.get('address_id')
        if not addr_id:
            return jsonify({"success": False, "error": "id missing"}), 400

        user_id = current_user.get('id') or current_user.get('user_id')
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE user_addresses SET
                full_name=%s, phone=%s, alt_phone=%s, pincode=%s, full_address=%s,
                city=%s, state=%s, locality=%s, line1=%s, line2=%s, landmark=%s, type=%s
            WHERE id=%s AND user_id=%s
        """, (
            d.get('full_name'), d.get('phone'), d.get('alt_phone'),
            d.get('pincode'), d.get('full_address'), d.get('city'),
            d.get('state'), d.get('locality'), d.get('line1'),
            d.get('line2'), d.get('landmark'), d.get('type', 'Home'),
            addr_id, user_id
        ))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Address updated"})
    except Exception as e:
        print("ADDRESS UPDATE ERROR:", e)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/address/delete', methods=['POST', 'DELETE', 'OPTIONS'])
@token_required
def address_delete(current_user):
    try:
        d = request.get_json() or {}
        addr_id = d.get('id') or d.get('address_id')
        if not addr_id:
            return jsonify({"success": False, "error": "id missing"}), 400

        user_id = current_user.get('id') or current_user.get('user_id')
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM user_addresses WHERE id=%s AND user_id=%s", (addr_id, user_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Address deleted"})
    except Exception as e:
        print("DELETE ERR:", e)
        return jsonify({"success": False, "error": str(e)}), 500
