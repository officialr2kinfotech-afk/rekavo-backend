from flask import request, jsonify
from app import app
from database import get_db
from psycopg2.extras import RealDictCursor
from auth import token_required  # 1. Bas ye line add ki

@app.route('/address/get', methods=['GET'])
@token_required  # 2. Bas ye line add ki - isse bina login koi address nahi dekh payega
def address_get(current_user):
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
            d = request.get_json() or {}
            email = (d.get('email') or '').lower().strip()
            try:
                uid_int = int(d.get('user_id')) if d.get('user_id') else None
            except:
                uid_int = None

            conn = get_db()
            cur = conn.cursor()

            cols = ["user_id","email","full_name","phone","alt_phone","pincode","full_address","city","state","locality","line1","line2","landmark","type"]
            vals = [
                uid_int,
                email,
                d.get('full_name'),
                d.get('phone'),
                d.get('alt_phone'),
                d.get('pincode'),
                d.get('full_address') or d.get('line1') or 'Test Address',
                d.get('city'),
                d.get('state'),
                d.get('locality'),
                d.get('line1'),
                d.get('line2'),
                d.get('landmark'),
                d.get('type','Home')
            ]

            # auto placeholders, kabhi mismatch nahi hoga
            placeholders = ", ".join(["%s"] * len(cols))
            sql = f"INSERT INTO user_addresses ({', '.join(cols)}) VALUES ({placeholders})"
            
            cur.execute(sql, tuple(vals))
            conn.commit()
            cur.close()
            conn.close()
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
