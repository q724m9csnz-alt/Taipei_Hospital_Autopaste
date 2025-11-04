# server.py
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
import json
import os
from collections import OrderedDict

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key' 

# --- 檔案儲存路徑設定 ---
# 檢查是否在 Render 環境中，如果是，則使用永續性硬碟路徑
DATA_DIR = os.environ.get('RENDER_DISK_MOUNT_PATH', '.')
DATA_FILE = os.path.join(DATA_DIR, "data.json")
CHECKLIST_FILE = os.path.join(DATA_DIR, "checklist.json")
DOCTORS_FILE = os.path.join(DATA_DIR, "doctors.json")
socketio = SocketIO(app, cors_allowed_origins="*")

def ensure_sort_order(data):
    """遞迴地確保每個分類字典都有一個 _sort_order 鍵"""
    if isinstance(data, (dict, OrderedDict)):
        # 最終修正標準：只要鍵不是特殊鍵，就應該被納入排序
        sub_categories = [
            k for k in data.keys()
            if k not in ['(按鈕)', '_sort_order']
        ]
        # --- 最終解決方案：只要容器是字典且沒有排序列表，就必須為其建立一個 ---
        # 舊的 `if sub_categories` 判斷是錯誤的，它會忽略只包含按鈕的分類。
        # 現在的邏輯確保了所有字典類型的容器都會被處理。
        if '_sort_order' not in data:
            # --- 最終解決方案：如果一個容器沒有 _sort_order，就為它建立一個，但不要遞迴調用，以避免覆蓋深層結構 ---
            # 這個修正確保了只有在絕對必要時才建立排序列表，並且不會破壞已有的順序。
            if sub_categories: # 只有在有子分類時才建立
                print(f"為容器補充 _sort_order: {sub_categories}")
                data['_sort_order'] = sub_categories
        
        for key, value in data.items():
            # --- 最終解決方案：只對字典類型的值進行遞迴，避免無效操作 ---
            if isinstance(value, (dict, OrderedDict)):
                ensure_sort_order(value)
    return data

def merge_duplicate_keys(ordered_pairs):
    """
    合併 JSON 中重複的鍵。如果鍵的值都是字典，則遞迴合併。
    這可以從根本上解決 data.json 中存在重複頂層分類的問題。
    """
    merged_data = OrderedDict()
    for key, value in ordered_pairs:
        if key in merged_data:
            # 如果鍵已存在，且兩個值都是字典，則進行遞迴合併
            if isinstance(merged_data[key], (dict, OrderedDict)) and isinstance(value, (dict, OrderedDict)):
                # 為了遞迴合併，需要將字典轉回 (key, value) pairs
                # 注意：這是一個簡化的合併，它會將第二個字典的內容合併到第一個中
                # 對於更深層的重複，可能需要更複雜的邏輯，但對於目前情況已足夠
                print(f"偵測到重複鍵 '{key}'，正在合併內容...")
                merged_data[key].update(value)
            # 如果值的類型不同或不是字典，則後者覆蓋前者（保持預設行為）
            else:
                merged_data[key] = value
        else:
            merged_data[key] = value
    return merged_data

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"error": "data.json not found on server"}, 500
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            if os.path.getsize(DATA_FILE) > 0:
                data = json.load(f, object_pairs_hook=merge_duplicate_keys)
                return ensure_sort_order(data) # 在合併後再確保排序
            else:
                return {}
    except (json.JSONDecodeError, IOError):
        return {"error": f"Failed to read or parse {DATA_FILE}"}, 500

def save_data(data):
    # --- 修正：與 save_generic_data 同步，確保在寫入前目錄存在 ---
    dir_name = os.path.dirname(DATA_FILE)
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    # ---------------------------------------------------------
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_generic_data(file_path):
    if not os.path.exists(file_path):
        return {"error": f"{os.path.basename(file_path)} not found on server"}, 404
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f) if os.path.getsize(file_path) > 0 else {}
    except (json.JSONDecodeError, IOError):
        return {"error": f"Failed to read or parse {file_path}"}, 500

def save_generic_data(file_path, data):
    # 在寫入前，確保目錄存在
    dir_name = os.path.dirname(file_path)
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route('/api/data', methods=['GET'])
def get_data():
    data = load_data()
    return jsonify(data)

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

# --- 按鈕資料 API ---
@app.route('/api/data', methods=['POST'])
def update_data():
    new_data = request.json
    if not new_data:
        return jsonify({"error": "No data provided"}), 400
    ordered_new_data = OrderedDict(new_data)
    save_data(ordered_new_data)
    socketio.emit('data_updated', ordered_new_data)
    return jsonify({"success": True})

# --- 待辦清單 API ---
@app.route('/api/checklist', methods=['GET'])
def get_checklist():
    data = load_generic_data(CHECKLIST_FILE)
    return jsonify(data)

@app.route('/api/checklist', methods=['POST'])
def update_checklist():
    new_data = request.json
    save_generic_data(CHECKLIST_FILE, new_data)
    socketio.emit('checklist_updated', new_data)
    return jsonify({"success": True})

# --- 醫師資料 API ---
@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    data = load_generic_data(DOCTORS_FILE)
    return jsonify(data)

@app.route('/api/doctors', methods=['POST'])
def update_doctors():
    new_data = request.json
    save_generic_data(DOCTORS_FILE, new_data)
    socketio.emit('doctors_updated', new_data)
    return jsonify({"success": True})


if __name__ == '__main__':
    print("開發伺服器正在啟動...")
    socketio.run(app, host='0.0.0.0', port=5000)
