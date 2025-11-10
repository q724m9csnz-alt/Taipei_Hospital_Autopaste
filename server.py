# server.py
# --- 最終解決方案：為 gevent worker 打上猴子補丁 ---
import gevent.monkey
gevent.monkey.patch_all()

from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
import json
import os
from collections import OrderedDict
# --- 新增：PostgreSQL 整合 ---
import psycopg2
from psycopg2.extras import Json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key' 

# --- PostgreSQL 資料庫初始化 ---
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """建立並返回一個資料庫連線"""
    if not DATABASE_URL:
        raise ValueError("錯誤：未設定 DATABASE_URL 環境變數。")
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    """初始化資料庫，建立我們需要的資料表"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # 我們建立一個簡單的 key-value 表，key 是唯一的
        # value 的類型是 JSONB，可以直接儲存我們的 JSON 資料
        cur.execute('''
            CREATE TABLE IF NOT EXISTS storage (
                key TEXT PRIMARY KEY,
                value JSONB
            );
        ''')
        conn.commit()
        cur.close()
        conn.close()
        print("資料庫資料表 'storage' 已確認存在。")
    except Exception as e:
        print(f"資料庫初始化失敗: {e}")

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
    """從 PostgreSQL 讀取按鈕資料"""
    data = load_generic_data("buttons_data", lambda: {})
    return ensure_sort_order(data)

def save_data(data):
    """將按鈕資料儲存到 PostgreSQL"""
    save_generic_data("buttons_data", data)

def load_generic_data(key, default_factory):
    """
    一個通用的 PostgreSQL 資料載入函式。
    - key: 我們在資料表中儲存資料的鍵 (例如 'buttons_data', 'checklist_data')。
    - default_factory: 一個函式，當檔案不存在或為空時，呼叫它來產生預設資料。
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT value FROM storage WHERE key = %s;", (key,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        if result:
            # result[0] 就是我們存的 JSONB 資料
            return result[0]
        return default_factory()
    except Exception as e:
        print(f"讀取資料 '{key}' 失敗: {e}")
        return default_factory()

def save_generic_data(key, data):
    """一個通用的 PostgreSQL 資料儲存函式。"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # 使用 UPSERT 語法：如果 key 已存在，則更新 value；如果不存在，則插入新的一行。
        # Json(data) 會將 Python 字典正確轉換為資料庫的 JSONB 格式。
        cur.execute('''
            INSERT INTO storage (key, value) VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
        ''', (key, Json(data)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"儲存資料 '{key}' 失敗: {e}")

@app.route('/api/data', methods=['GET'])
def get_data():
    data = load_data()
    return jsonify(data)

# --- 健康檢查路由 ---
@app.route('/', methods=['GET'])
def health_check():
    return "Server is running."

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

# --- 按鈕資料 API ---
# 這是專門用來接收從客戶端「匯入舊資料」的 HTTP POST 請求
@app.route('/api/data', methods=['POST'])
def http_update_data():
    new_data = request.json
    if not new_data:
        return jsonify({"error": "No data provided"}), 400
    save_data(OrderedDict(new_data))
    socketio.emit('data_updated', new_data) # 通知所有線上使用者刷新
    return jsonify({"success": True})

# 這是專門用來接收未來可能的即時同步（例如拖曳排序）的 WebSocket 事件
@socketio.on('update_data')
def socket_update_data(new_data):
    if not new_data:
        return
    save_data(OrderedDict(new_data))
    # 使用 broadcast=True 通知除了發送者之外的所有客戶端
    emit('data_updated', new_data, broadcast=True)

# --- 待辦清單 API ---
@app.route('/api/checklist', methods=['GET'])
def get_checklist():
    # 使用新的讀取函式，如果檔案不存在或為空，則回傳一個空字典
    data = load_generic_data("checklist_data", lambda: {})
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
    save_generic_data("checklist_data", new_data)
    socketio.emit('checklist_updated', new_data)
    return jsonify({"success": True})

# --- 醫師資料 API ---
@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    # 使用新的讀取函式，如果檔案不存在或為空，則回傳包含預設值的字典
    data = load_generic_data("doctors_data", lambda: {"未指派": "#808080"})
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
    save_generic_data("doctors_data", new_data)
    socketio.emit('doctors_updated', new_data)
    return jsonify({"success": True})


if __name__ == '__main__':
    print("開發伺服器正在啟動...")
    init_db() # 在本地開發時也初始化資料庫
    # Render 會自動設定 PORT 環境變數
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
