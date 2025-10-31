import tkinter as tk  # 引入 tkinter 介面模組
from tkinter import simpledialog, messagebox  # 引入簡易對話框與訊息框
import pyperclip  # 引入剪貼簿操作模組
import pyautogui  # 引入自動化鍵鼠操作模組
import sys  # 系統模組，用於判斷平台
import json  # JSON 處理模組
import os  # 作業系統介面模組
import time  # 時間處理模組
from collections import OrderedDict  # 有序字典，用於保持 JSON 資料順序
import requests  # HTTP 請求模組
import socketio  # WebSocket 客戶端模組
import threading # 多執行緒模組


DATA_FILE = "buttons.json"  # 資料檔名

# --- 請將此處的網址換成您在 Render 上複製的網址 ---
SERVER_URL = "https://taipei-hospital-orthopedics-autopaste.onrender.com"


class AddButtonWindow(tk.Toplevel):  # 新增按鈕視窗
    def __init__(self, app, category_path):
        super().__init__(app)
        self.app = app
        self.category_path = category_path
        self.title(f"在 {self.category_path[-1]} 中新增按鈕")
        self.geometry("400x300")
        self.transient(self.app)
        self.focus_force()
        self.create_widgets()
        self.center_window()

    def create_widgets(self):
        tk.Label(self, text="按鈕名稱:", font=("Segoe UI", 10)).pack(pady=5)
        self.entry_name = tk.Entry(self, font=("Segoe UI", 10))
        self.entry_name.pack(fill='x', padx=10)
        tk.Label(self, text="預設貼文內容:", font=("Segoe UI", 10)).pack(pady=5)
        self.text_content = tk.Text(self, height=10, font=("Segoe UI", 10))
        self.text_content.pack(fill='both', padx=10, expand=True)
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="新增", command=self.add_button, width=8).pack(side='left', padx=10)
        tk.Button(btn_frame, text="取消", command=self.destroy, width=8).pack(side='left', padx=10)

    def add_button(self):
        name = self.entry_name.get().strip()
        content = self.text_content.get('1.0', 'end').rstrip('\n')
        if not name or not content:
            messagebox.showwarning("錯誤", "名稱與內容不可為空", parent=self)
            return

        container = self.app.get_container_by_path(self.category_path)
        button_list = []
        if isinstance(container, list):
            button_list = container
        elif isinstance(container, dict):
            button_list = container.setdefault('(按鈕)', [])

        if name in [btn['label'] for btn in button_list]:
            messagebox.showwarning("錯誤", "重複的按鈕名稱", parent=self)
            return

        button_list.append({'label': name, 'text': content})
        self.app.save()
        
        # Get the category frame and ensure it's expanded to show the new button
        category_frame = self.app.category_frames.get(tuple(self.category_path))
        if category_frame:
            category_frame.expand() # This will call show_data() and refresh the buttons

        self.destroy()

    def center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = screen_w - w - 0
        y = screen_h - h - 72
        self.geometry(f"+{x}+{y}")


class EditButtonWindow(tk.Toplevel):  # 編輯按鈕視窗
    def __init__(self, app, btn_frame):
        super().__init__(app)
        self.app = app
        self.btn_frame = btn_frame
        self.title("修改按鈕")
        self.geometry("400x300")
        self.transient(self.app)
        self.focus_force()
        self.create_widgets()
        self.center_window()

    def create_widgets(self):
        tk.Label(self, text="按鈕名稱：", font=("Segoe UI", 10)).pack(pady=5)
        self.edit_name_var = tk.StringVar(value=self.btn_frame.btn_data['label'])
        tk.Entry(self, textvariable=self.edit_name_var, font=("Segoe UI", 10)).pack(fill='x', padx=10)
        tk.Label(self, text="內容：", font=("Segoe UI", 10)).pack(pady=5)
        self.edit_text = tk.Text(self, height=9, font=("Segoe UI", 10))
        self.edit_text.pack(fill='both', padx=10, pady=5, expand=True)
        self.edit_text.insert('1.0', self.btn_frame.btn_data['text'])
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="確定", command=self.confirm_edit, width=8).pack(side='left', padx=10)
        tk.Button(btn_frame, text="取消", command=self.destroy, width=8).pack(side='left', padx=10)

    def confirm_edit(self):
        new_name = self.edit_name_var.get().strip()
        new_content = self.edit_text.get('1.0', 'end').rstrip('\n')
        if not new_name or not new_content:
            messagebox.showwarning("錯誤", "名稱與內容不可為空", parent=self)
            return
        self.btn_frame.btn_data['label'] = new_name
        self.btn_frame.btn_data['text'] = new_content
        self.btn_frame.main_button.config(text=new_name)
        self.app.save()
        self.btn_frame.category_frame.expand()
        self.destroy()

    def center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = screen_w - w - 0
        y = screen_h - h - 72
        self.geometry(f"+{x}+{y}")


