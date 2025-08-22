import re
from flask import Flask, request, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from datetime import datetime
import os

# === LINE Bot 設定 ===
line_bot_api = LineBotApi('AvZds3TWRGU0Dkv8s4ayWXtv5oCELiYs9jlKn0/B9Vvzfo9xoVYT6ufMut641La0RRPMiyCmqQx+j2Hmir8ol0x0yfwce6GFtpGSP1a4OYee4PlonyZ1VCZRI3HaKkTF5IhN/C8vrNabg67skELNqgdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('f6690a74c4ccbf530d157674c4ecab05')

# === Flask 設定 ===
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://project:Y7TuzgqXiJ4w64rSiIVLjOm3LQqw1nwk@dpg-d2is9imr433s73e6l2s0-a.singapore-postgres.render.com/project_fh7i"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# === 資料庫模型 ===
class TemperatureHumidity(db.Model):
    __tablename__ = 'temperature_humidity'
    id = db.Column(db.Integer, primary_key=True)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class ControlCommand(db.Model):
    __tablename__ = 'control_command'
    id = db.Column(db.Integer, primary_key=True)
    command = db.Column(db.String(10), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

with app.app_context():
    db.create_all()

# === 儲存感測數據 ===
def save_to_database(temperature, humidity):
    new_data = TemperatureHumidity(temperature=temperature, humidity=humidity)
    try:
        db.session.add(new_data)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error saving data: {e}")

# === API: Arduino 上傳數據 ===
@app.route("/upload", methods=['POST'])
def upload():
    try:
        humidity = float(request.form.get("humidity"))
        temperature = float(request.form.get("temperature"))
        save_to_database(temperature, humidity)
        return {"status": "ok"}, 200
    except Exception as e:
        return {"error": str(e)}, 400

# === API: Arduino 查詢控制指令 ===
@app.route("/command", methods=['GET'])
def command():
    latest = ControlCommand.query.order_by(ControlCommand.id.desc()).first()
    if latest:
        return {"command": latest.command}, 200
    return {"command": "none"}, 200

# === LINE Bot Webhook ===
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# === LINE Bot 訊息處理 ===
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    message = event.message.text.lower()
    reply = ""

    cmd_map = {
        "開燈": "0",
        "關燈": "1",
        "開風扇": "2",
        "關風扇": "3",
        "開灑水": "4",
        "關灑水": "5"
    }

    if message in cmd_map:
        cmd = cmd_map[message]
        new_cmd = ControlCommand(command=cmd)
        db.session.add(new_cmd)
        db.session.commit()
        reply = f"已執行：{message}"

    elif "溫濕度" in message:
        latest = TemperatureHumidity.query.order_by(TemperatureHumidity.id.desc()).first()
        if latest:
            reply = f"目前溫度：{latest.temperature:.1f}℃\n濕度：{latest.humidity:.1f}%"
        else:
            reply = "尚未接收到溫濕度數據。"
    else:
        reply = "請輸入：開燈/關燈/開風扇/關風扇/開灑水/關灑水/溫濕度"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

@app.route('/')
def home():
    return '伺服器運行中'

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
