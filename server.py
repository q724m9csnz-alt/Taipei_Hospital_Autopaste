# server.py
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
import json
import os
from collections import OrderedDict

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key' 
socketio = SocketIO(app, cors_allowed_origins="*")

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"error": "data.json not found on server"}, 500
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            if os.path.getsize(DATA_FILE) > 0:
                return json.load(f, object_pairs_hook=OrderedDict)
            else:
                return {}
    except (json.JSONDecodeError, IOError):
        return {"error": "Failed to read or parse data.json"}, 500

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route('/api/data', methods=['GET'])
def get_data():
    data = load_data()
    return jsonify(data)

@app.route('/api/data', methods=['POST'])
def update_data():
    new_data = request.json
    if not new_data:
        return jsonify({"error": "No data provided"}), 400

    ordered_new_data = OrderedDict(new_data)
    save_data(ordered_new_data)

    socketio.emit('data_updated', ordered_new_data)

    return jsonify({"success": True})

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    print("開發伺服器正在啟動...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