class DragButtonFrame(tk.Frame):  # 自訂拖曳按鈕容器類別，用於單個按鈕及編輯刪除按鈕
    def __init__(self, parent, btn_data, category_frame, index, app, **kwargs):
        super().__init__(parent, bg=parent.cget('bg'), **kwargs)
        self.app = app  # 主應用實例
        self.btn_data = btn_data  # 按鈕資料字典 {'label':..., 'text':...}
        self.category_frame = category_frame  # 所屬分類框架
        self.index = index  # 位置索引（未實際用）

        self.last_paste_time = 0  # 用於防止雙擊過快多次貼上

        self.main_button = tk.Button(self, text=btn_data['label'], anchor='w', relief='flat', bg='#ffffff', bd=0, activebackground='#e0e0e0', font=("Segoe UI", 10), justify='left', padx=5)
        self.main_button.pack(side='left', fill='x', expand=True, padx=1, pady=1)  # 水平填滿並擴張
        self.main_button.bind('<Button-1>', self.on_click)  # 單擊事件綁定複製文字
        self.main_button.bind('<Double-Button-1>', self.on_double_click)  # 雙擊事件綁定貼上

        # 綁定右鍵點擊事件以顯示上下文選單
        self.main_button.bind('<Button-3>', self.show_context_menu)

        self._dragging = False  # 拖曳中狀態旗標
        self._start_x = 0  # 按下點相對座標X
        self._start_y = 0  # 按下點相對座標Y

    # --- Event Handlers ---

    def on_click(self, event):
        if not self._dragging:
            pyperclip.copy(self.btn_data['text'])  # 單擊時將文字複製到剪貼簿

    def on_double_click(self, event):
        now = time.time()  # 目前時間
        if now - self.last_paste_time < 0.8:  # 避免過快重複貼上
            return
        self.last_paste_time = now
        pyperclip.copy(self.btn_data['text'])  # 複製文字

        def paste_with_window_switch():  # 模擬切換視窗與貼上
            if sys.platform == 'darwin':  # MacOS
                pyautogui.hotkey('command', 'tab')
                time.sleep(0.3)
                pyautogui.hotkey('command', 'v')
            else:  # 其他系統Windows為主
                pyautogui.hotkey('alt', 'tab')
                time.sleep(0.3)
                pyautogui.hotkey('ctrl', 'v')

        self.app.after(100, paste_with_window_switch)  # 延遲呼叫貼上
        self.main_button.config(bg='lightblue')  # 按鈕背景閃爍提示
        self.after(150, lambda: self.main_button.config(bg='#ffffff'))  # 恢復背景為白色

    def show_context_menu(self, event):
        # 建立一個彈出式選單
        context_menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 9))

        # --- Create "Move To..." sub-menu for buttons ---
        move_menu = tk.Menu(context_menu, tearoff=0, font=("Segoe UI", 9))
        
        def build_move_menu(parent_menu, data_dict, current_path):
            for name, content in data_dict.items():
                if name == '(按鈕)': continue
                new_path = current_path + [name]
                label = "    " * len(current_path) + name
                # Disable moving to the same category the button is already in
                is_invalid_target = (new_path == self.category_frame.path)

                if is_invalid_target:
                    parent_menu.add_command(label=label, state="disabled")
                else:
                    parent_menu.add_command(label=label, 
                                            command=lambda dest=new_path: self.app.move_button_to_new_category(self.btn_data, self.category_frame.path, dest))
                
                # Recursively build the menu for sub-categories
                if isinstance(content, dict):
                    build_move_menu(parent_menu, content, new_path)

        build_move_menu(move_menu, self.app.data, [])
        context_menu.add_cascade(label="移至...", menu=move_menu)
        context_menu.add_separator()
        context_menu.add_command(label="上移", command=self.move_up)
        context_menu.add_command(label="下移", command=self.move_down)
        context_menu.add_separator()
        context_menu.add_command(label="編輯", command=self.open_edit_window)
        context_menu.add_command(label="刪除", command=self.confirm_delete)
        # 在滑鼠點擊的位置顯示選單
        context_menu.tk_popup(event.x_root, event.y_root)

    # --- Actions ---
    def move_up(self):
        self.app.move_button(self.btn_data, self.category_frame.path, -1)

    def move_down(self):
        self.app.move_button(self.btn_data, self.category_frame.path, 1)

    def open_edit_window(self):
        self.app.open_edit_window(self)  # 呼叫主程式開啟編輯視窗

    def confirm_delete(self):
        cat_name = str(self.category_frame.category_name)  # 取得分類名稱
        if messagebox.askyesno("刪除確認", f"確定要刪除「{self.btn_data['label']}」嗎？", parent=self.app):  # 刪除確認對話框
            container = self.app.get_container_by_path(self.category_frame.path)
            if isinstance(container, dict):
                button_list = container.get('(按鈕)', [])
                if self.btn_data in button_list:
                    button_list.remove(self.btn_data)
            elif isinstance(container, list) and self.btn_data in container:
                container.remove(self.btn_data)
            self.app.save()  # 儲存資料
            self.category_frame.expand()  # 重新展開分類來刷新列表
            self.destroy()  # 銷毀此按鈕物件


