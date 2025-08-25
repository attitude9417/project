import re
from flask import Flask, request, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from datetime import datetime

# LINE Bot 設定
line_bot_api = LineBotApi('AvZds3TWRGU0Dkv8s4ayWXtv5oCELiYs9jlKn0/B9Vvzfo9xoVYT6ufMut641La0RRPMiyCmqQx+j2Hmir8ol0x0yfwce6GFtpGSP1a4OYee4PlonyZ1VCZRI3HaKkTF5IhN/C8vrNabg67skELNqgdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('f6690a74c4ccbf530d157674c4ecab05')

# Flask 設定
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://project:Y7TuzgqXiJ4w64rSiIVLjOm3LQqw1nwk@dpg-d2is9imr433s73e6l2s0-a.singapore-postgres.render.com/project_fh7i"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 最新感測數據 & 控制狀態
latest_data = ""
device_command = None  # Arduino 定時查這個指令

# 資料庫模型
class TemperatureHumidity(db.Model):
    __tablename__ = 'TemperatureHumidity'
    id = db.Column(db.Integer, primary_key=True)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

with app.app_context():
    db.create_all()

def save_to_database(temperature, humidity):
    new_data = TemperatureHumidity(temperature=temperature, humidity=humidity)
    try:
        db.session.add(new_data)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error saving data: {e}")

# === Arduino/ESP 上傳感測數據 ===
@app.route("/upload", methods=["POST"])
def upload():
    global latest_data
    try:
        humidity = float(request.form.get("humidity"))
        temperature = float(request.form.get("temperature"))
        latest_data = f"H={humidity}% T={temperature}℃"
        save_to_database(temperature, humidity)
        return "OK", 200
    except Exception as e:
        return str(e), 400

# === Arduino/ESP 查詢最新指令 ===
@app.route("/command", methods=["GET"])
def command():
    global device_command
    cmd = device_command
    device_command = None  # 拿過一次就清空，避免重複執行
    return jsonify({"command": cmd})

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

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global device_command, latest_data
    message = event.message.text.lower()

    if "開燈" in message:
        device_command = "light_on"
        reply = "電燈已開啟！"
    elif "關燈" in message:
        device_command = "light_off"
        reply = "電燈已關閉！"
    elif "開風扇" in message:
        device_command = "fan_on"
        reply = "風扇已開啟！"
    elif "關風扇" in message:
        device_command = "fan_off"
        reply = "風扇已關閉！"
    elif "開灑水" in message:
        device_command = "water_on"
        reply = "灑水已開啟！"
    elif "關灑水" in message:
        device_command = "water_off"
        reply = "灑水已關閉！"
    elif "溫濕度" in message:
        reply = f"目前溫濕度為：\n{latest_data}" if latest_data else "尚未接收到溫濕度數據。"
    else:
        reply = "請輸入：開燈/關燈/開風扇/關風扇/開灑水/關灑水/溫濕度"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

@app.route('/')
def home():
    return '伺服器運行中 (Render)'

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))  # Render 會指定 PORT
    app.run(host="0.0.0.0", port=port)
