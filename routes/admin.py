from flask import request, jsonify
from app import app
from database import get_db, is_admin_allowed, mask_mobile, mask_password, ADMIN_KEY
from psycopg2.extras import RealDictCursor

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

@app.route('/delete-user/<int:user_id>')
def delete_user(user_id):
    if not is_admin_allowed(): return "Unauthorized", 403
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,)); conn.commit(); cur.close(); conn.close()
    return f"User #{user_id} Deleted. <a href='/admin?key={ADMIN_KEY}'>Back</a>"