class CategoryFrame(tk.Frame):  # 單一分類框架，含分類標題與所有拖曳按鈕
    def __init__(self, parent, name, app, depth=0, path=None): # Removed bd/relief from super()
        super().__init__(parent)
        self.app = app
        self.category_name = str(name)  # 分類名稱
        self.depth = depth
        self.path = path if path is not None else [self.category_name]
        self.expanded = False  # 收合狀態
        self.buttons = []  # 按鈕物件列表
        self.subcategories = {} # 子分類框架

        self.header = tk.Frame(self)  # 標頭欄位
        self.header.pack(fill='x')
        
        # --- Visual Distinction Logic ---
        if self.depth == 0: # Top-level category styling
            self.config(bd=2, relief='ridge') # Frame border for top-level
            font_style = ("Segoe UI", 11, "bold") # Larger, bold font
            header_bg = "#d9e1e8" # Light steel blue header
            content_bg = "#eef2f5" # Slightly lighter blue-grey content
        else: # Sub-category styling
            self.config(bd=1, relief='solid', highlightbackground="#cccccc", highlightthickness=1) # Subtle nested border
            font_style = ("Segoe UI", 10) # Normal font for sub-categories
            header_bg = "#e4eaf0" # Very light blue-grey header
            content_bg = "#f4f6f8" # Almost white-blue content area

        self.header.config(bg=header_bg)

        indent = "    " * self.depth
        self.label = tk.Label(self.header, text=f"{indent}+ {self.category_name}", anchor='w', font=font_style, bg=header_bg)
        self.label.pack(side='left', fill='x', expand=True)

        # --- Vertically stacked Up/Down Buttons ---
        button_container = tk.Frame(self.header, bg=header_bg)
        button_container.pack(side="right", padx=(0, 5), fill='y')

        active_bg_color = '#c8d1d8' if self.depth == 0 else '#d3dae0' # Slightly darker shade for active state

        self.btn_up = tk.Button(button_container, text="▲", command=self.move_up, bg=header_bg, fg="#555", relief='flat', bd=0, activebackground=active_bg_color, activeforeground="#222", font=("Segoe UI", 7))
        self.btn_up.pack(side="top", expand=True, fill='both', pady=(2,0))
        self.btn_down = tk.Button(button_container, text="▼", command=self.move_down, bg=header_bg, fg="#555", relief='flat', bd=0, activebackground=active_bg_color, activeforeground="#222", font=("Segoe UI", 7))
        self.btn_down.pack(side="bottom", expand=True, fill='both', pady=(0,2))

        # Bind left-click on the label to toggle, and right-click on the header to show the menu.
        self.label.bind('<Button-1>', lambda e: self.toggle()) # Left-click to toggle
        self.header.bind('<Button-3>', self.show_context_menu)
        self.label.bind('<Button-3>', self.show_context_menu)

        self.content = tk.Frame(self)  # 內容放置按鈕的容器
        self.content.pack(fill='x')
        self.content.config(bg=content_bg) # Apply determined content background
        self.content.forget()  # 預設隱藏內容框

    # --- UI Actions ---

    def open_add_button_window(self):
        self.app.open_add_button_window(self.path)

    def toggle(self):
        if self.expanded:
            self.collapse()
        else:
            self.expand()

    def show_context_menu(self, event):
        context_menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 9))
        context_menu.add_command(label="新增按鈕", command=self.open_add_button_window)
        context_menu.add_command(label="新增子分類", command=self.add_subcategory)

        # --- Create "Move To..." sub-menu for categories ---
        move_menu = tk.Menu(context_menu, tearoff=0, font=("Segoe UI", 9))
        
        # Recursive function to build the destination menu
        def build_move_menu(parent_menu, data_dict, current_path):
            for name, content in data_dict.items():
                if name == '(按鈕)': continue
                
                new_path = current_path + [name]
                # Prevent moving a category into itself or its own children
                is_invalid_target = (len(new_path) >= len(self.path) and new_path[:len(self.path)] == self.path)
                label = "    " * len(current_path) + name
                
                if is_invalid_target: # Cannot move into itself or its descendants
                    parent_menu.add_command(label=label, state="disabled")
                else:
                    parent_menu.add_command(label=label,
                                            command=lambda dest=new_path: self.app.move_category_to_new_parent(self.path, dest))
                if isinstance(content, dict):
                    build_move_menu(parent_menu, content, new_path)

        build_move_menu(move_menu, self.app.data, [])
        if self.depth > 0: # If it's a sub-category, add option to move to top level
            move_menu.add_separator()
            move_menu.add_command(label="(移至頂層)", command=lambda: self.app.move_category_to_new_parent(self.path, []))

        context_menu.add_cascade(label="移至...", menu=move_menu)
        context_menu.add_separator()
        context_menu.add_command(label="重新命名", command=self.rename)
        context_menu.add_command(label="刪除分類", command=self.confirm_delete)
        context_menu.tk_popup(event.x_root, event.y_root)

    def add_subcategory(self):
        self.app.add_category(parent_path=self.path)

    def expand(self):
        self.expanded = True
        indent = "    " * self.depth
        self.label.config(text=f"{indent}- {self.category_name}")
        self.content.pack(fill='x')
        self.show_data()

    def confirm_delete(self):
        # 刪除分類前的確認對話框
        if messagebox.askyesno("刪除分類確認",
                               f"確定要刪除整個分類「{self.category_name}」及其中所有按鈕嗎？",
                               parent=self.app):
            # 從主程式資料中刪除此分類
            container = self.app.get_container_by_path(self.path[:-1])
            if self.category_name in container:
                del container[self.category_name]
            self.app.save()
            # self.app.save() # This was already here, but it's good practice to ensure it is.
            self.app.populate()  # 重新載入介面
    
    def collapse(self):
        self.expanded = False
        indent = "    " * self.depth
        self.label.config(text=f"{indent}+ {self.category_name}")
        self.content.forget()
        for btn in self.buttons:
            btn.destroy()
        self.buttons.clear()

    def rename(self):
        new_name = simpledialog.askstring('重命名分類', '請輸入新名稱:', initialvalue=self.category_name, parent=self.app)
        if new_name and new_name != self.category_name:
            if new_name in self.app.data:
                messagebox.showwarning('錯誤', '名稱已存在', parent=self.app)
                return

            container = self.app.get_container_by_path(self.path[:-1])
            new_container = OrderedDict()
            for key, value in container.items():
                if key == self.category_name:
                    new_container[new_name] = value
                else:
                    new_container[key] = value
            container.clear()
            container.update(new_container)

            self.app.save()
            self.app.populate()
    
    # --- Data Display ---

    def show_data(self):
        for btn in self.buttons:
            btn.destroy()
        self.buttons.clear()
        for sub in list(self.subcategories.values()):
            sub.destroy()
        self.subcategories.clear()

        cdata = self.app.get_container_by_path(self.path)

        if isinstance(cdata, dict):
            for key, value in cdata.items():
                if key == '(按鈕)':
                    self.show_buttons(value)
                else: # It's a sub-category
                    sub_path = self.path + [key]
                    sub_frame = CategoryFrame(self.content, key, self.app, self.depth + 1, sub_path)
                    sub_frame.pack(fill='x', pady=1)
                    self.subcategories[key] = sub_frame
        elif isinstance(cdata, list):
            self.show_buttons(cdata)

    def show_buttons(self, btn_list):
        for btn in self.buttons:
            btn.destroy()
        self.buttons.clear()
        if btn_list:
            for btn_data in btn_list:
                btn_frame = DragButtonFrame(self.content, btn_data, self, 0, self.app)
                # The bindings for drag-and-drop are now removed, so we don't need to re-add them here.
                # The right-click menu is the primary way to interact.
                btn_frame.pack(fill='x', padx=5, pady=1)
                self.buttons.append(btn_frame)

    def move_up(self):
        self.app.move_category(self.path, -1)

    def move_down(self):
        self.app.move_category(self.path, +1)


