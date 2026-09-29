@app.route('/admin-users')
def admin_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, password, created_at FROM users ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()

    total_users = len(rows)

    html_rows = ""
    for r in rows:
        html_rows += f"""
        <tr>
            <td>#{r[0]}</td>
            <td><div class='user-flex'><div class='avatar'>{r[1][0].upper() if r[1] else 'U'}</div><div><b>{r[1]}</b><br><small>ID: {r[0]}</small></div></div></td>
            <td>{r[2]}</td>
            <td><span class='pass-blur'>{r[3]}</span></td>
            <td>{r[4].strftime('%d %b, %Y')}</td>
            <td><span class='status active'>Active</span></td>
        </tr>
        """

    return f"""
    <html>
    <head><meta name='viewport' content='width=device-width, initial-scale=1.0'><title>REKAVO Admin</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap');
        body{{font-family:'Poppins',sans-serif; background:#f4f6f9; margin:0; padding:20px;}}
       .header{{background: linear-gradient(135deg, #6e00ff, #ff00a0); color:white; padding:25px; border-radius:20px; display:flex; justify-content:space-between; align-items:center;}}
       .stats{{display:grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr)); gap:15px; margin:20px 0;}}
       .card{{background:white; padding:20px; border-radius:15px; box-shadow:0 5px 15px rgba(0,0,0,0.05);}}
       .card h2{{margin:5px 0; font-size:28px;}}
       .table-box{{background:white; border-radius:15px; padding:20px; box-shadow:0 5px 15px rgba(0,0,0,0.05); overflow-x:auto;}}
        table{{width:100%; border-collapse:collapse;}}
        th{{text-align:left; color:#888; font-size:13px; padding:15px 10px; border-bottom:2px solid #f0f0f0;}}
        td{{padding:15px 10px; border-bottom:1px solid #f0f0f0; font-size:14px;}}
       .user-flex{{display:flex; align-items:center; gap:10px;}}
       .avatar{{width:35px; height:35px; background:#6e00ff; color:white; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:600;}}
       .status.active{{background:#e6f9ec; color:#00b831; padding:5px 12px; border-radius:20px; font-size:12px; font-weight:600;}}
       .pass-blur{{filter: blur(4px); transition:0.3s; cursor:pointer;}}.pass-blur:hover{{filter: blur(0px);}}
    </style>
    </head>
    <body>
        <div class='header'>
            <div><h1 style='margin:0;'>REKAVO Admin Panel</h1><p style='margin:0; opacity:0.9;'>Welcome back, Boss 🔥</p></div>
            <div style='font-size:14px;'>rekavo.in • Live</div>
        </div>
        <div class='stats'>
            <div class='card'><small>TOTAL USERS</small><h2>{total_users}</h2><span style='color:green;'>▲ 100% Real Hosting</span></div>
            <div class='card'><small>TOTAL ORDERS</small><h2>0</h2><span>Abhi aane wale hain</span></div>
            <div class='card'><small>REVENUE</small><h2>₹0</h2><span>Next Update me</span></div>
        </div>
        <div class='table-box'>
            <h3>All Customers</h3>
            <table>
                <tr><th>ID</th><th>CUSTOMER</th><th>EMAIL</th><th>PASSWORD</th><th>JOINED</th><th>STATUS</th></tr>
                {html_rows if html_rows else "<tr><td colspan=6 style='text-align:center; padding:40px;'>Koi user nahi hai abhi, pehla register ka intezar hai...</td></tr>"}
            </table>
        </div>
    </body>
    </html>
    """
