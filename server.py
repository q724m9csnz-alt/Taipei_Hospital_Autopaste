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

def ensure_sort_order(data):
    """遞迴地確保每個分類字典都有一個 _sort_order 鍵"""
    if isinstance(data, (dict, OrderedDict)):
        # 檢查這是否是一個包含子分類的容器
        sub_categories = [k for k in data.keys() if k not in ['(按鈕)', '_sort_order'] and isinstance(data[k], (dict, OrderedDict, list))]
        if sub_categories and '_sort_order' not in data:
            print(f"為容器補充 _sort_order: {list(data.keys())}")
            data['_sort_order'] = sub_categories
        
        for key, value in data.items():
            ensure_sort_order(value)
    return data

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"error": "data.json not found on server"}, 500
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            if os.path.getsize(DATA_FILE) > 0:
                data = json.load(f, object_pairs_hook=OrderedDict)
                # 確保載入的資料有排序列表
                return ensure_sort_order(data)
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
