import os
from flask import Flask, request, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from datetime import datetime

# ================= LINE Bot 設定 =================
line_bot_api = LineBotApi('AvZds3TWRGU0Dkv8s4ayWXtv5oCELiYs9jlKn0/B9Vvzfo9xoVYT6ufMut641La0RRPMiyCmqQx+j2Hmir8ol0x0yfwce6GFtpGSP1a4OYee4PlonyZ1VCZRI3HaKkTF5IhN/C8vrNabg67skELNqgdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('f6690a74c4ccbf530d157674c4ecab05')

# ================= Flask 設定 =================
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    "DATABASE_URL", "postgresql://admin:123456@127.0.0.1:5432/testdb"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ================= 最新感測數據 =================
latest_data = ""

# ================= 資料庫模型 =================
class TemperatureHumidity(db.Model):
    __tablename__ = 'temperature_humidity'
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

# ================= ESP-01 傳感測數據 API =================
@app.route("/sensor", methods=["POST"])
def sensor_data():
    global latest_data
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data"}), 400

    temperature = data.get("temperature")
    humidity = data.get("humidity")
    if temperature is None or humidity is None:
        return jsonify({"error": "Missing temperature or humidity"}), 400

    try:
        temperature = float(temperature)
        humidity = float(humidity)
        latest_data = f"H={humidity}% T={temperature}℃"
        with app.app_context():
            save_to_database(temperature, humidity)
        return jsonify({"status": "ok"}), 200
    except ValueError:
        return jsonify({"error": "Invalid temperature or humidity value"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ================= LINE Webhook =================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    message = event.message.text.lower()
    reply = ""

    if "開燈" in message:
        reply = "電燈已開啟！"
    elif "關燈" in message:
        reply = "電燈已關閉！"
    elif "開風扇" in message:
        reply = "風扇已開啟！"
    elif "關風扇" in message:
        reply = "風扇已關閉！"
    elif "開灑水" in message:
        reply = "灑水已開啟！"
    elif "關灑水" in message:
        reply = "灑水已關閉！"
    elif "溫濕度" in message:
        reply = f"目前溫濕度為：\n{latest_data}" if latest_data else "尚未接收到溫濕度數據。"
    else:
        reply = "請輸入：開燈/關燈/開風扇/關風扇/開灑水/關灑水/溫濕度"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

# ================= 測試首頁 =================
@app.route('/')
def home():
    return '伺服器運行中'

# ================= 主程式 =================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)


