import os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_welcome_email(to_email, user_name="there"):
    try:
        gmail_user = os.getenv("GMAIL_USER")
        gmail_pass = os.getenv("GMAIL_APP_PASSWORD")
        if not gmail_user or not gmail_pass:
            print("Gmail creds missing")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Welcome to REKAVO Family, {user_name} 🖤"
        msg["From"] = f"REKAVO <{gmail_user}>"
        msg["To"] = to_email

        first_name = user_name.split()[0] if user_name else "there"

        html = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin:0;padding:0;background:#f4f4f4;font-family:Helvetica, Arial, sans-serif;">
        <div style="max-width:600px;margin:30px auto;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e5e5e5;">
            <div style="background:#000000;padding:32px 30px;text-align:center;">
                <h1 style="color:#ffffff;margin:0;font-size:32px;letter-spacing:6px;font-weight:900;">REKAVO</h1>
                <p style="color:#a3a3a3;margin:8px 0 0 0;font-size:11px;letter-spacing:3px;">PREMIUM STREETWEAR</p>
            </div>
            <div style="padding:40px 32px;">
                <h2 style="margin:0 0 10px 0;font-size:26px;color:#000;">Welcome, {first_name}! 🖤</h2>
                <p style="color:#333;font-size:15px;line-height:24px;margin:0;">Your account has been <b>successfully created</b>. You are now officially part of the REKAVO Family.</p>
                <div style="background:#f9f9f9;border:2px dashed #000;border-radius:14px;padding:24px;text-align:center;margin:32px 0;">
                    <p style="margin:0;font-size:11px;letter-spacing:2px;color:#666;font-weight:bold;">YOUR FIRST ORDER GIFT</p>
                    <h1 style="margin:12px 0;font-size:36px;letter-spacing:4px;color:#000;">WELCOME10</h1>
                    <p style="margin:0 0 8px 0;font-size:14px;color:#000;font-weight:bold;">Get 10% OFF on your first drop</p>
                    <p style="margin:0;font-size:12px;color:#888;">Valid for next 48 hours • No minimum order</p>
                </div>
                <p style="color:#555;font-size:14px;line-height:22px;">At REKAVO, we don't just sell clothes. We craft identity. Premium fabrics, limited drops, built for those who stand out.</p>
                <div style="text-align:center;margin:30px 0;">
                    <a href="https://rekavo.in" style="display:inline-block;background:#000;color:#fff;padding:16px 40px;text-decoration:none;border-radius:100px;font-weight:900;letter-spacing:1px;font-size:14px;">START SHOPPING →</a>
                </div>
            </div>
            <div style="background:#000;padding:20px;text-align:center;">
                <p style="color:#666;font-size:11px;margin:0;letter-spacing:1px;">© 2026 REKAVO • R2K INFOTECH • All Rights Reserved</p>
            </div>
        </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html, "html"))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, to_email, msg.as_string())
        server.quit()
        print(f"Welcome mail sent to {to_email}")
        return True
    except Exception as e:
        print(f"Welcome mail error: {e}")
        return False
