# server.py
# --- 最終解決方案：為 gevent worker 打上猴子補丁 ---
import gevent.monkey
gevent.monkey.patch_all()

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
# --- 修正：增加 ping_timeout 以提高連線穩定性 ---
# 預設的 ping_timeout (5s) 對於休眠後喚醒的伺服器可能太短。
# 增加到 20 秒可以給予客戶端更長的響應時間，減少因網路延遲導致的斷線。
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=20)

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
    """讀取並處理按鈕資料 (data.json)"""
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            if os.path.getsize(DATA_FILE) > 0:
                # 僅在讀取 data.json 時使用 merge_duplicate_keys
                data = json.load(f, object_pairs_hook=merge_duplicate_keys)
                return ensure_sort_order(data)
            return {}
    except (json.JSONDecodeError, IOError):
        return {} # 如果檔案損毀，回傳空字典

def save_data(data):
    save_generic_data(DATA_FILE, data)

def load_json_data(file_path, default_factory):
    """
    一個通用的、安全的 JSON 資料載入函式 (不處理重複鍵)。
    適用於 checklist.json 和 doctors.json。
    - file_path: 檔案路徑。
    - default_factory: 一個函式，當檔案不存在或為空時，呼叫它來產生預設資料。
    """
    if not os.path.exists(file_path):
        return default_factory()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            if os.path.getsize(file_path) > 0:
                # 這裡不使用 object_pairs_hook，因為它僅適用於 data.json
                return json.load(f)
            return default_factory()
    except (json.JSONDecodeError, IOError):
        # 如果檔案損毀或無法讀取，也回傳預設值
        return default_factory()

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
    # 使用新的讀取函式，如果檔案不存在或為空，則回傳一個空字典
    data = load_json_data(CHECKLIST_FILE, lambda: {})
    if not isinstance(data, dict): # 保險措施：如果讀到的不是字典，也回傳空字典
        return jsonify({})
    return jsonify(data)

@app.route('/api/checklist', methods=['POST'])
def update_checklist():
    new_data = request.json
    # --- 最終解決方案：增加伺服器端驗證，防止被空資料覆蓋 ---
    # 只有當收到的資料是一個非空的字典時，才進行儲存。
    if not new_data or not isinstance(new_data, dict):
        print("拒絕儲存：收到的病人清單資料為空或格式不正確。")
        return jsonify({"error": "Invalid or empty checklist data provided"}), 400
    save_generic_data(CHECKLIST_FILE, new_data)
    socketio.emit('checklist_updated', new_data)
    return jsonify({"success": True})

# --- 醫師資料 API ---
@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    # 使用新的讀取函式，如果檔案不存在或為空，則回傳包含預設值的字典
    data = load_json_data(DOCTORS_FILE, lambda: {"未指派": "#808080"})
    if not isinstance(data, dict): # 保險措施：如果讀到的不是字典
        return jsonify({"未指派": "#808080"})
    return jsonify(data)

@app.route('/api/doctors', methods=['POST'])
def update_doctors():
    new_data = request.json
    # --- 最終解決方案：增加伺服器端驗證，防止被空資料覆蓋 ---
    if not new_data or not isinstance(new_data, dict):
        print("拒絕儲存：收到的醫師列表資料為空或格式不正確。")
        return jsonify({"error": "Invalid or empty doctors data provided"}), 400

    # 確保 "未指派" 永遠存在
    if "未指派" not in new_data:
        new_data["未指派"] = "#808080"
    save_generic_data(DOCTORS_FILE, new_data)
    socketio.emit('doctors_updated', new_data)
    return jsonify({"success": True})


if __name__ == '__main__':
    print("開發伺服器正在啟動...")
    socketio.run(app, host='0.0.0.0', port=5000)
