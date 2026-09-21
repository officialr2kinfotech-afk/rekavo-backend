from flask import Flask, request, jsonify
from flask_cors import CORS
import os, random, time
from resend import Resend

app = Flask(__name__)
CORS(app)

# Key Render se aayegi, yaha likhne ki zarurat nahi
resend = Resend(api_key=os.environ.get('RESEND_API_KEY'))

otp_storage = {}

@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get('email')
    otp = str(random.randint(100000, 999999))
    otp_storage[email] = {'otp': otp, 'time': time.time()}

    resend.emails.send({
        "from": "REKAVO <otp@rekavo.in>",
        "to": email,
        "subject": f"{otp} is your REKAVO OTP",
        "html": f"<h1>{otp}</h1><p>Your REKAVO OTP. Valid for 5 minutes.</p>"
    })
    return jsonify({"success": True})

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    user_otp = data.get('otp')

    if email not in otp_storage:
        return jsonify({"success": False, "message": "OTP not sent"})

    if time.time() - otp_storage[email]['time'] > 300:
        return jsonify({"success": False, "message": "OTP expired"})

    if otp_storage[email]['otp'] == user_otp:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Wrong OTP"})

@app.route('/')
def home():
    return "REKAVO Perfect OTP Backend Running"

if __name__ == '__main__':
    app.run()