class AutoPasteApp(tk.Tk):  # 主視窗類別，介面核心
    def __init__(self):
        super().__init__()
        self.overrideredirect(True)  # Remove default OS title bar

        self.update_idletasks()

        # 主視窗寬度與高度設定（寬270，高310）
        self.width = 260
        self.height = 400
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.category_frames = {}  # 分類框架字典，key為分類名稱

        self.drag_shadow = None
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.insertion_line = None
        self._current_drag_target = None  # Tuple of (category_name, insert_index)

        # 預設先放置中心，稍後用 after() 再調整準確位置
        self.geometry(f"{self.width}x{self.height}+{(screen_w - self.width)//2}+{(screen_h - self.height)//2}")

        self.attributes('-topmost', True)
        self.config(bg="#2c3e50")  # Set main background color
        self.data = self.load()  # 載入資料

        # --- Custom Title Bar ---
        title_bar = tk.Frame(self, bg='#34495e', relief='raised', bd=0, height=25)
        title_bar.pack(expand=0, fill='x')
        title_label = tk.Label(title_bar, text="自動貼文系統", bg='#34495e', fg='white', font=("Segoe UI", 11, "bold"))
        title_label.pack(side='left', padx=10)
        # Bind events to move the window
        # title_bar.bind("<ButtonPress-1>", self.start_window_move)
        # title_bar.bind("<B1-Motion>", self.do_window_move)
        # title_label.bind("<ButtonPress-1>", self.start_window_move)
        # title_label.bind("<B1-Motion>", self.do_window_move)

        minimize_button = tk.Button(title_bar, text='—', command=self.minimize_to_icon, bg='#f39c12', fg='white', relief='flat', activebackground='#f1c40f', activeforeground='white', font=("Segoe UI", 10, "bold"), width=3)
        minimize_button.pack(side='right', padx=0, pady=2)

        close_button = tk.Button(title_bar, text='✕', command=self.destroy, bg='#e74c3c', fg='white', relief='flat', activebackground='#c0392b', activeforeground='white', font=("Segoe UI", 10, "bold"), width=3)
        close_button.pack(side='right', padx=5, pady=2)

        # --- Top Function Bar ---
        top_frame = tk.Frame(self, bg="#2c3e50")
        top_frame.pack(fill='x', padx=5, pady=5)
        tk.Button(top_frame, text='新增分類', command=self.add_category, bg='#34495e', fg='#f39c12', relief='flat', activebackground='#4a6278', activeforeground='white', font=("Segoe UI", 9)).pack(side='left')

        # 主內容容器改為包含Canvas與垂直捲軸，可滑動顯示過多的分類和按鈕
        self.container = tk.Frame(self)
        self.container.pack(fill='both', expand=True)

        self.canvas = tk.Canvas(self.container, bg="#2c3e50", highlightthickness=0)  # Canvas background matches main app background
        self.scrollbar = tk.Scrollbar(self.container, orient="vertical", command=self.canvas.yview)
        self.canvas.pack(side="left", fill="both", expand=True)

        # 內部滾動框架，實際放置分類用
        self.inner_frame = tk.Frame(self.canvas, bg="#ffffff")  # Clean white background for the scrollable area content

        # 建立Canvas內部視窗，設定滾動視窗為內框架
        self.canvas.create_window((0, 0), window=self.inner_frame, anchor='nw')

        # 更新滾動區域大小
        self.inner_frame.bind("<Configure>", self.on_frame_configure)

        # 讓 inner_frame 的寬度跟隨 canvas 的寬度
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # 綁定滑鼠滾輪事件，對Canvas作垂直滾動
        self.canvas.bind_all("<MouseWheel>", self.on_mouse_wheel)  # Windows / Mac OS
        self.canvas.bind_all("<Button-4>", self.on_mouse_wheel)  # Linux 滾輪向上
        self.canvas.bind_all("<Button-5>", self.on_mouse_wheel)  # Linux 滾輪向下

        self.populate()  # Initial population of categories

        self.icon_window = None
        self.icon_drag_start_x = 0
        self.icon_drag_start_y = 0

        self.icon_pos_x = screen_w - 50 - 20  # 預設企鵝按鈕位置
        self.icon_pos_y = 40

        # --- WebSocket 初始化 ---
        self.sio = socketio.Client()
        self.setup_socketio_events()
        self.connect_to_server()

        self.after(10, self.set_window_position)  # 程式啟動後延遲呼叫設定窗體位置，確保生效

    def start_window_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_window_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        self.geometry(f"+{self.winfo_x() + deltax}+{self.winfo_y() + deltay}")

    def set_window_position(self):
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        # 貼齊螢幕最右側與工作欄上方(預留40px)
        x = screen_w - self.width - 0
        y = screen_h - self.height - 40
        self.geometry(f"{self.width}x{self.height}+{x}+{y}")

    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_ui_update(self, data):
        """安全地在主執行緒中更新UI"""
        # 在更新UI前，也對從WebSocket收到的資料進行淨化
        self.data = self._sanitize_data(OrderedDict(data))
        self.populate()

    def setup_socketio_events(self):
        @self.sio.event
        def connect():
            print("成功連接到雲端伺服器！")

        @self.sio.event
        def data_updated(data):
            print("收到資料更新通知，正在刷新介面...")
            # 使用 after() 確保 UI 更新在主執行緒中執行
            self.after(0, self.on_ui_update, data)

        @self.sio.event
        def disconnect():
            print("與雲端伺服器斷開連接。")

    def connect_to_server(self):
        """在背景執行緒中連接到 WebSocket 伺服器"""
        def run():
            try:
                self.sio.connect(SERVER_URL)
                self.sio.wait()
            except socketio.exceptions.ConnectionError as e:
                print(f"無法連接到伺服器: {e}")
                messagebox.showerror("連線錯誤", f"無法連接到伺服器 {SERVER_URL}。\n請確認伺服器正在執行且網路連線正常。")
        
        thread = threading.Thread(target=run)
        thread.daemon = True  # 設置為守護執行緒，主程式退出時會自動結束
        thread.start()

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas.create_window((0, 0), window=self.inner_frame, anchor='nw'), width=event.width)
    def on_mouse_wheel(self, event):
        # Windows 和 MacOS
        if event.num == 4 or event.delta > 0:  # 向上滾
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:  # 向下滾
            self.canvas.yview_scroll(1, "units")

    # --- Data Persistence ---

    def _sanitize_data(self, data):
        """遞迴地清理資料，確保所有鍵和字串值都是合法的字串。"""
        if isinstance(data, OrderedDict):
            return OrderedDict((str(k), self._sanitize_data(v)) for k, v in data.items())
        if isinstance(data, dict):
            return {str(k): self._sanitize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_data(elem) for elem in data]
        elif isinstance(data, str):
            # 確保字串是合法的，但通常json.loads已經處理了
            return data
        else:
            return data

    def load(self):
        """從伺服器載入資料"""
        try:
            # 延長 timeout 以應對 Render 伺服器休眠喚醒
            response = requests.get(f"{SERVER_URL}/api/data", timeout=45)
            response.raise_for_status()  # 如果請求失敗 (e.g., 404, 500)，會拋出異常
            # 使用伺服器回傳的 JSON，並進行淨化處理
            loaded_data = response.json(object_pairs_hook=OrderedDict) # type: ignore
            return self._sanitize_data(loaded_data) # type: ignore
        except requests.exceptions.RequestException as e:
            messagebox.showerror("網路錯誤", f"無法從雲端伺服器載入資料: {e}")
            return OrderedDict()

    def save(self):
        """將目前資料儲存到伺服器"""
        try:
            requests.post(f"{SERVER_URL}/api/data", json=self.data, timeout=45)
        except requests.exceptions.RequestException as e:
            messagebox.showerror("網路錯誤", f"無法儲存資料到雲端伺服器: {e}")

    # --- UI Population and Management ---

    def populate(self):
        # Preserve expanded state by path
        expanded_paths = {tuple(frame.path) for name, frame in self.category_frames.items() if frame.expanded}
        for w in self.inner_frame.winfo_children():
            w.destroy()
        self.category_frames.clear()
        self.insertion_line = None  # The line widget is destroyed, so reset the reference
        self._populate_recursive(self.inner_frame, self.data, [], expanded_paths)

    def _populate_recursive(self, parent_widget, data_dict, current_path, expanded_paths):
        # 決定迭代順序：優先使用 _sort_order，否則使用原始鍵
        sorted_keys = data_dict.get('_sort_order', [k for k in data_dict.keys() if k not in ['(按鈕)', '_sort_order']])

        for name in sorted_keys:
            if name not in data_dict: continue # 如果排序列表中的鍵不存在，則跳過
            content = data_dict[name]

            path = current_path + [name]
            frame = CategoryFrame(parent_widget, name, self, depth=len(current_path), path=path)
            # Add more vertical space between top-level categories
            pady = 5 if len(current_path) == 0 else 1  # Increased pady for top-level categories
            frame.pack(fill='x', pady=(pady, 0), padx=2)
            self.category_frames[tuple(path)] = frame
            if tuple(path) in expanded_paths:
                frame.expand()

    def toggle_category(self, category):
        category = str(category)
        if category in self.category_frames:
            cf = self.category_frames[category]
            if cf.expanded:
                cf.collapse()
            else:
                cf.expand()

    def show_category_buttons(self, category):
        category = str(category)
        frame = self.category_frames.get(category)
        if not frame:
            return
        for btn in frame.buttons:
            btn.destroy()
        frame.buttons.clear()
        for btn_data in self.data[category]:
            btn_frame = DragButtonFrame(frame.content, btn_data, frame, 0, self)
            btn_frame.main_button.bind('<ButtonPress-1>', btn_frame.on_press)
            btn_frame.main_button.bind('<B1-Motion>', btn_frame.on_drag)
            btn_frame.main_button.bind('<ButtonRelease-1>', btn_frame.on_release)

    def add_category(self, parent_path=None):
        title = '新增分類' if parent_path is None else f'在 "{parent_path[-1]}" 中新增子分類'
        name = simpledialog.askstring(title, '請輸入分類名稱:', parent=self)
        if name:
            name = str(name)
            container = self.get_container_by_path(parent_path)

            if name in container:
                messagebox.showwarning('錯誤', '分類名稱已存在', parent=self)
                return

            if isinstance(container, list):
                # Convert a button list to a mixed-content category
                new_content = OrderedDict({'(按鈕)': container, name: []})
                parent_container = self.get_container_by_path(parent_path[:-1])
                parent_container[parent_path[-1]] = new_content
            else:
                container[name] = []

            self.save()
            self.populate()

    # --- Core Functionality ---

    def get_container_by_path(self, path):
        if not path:
            return self.data
        
        ref = self.data
        for step in path:
            ref = ref[step]
        return ref

    def paste_text(self, btn_data):
        pyperclip.copy(btn_data['text'])
        if sys.platform == 'darwin':
            pyautogui.hotkey('command', 'tab')
            time.sleep(0.3)
            pyautogui.hotkey('command', 'v')
            time.sleep(0.2)
            pyautogui.hotkey('command', 'tab')
        else:
            pyautogui.hotkey('alt', 'tab')
            time.sleep(0.3)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.2)
            pyautogui.hotkey('alt', 'tab')
        if self.drag_shadow:
            self.drag_shadow.destroy()
        w = widget.winfo_width()
        h = widget.winfo_height()
        scale = 0.7
        self.drag_offset_x = int(widget._start_x)
        self.drag_offset_y = int(widget._start_y)
        x = widget.winfo_rootx() - self.drag_offset_x
        y = widget.winfo_rooty() - self.drag_offset_y
        
        self.drag_shadow = tk.Toplevel(self)
        self.drag_shadow.overrideredirect(True)
        self.drag_shadow.attributes('-topmost', True)
        self.drag_shadow.geometry(f"{w}x{h}+{x}+{y}")
        label = tk.Label(self.drag_shadow, text=widget.main_button.cget('text'), bg='lightgray', relief='solid', bd=1)
        label.pack(fill='both', expand=True)        

    def destroy_drag_shadow(self):
        if self.drag_shadow:
            self.drag_shadow.destroy()
            self.drag_shadow = None

    def create_insertion_line(self):
        if self.insertion_line:
            # If it's a dead widget, reset it
            try:
                self.insertion_line.winfo_exists()
            except tk.TclError:
                self.insertion_line = None
        if self.insertion_line:
            return
        if not self.insertion_line:
            return
        found = False
        for path, frame in self.category_frames.items():
            # Check if dragging over a category header to expand it
            header_x, header_y = frame.header.winfo_rootx(), frame.header.winfo_rooty()
            header_w, header_h = frame.header.winfo_width(), frame.header.winfo_height()
            if header_x <= x_root <= header_x + header_w and header_y <= y_root <= header_y + header_h:
                if not frame.expanded:
                    frame.expand()
                    # After expanding, we might need a moment for the UI to update before proceeding.
                    # We can return and let the next drag event handle the insertion line.
                    self.insertion_line.place_forget()
                    self._current_drag_target = None
                    return

            # Check if dragging inside an expanded category's content area
            fx, fy = frame.content.winfo_rootx(), frame.content.winfo_rooty()
            fw, fh = frame.content.winfo_width(), frame.content.winfo_height() # Use winfo_height for check
            if frame.expanded and (fx <= x_root < fx + fw) and (fy <= y_root < fy + fh):
                # Convert root_y to be relative to the content frame
                y_in_content = y_root - fy
                buttons = frame.buttons
                insert_index = len(buttons)

                # Find the correct insertion index based on the y-position
                for i, btn in enumerate(buttons):
                    # If the cursor is in the top half of a button, insert before it
                    if y_in_content < btn.winfo_y() + (btn.winfo_height() / 2):
                        insert_index = i
                        break

                # Calculate the Y position for the insertion line within the category's content frame
                if insert_index < len(buttons):
                    # Place line at the top of the button we're inserting before
                    line_y_in_content = buttons[insert_index].winfo_y()
                elif buttons:
                    # Place line at the bottom of the last button
                    last_btn = buttons[-1]
                    line_y_in_content = last_btn.winfo_y() + last_btn.winfo_height()
                else:
                    # Place at the top if the category is empty
                    line_y_in_content = 0

                self.insertion_line.place(in_=frame.content, x=0, y=line_y_in_content, relwidth=1.0)
                self._current_drag_target = (frame.path, insert_index)
                found = True
                break

        if not found:
            self.insertion_line.place_forget()
            self._current_drag_target = None
    def destroy_insertion_line(self):
        if self.insertion_line and self.insertion_line.winfo_ismapped():
            self.insertion_line.place_forget()
        self._current_drag_target = None

    def handle_drop(self, widget):
        # Get the source category and the button data
        old_cat = str(widget.category_frame.category_name)
        btn_data = widget.btn_data

        # Determine the target category and insertion index
        if self._current_drag_target is not None:
            target_path, insert_index = self._current_drag_target
        else:
            # If dropped in an invalid area, do nothing.
            return

        # Get containers
        old_container = self.get_container_by_path(widget.category_frame.path)
        target_container = self.get_container_by_path(target_path)

        # Modify the data model: remove from old, insert into new
        if isinstance(old_container, dict):
            old_container['(按鈕)'].remove(btn_data)
        else: # It's a list
            old_container.remove(btn_data)

        if isinstance(target_container, dict):
            target_container.setdefault('(按鈕)', []).insert(insert_index, btn_data)
        else: # It's a list
            target_container.insert(insert_index, btn_data)

        self.save()
        # Instead of a full populate, just refresh the affected categories
        self.category_frames[tuple(widget.category_frame.path)].expand()
        if widget.category_frame.path != target_path:
            self.category_frames[tuple(target_path)].expand()

    # --- Window Opening ---

    def open_add_button_window(self, category_path):
        AddButtonWindow(self, category_path)

    def open_edit_window(self, btn_frame):
        EditButtonWindow(self, btn_frame)

    def move_button_to_new_category(self, btn_data, source_path, target_path):
        """Moves a button to a new category using paths."""
        # Get source container and remove button
        source_container = self.get_container_by_path(source_path)
        if isinstance(source_container, dict):
            source_container.get('(按鈕)', []).remove(btn_data)
        elif isinstance(source_container, list):
            source_container.remove(btn_data)

        # Get target container and add button
        target_container = self.get_container_by_path(target_path)
        if isinstance(target_container, list):
            # Convert button-only category to a mixed one if needed
            parent_container = self.get_container_by_path(target_path[:-1])
            parent_container[target_path[-1]] = OrderedDict({'(按鈕)': target_container}) # Corrected to half-width
            target_container = parent_container[target_path[-1]]
        
        target_container.setdefault('(按鈕)', []).append(btn_data)
        self.save()
        self.populate()

    def move_category_to_new_parent(self, source_path, new_parent_path):
        """Moves a category to a new parent category using paths."""
        source_container = self.get_container_by_path(source_path[:-1])
        source_name = source_path[-1]
        source_data = source_container.pop(source_name)

        target_container = self.get_container_by_path(new_parent_path)
        
        # If the target container is just a list of buttons, we need to convert it
        if isinstance(target_container, list):
            grandparent_container = self.get_container_by_path(new_parent_path[:-1])
            grandparent_container[new_parent_path[-1]] = OrderedDict({'(按鈕)': target_container}) # Corrected to half-width
            target_container = grandparent_container[new_parent_path[-1]]
        
        target_container[source_name] = source_data
        self.save()
        self.populate()

    def move_button(self, btn_data, category_path, direction):
        """Moves a button up or down within its category list."""
        container = self.get_container_by_path(category_path)

        button_list = []
        if isinstance(container, dict):
            button_list = container.get('(按鈕)', [])
        elif isinstance(container, list):
            button_list = container

        # --- 根本性修正 #1：從比對物件改為比對內容 (label) ---
        # 舊的錯誤方法: idx = button_list.index(btn_data)
        # 這會因為物件記憶體位置不同而永遠失敗。
        
        # 新的正確方法：透過唯一的 'label' 找到按鈕在列表中的索引
        target_label = btn_data.get('label')
        if not target_label:  # 如果按鈕沒有label，無法尋找
            return

        idx = -1
        for i, btn in enumerate(button_list):
            if btn.get('label') == target_label:
                idx = i
                break
        
        # 如果在列表中沒找到對應的按鈕，則直接返回
        if idx == -1:
            return

        new_idx = idx + direction
        if 0 <= new_idx < len(button_list):
            button_list.insert(new_idx, button_list.pop(idx))
            self.save()
            self.populate()

    # --- Category and Button Data Manipulation ---

    def move_category(self, path, direction):
        """Moves a category up or down within its parent's list of categories."""
        if not path:
            return

        parent_path = path[:-1]
        category_name = path[-1]
        parent_container = self.get_container_by_path(parent_path)

        # --- 最終解決方案：修改 _sort_order 列表 ---
        # 確保排序列表存在
        if '_sort_order' not in parent_container:
            parent_container['_sort_order'] = [k for k in parent_container.keys() if k not in ['(按鈕)', '_sort_order']]

        sort_order = parent_container['_sort_order']
        
        if category_name not in sort_order:
            return  # 如果在列表中找不到該分類，直接返回

        idx = sort_order.index(category_name)

        new_idx = idx + direction
        if 0 <= new_idx < len(sort_order):
            sort_order.insert(new_idx, sort_order.pop(idx))
            
            self.save()
            self.populate()

    # --- Iconify/Minimize Functionality ---

    def minimize_to_icon(self):
        if self.icon_window is not None:
            return
        self.withdraw()  # 隱藏主視窗
        self.icon_window = tk.Toplevel(self)

        # 不要視窗邊框並永遠顯示最前
        self.icon_window.overrideredirect(True)
        self.icon_window.attributes('-topmost', True)

        size = 50
        self.icon_window.geometry(f"{size}x{size}+{self.icon_pos_x}+{self.icon_pos_y}")

        self.penguin_button = tk.Button(self.icon_window, text="🐧", font=("Arial", 30), relief="flat", bg="white",
                                       activebackground="white", bd=0, cursor="hand2")
        self.penguin_button.pack(fill='both', expand=True)

        self.penguin_button.bind("<Double-Button-1>", self.restore_from_icon)  # 雙擊恢復主窗

        self.penguin_button.bind("<ButtonPress-1>", self.start_drag_icon)  # 拖曳開始
        self.penguin_button.bind("<B1-Motion>", self.do_drag_icon)  # 拖曳執行
        self.icon_window.bind("<ButtonPress-1>", self.start_drag_icon)
        self.icon_window.bind("<B1-Motion>", self.do_drag_icon)

    def start_drag_icon(self, event):
        self.icon_drag_start_x = event.x  # 拖曳起點X
        self.icon_drag_start_y = event.y  # 拖曳起點Y

    def do_drag_icon(self, event):
        x = self.icon_window.winfo_x() + (event.x - self.icon_drag_start_x)  # 新X座標
        y = self.icon_window.winfo_y() + (event.y - self.icon_drag_start_y)  # 新Y座標
        self.icon_window.geometry(f"+{x}+{y}")  # 移動企鵝視窗
        self.icon_pos_x = x  # 儲存新位置X
        self.icon_pos_y = y  # 儲存新位置Y

    def restore_from_icon(self, event=None):
        if self.icon_window:
            self.icon_window.destroy()
            self.icon_window = None
        # Call the same positioning method used at startup to ensure consistency.
        self.set_window_position()
        self.deiconify()  # 顯示主視窗
    
    def destroy(self):
        # 關閉程式前的保險儲存機制
        print("正在關閉程式並儲存最後狀態...")
        self.save()
        self.sio.disconnect()
        super().destroy()


if __name__ == '__main__':
    app = AutoPasteApp()
    app.mainloop()
