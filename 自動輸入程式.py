import gevent.monkey
gevent.monkey.patch_all()

import tkinter as tk  # 引入 tkinter 介面模組
from tkinter import simpledialog, messagebox  # 引入簡易對話框與訊息框
from tkinter import ttk, colorchooser # 引入 ttk 模組和顏色選擇器
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

# --- 版本與更新設定 ---
CURRENT_VERSION = "v1.0"  # *** 每次發布新版本時，請務必手動增加此版本號！ (例如 v1.1, v1.2) ***
GITHUB_REPO = "q724m9csnz-alt/Taipei_Hospital_Autopaste" # *** 請替換成您自己的 GitHub 專案路徑 ***


DATA_FILE = "buttons.json"  # 資料檔名

# --- 請將此處的網址換成您在 Render 上複製的網址 ---
SERVER_URL = "https://taipei-hospital-orthopedics-autopaste.onrender.com"

CHECKLIST_FILE = "checklist.json" # Checklist 資料檔名
DOCTORS_FILE = "doctors.json" # 醫師資料檔名

class AddPatientDialog(simpledialog.Dialog):
    """自訂對話框，用於一次性輸入病人的 ID, Name 和 Bed Number。"""
    def body(self, master):
        tk.Label(master, text="病人 ID:", font=("Segoe UI", 10)).grid(row=0, sticky='w')
        tk.Label(master, text="姓名:", font=("Segoe UI", 10)).grid(row=1, sticky='w')
        tk.Label(master, text="床號:", font=("Segoe UI", 10)).grid(row=2, sticky='w')

        self.id_entry = tk.Entry(master, font=("Segoe UI", 10))
        self.name_entry = tk.Entry(master, font=("Segoe UI", 10))
        self.bed_entry = tk.Entry(master, font=("Segoe UI", 10))

        self.id_entry.grid(row=0, column=1, padx=5, pady=2)
        self.name_entry.grid(row=1, column=1, padx=5, pady=2)
        self.bed_entry.grid(row=2, column=1, padx=5, pady=2)

        return self.id_entry # initial focus

    def validate(self):
        self.patient_id = self.id_entry.get().strip()
        if not self.patient_id:
            messagebox.showwarning("輸入錯誤", "病人 ID 不可為空。", parent=self)
            return 0
        return 1

    def apply(self):
        self.result = {
            "patient_id": self.patient_id,
            "patient_name": self.name_entry.get().strip(),
            "bed_number": self.bed_entry.get().strip()
        }

def ask_new_patient_info(parent):
    """
    開啟新增病人對話框並返回結果。
    """
    dialog = AddPatientDialog(parent, "新增病人")
    return dialog.result

class EditPatientDialog(simpledialog.Dialog):
    """自訂對話框，用於修改病人的 Name 和 Bed Number。"""
    def __init__(self, parent, title, patient_data):
        self.patient_data = patient_data
        super().__init__(parent, title)

    def body(self, master):
        tk.Label(master, text="病人 ID:", font=("Segoe UI", 10)).grid(row=0, sticky='w')
        id_label = tk.Label(master, text=self.patient_data.get('patient_id', ''), font=("Segoe UI", 10, "bold"))
        id_label.grid(row=0, column=1, padx=5, pady=2, sticky='w')

        tk.Label(master, text="姓名:", font=("Segoe UI", 10)).grid(row=1, sticky='w')
        tk.Label(master, text="床號:", font=("Segoe UI", 10)).grid(row=2, sticky='w')
        tk.Label(master, text="主治醫師:", font=("Segoe UI", 10)).grid(row=3, sticky='w')

        self.name_entry = tk.Entry(master, font=("Segoe UI", 10))
        self.name_entry.insert(0, self.patient_data.get('patient_name', ''))
        self.bed_entry = tk.Entry(master, font=("Segoe UI", 10))
        self.bed_entry.insert(0, self.patient_data.get('bed_number', ''))
        
        self.doctor_selector = ttk.Combobox(master, values=list(self.master.doctor_colors.keys()), state="readonly", font=("Segoe UI", 10))
        current_doctor = self.patient_data.get('attending_doctor', '未指派')
        self.doctor_selector.set(current_doctor)

        self.name_entry.grid(row=1, column=1, padx=5, pady=2)
        self.bed_entry.grid(row=2, column=1, padx=5, pady=2)
        self.doctor_selector.grid(row=3, column=1, padx=5, pady=2)

        return self.name_entry # initial focus

    def apply(self):
        self.result = {
            "patient_name": self.name_entry.get().strip(),
            "bed_number": self.bed_entry.get().strip(),
            "attending_doctor": self.doctor_selector.get()
        }

class DoctorManagerWindow(tk.Toplevel):
    """管理主治醫師及其顏色的視窗"""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("主治")
        self.geometry("350x400")
        self.transient(parent)
        self.focus_force()

        self.listbox = tk.Listbox(self, font=("Segoe UI", 10))
        self.listbox.pack(fill='both', expand=True, padx=10, pady=10)
        self.listbox.bind("<Double-Button-1>", self.edit_color)

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill='x', padx=10, pady=(0, 10))
        tk.Button(btn_frame, text="新增醫師", command=self.add_doctor).pack(side='left')
        tk.Button(btn_frame, text="刪除選定醫師", command=self.delete_doctor).pack(side='left', padx=10)
        tk.Button(btn_frame, text="關閉", command=self.destroy).pack(side='right')

        self.populate_list()

    def populate_list(self):
        self.listbox.delete(0, 'end')
        for doctor, color in self.parent.doctor_colors.items():
            if doctor == "未指派": continue # 不允許編輯"未指派"
            self.listbox.insert('end', doctor)
            self.listbox.itemconfig('end', {'fg': color})

    def add_doctor(self):
        doctor_name = simpledialog.askstring("新增醫師", "請輸入醫師姓名:", parent=self)
        if doctor_name and doctor_name.strip():
            doctor_name = doctor_name.strip()
            if doctor_name in self.parent.doctor_colors:
                messagebox.showerror("錯誤", "該醫師已存在。", parent=self)
                return
            self.parent.doctor_colors[doctor_name] = "#000000" # 預設黑色
            self.parent.save_doctors()
            self.populate_list()
            self.parent.update_patient_selector() # 更新主視窗的下拉選單

    def delete_doctor(self):
        selected_indices = self.listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("無效操作", "請先選擇一位要刪除的醫師。", parent=self)
            return
        
        doctor_name = self.listbox.get(selected_indices[0])
        if messagebox.askyesno("刪除確認", f"確定要刪除醫師 '{doctor_name}' 嗎？", parent=self):
            del self.parent.doctor_colors[doctor_name]
            self.parent.save_doctors()
            self.populate_list()
            self.parent.update_patient_selector() # 更新主視窗的下拉選單

    def edit_color(self, event):
        selected_indices = self.listbox.curselection()
        if not selected_indices: return
        doctor_name = self.listbox.get(selected_indices[0])
        
        color_code = colorchooser.askcolor(title=f"為 {doctor_name} 選擇顏色", initialcolor=self.parent.doctor_colors[doctor_name])
        if color_code[1]: # 如果使用者選擇了顏色
            self.parent.doctor_colors[doctor_name] = color_code[1]
            self.parent.save_doctors()
            self.populate_list()
            self.parent.update_patient_selector() # 更新主視窗的下拉選單

class ChecklistWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.withdraw() # 先隱藏主面板
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.config(bg="#f0f0f0", bd=2, relief='ridge') # --- 最終解決方案：設定固定的背景色 ---

        self.width = 300
        self.height = 400
        screen_w = self.winfo_screenwidth() # type: ignore
        screen_h = self.winfo_screenheight()
        # --- 最終解決方案：調整視窗位置，使其貼齊螢幕右側頂部 ---
        self.geometry(f"{self.width}x{self.height}+{screen_w - self.width}+{20}")

        self.all_patients_data = self.load_checklist()
        self.doctor_colors = self.load_doctors()
        self.patient_info_expanded = False # 預設病人資訊是收合的
        self.current_patient_id = self.all_patients_data.get("__current_patient_id__")
        self.tooltip_window = None # 用於備註提示
        self.run_daily_task_automation() # 執行每日自動化任務

        self.patient_listbox_popup = None # 用於自訂的下拉列表
        self.create_widgets()
        self.update_patient_selector()
        
        # --- 建立滑動把手 ---
        self.handle = tk.Toplevel(app)
        self.handle.overrideredirect(True)
        self.handle.attributes('-topmost', True)
        self.handle.geometry(f"30x100+{screen_w - 30}+{screen_h // 2 - 50}")
        handle_button = tk.Button(self.handle, text="待\n辦", command=self.show_panel, bg="#f39c12", fg="white", relief="flat", font=("Segoe UI", 10, "bold"))
        handle_button.pack(fill='both', expand=True)

    def create_widgets(self):
        # --- 標題列 ---
        self.title_bar = tk.Frame(self, bg='#34495e', height=25)
        self.title_bar.pack(fill='x', pady=(0, 2)) # 增加底部間距
        tk.Label(self.title_bar, text="待辦清單", bg='#34495e', fg='white', font=("Segoe UI", 11, "bold")).pack(side='left', padx=10)
        
        # --- 將主要功能按鈕移至標題列 ---
        button_style = {'bg': '#5d6d7e', 'fg': 'white', 'relief': 'flat', 'font': ("Segoe UI", 9, "bold"), 'width': 5}
        tk.Button(self.title_bar, text="新增病人", command=self.add_new_patient, **button_style).pack(side='left', padx=(10, 2), pady=2)
        tk.Button(self.title_bar, text="刪除病人", command=self.delete_current_patient, **button_style).pack(side='left', padx=2, pady=2)
        tk.Button(self.title_bar, text="醫師列表", command=self.open_doctor_manager, **button_style).pack(side='left', padx=2, pady=2)

        tk.Button(self.title_bar, text='>', command=self.hide_panel, bg='#e74c3c', fg='white', relief='flat', font=("Segoe UI", 10, "bold"), width=3).pack(side='right', padx=5, pady=2)

        # --- 病人選擇器 ---
        self.selector_frame = tk.Frame(self, bg="#f0f0f0")
        self.selector_frame.pack(fill='x', padx=10, pady=(5, 5))
        # --- 最終解決方案：使用一個按鈕來觸發自訂的 Listbox 下拉選單 ---
        self.patient_selector_var = tk.StringVar()
        self.patient_selector_btn = tk.Button(self.selector_frame, textvariable=self.patient_selector_var, command=self.show_patient_listbox, anchor='w', justify='left', font=("Segoe UI", 10), relief='solid', bd=1)
        # --- 新增功能：綁定右鍵選單以標記病人 ---
        self.patient_selector_btn.bind("<Button-3>", self.show_patient_tag_menu)
        self.patient_selector_btn.pack(side='left', fill='x', expand=True)

        # --- 可收合的病人資訊區塊 ---
        self.patient_info_toggle_frame = tk.Frame(self, bg="#e0e0e0", cursor="hand2")
        self.patient_info_toggle_frame.pack(fill='x', padx=10, pady=(5,0))
        self.patient_info_toggle_label = tk.Label(self.patient_info_toggle_frame, text="顯示病人資訊 ▼", bg="#e0e0e0", font=("Segoe UI", 9))
        self.patient_info_toggle_label.pack(pady=2)
        self.patient_info_toggle_frame.bind("<Button-1>", self.toggle_patient_info)
        self.patient_info_toggle_label.bind("<Button-1>", self.toggle_patient_info)

        # --- 最終解決方案：將病人基本資訊備註欄放在可收合面板下方 ---
        notes_label_frame = tk.Frame(self, bg="#f0f0f0")
        notes_label_frame.pack(fill='x', padx=10, pady=(5,0))
        tk.Label(notes_label_frame, text="病人基本資訊備註:", bg="#f0f0f0", font=("Segoe UI", 9)).pack(side='left')

        self.notes_text = tk.Text(self, height=4, font=("Segoe UI", 10), relief='solid', bd=1)
        self.notes_text.pack(fill='x', padx=10, pady=(0, 5))
        self.notes_text.bind("<KeyRelease>", self.on_notes_changed) # 綁定按鍵釋放事件以自動儲存


        # --- 病人資訊 ---
        self.patient_frame = tk.Frame(self, bg="#f0f0f0")
        # 預設不 pack，由 toggle_patient_info 控制
        tk.Label(self.patient_frame, text="ID:", bg="#f0f0f0", font=("Segoe UI", 10)).grid(row=0, column=0, sticky='w', pady=1)
        self.patient_id_var = tk.StringVar()
        self.patient_id_entry = tk.Entry(self.patient_frame, textvariable=self.patient_id_var, font=("Segoe UI", 10), state='readonly')
        self.patient_id_entry.grid(row=0, column=1, sticky='ew')
        rename_id_btn = tk.Button(self.patient_frame, text="重命名", command=self.rename_current_patient_id, font=("Segoe UI", 8), width=5)
        rename_id_btn.grid(row=0, column=2, sticky='e', padx=(5,0))

        tk.Label(self.patient_frame, text="Name:", bg="#f0f0f0", font=("Segoe UI", 10)).grid(row=1, column=0, sticky='w', pady=1)
        self.patient_name_var = tk.StringVar() # type: ignore
        self.patient_name_entry = tk.Entry(self.patient_frame, textvariable=self.patient_name_var, font=("Segoe UI", 10), state='readonly')
        self.patient_name_entry.grid(row=1, column=1, sticky='ew', columnspan=2)
        tk.Label(self.patient_frame, text="Bed No:", bg="#f0f0f0", font=("Segoe UI", 10)).grid(row=2, column=0, sticky='w', pady=1)
        self.bed_number_var = tk.StringVar()
        self.bed_number_entry = tk.Entry(self.patient_frame, textvariable=self.bed_number_var, font=("Segoe UI", 10), state='readonly')
        self.bed_number_entry.grid(row=2, column=1, sticky='ew', columnspan=2)
        edit_btn = tk.Button(self.patient_frame, text="修改資料", command=self.edit_current_patient, font=("Segoe UI", 8))
        edit_btn.grid(row=3, column=1, columnspan=2, sticky='e', pady=(5,0))

        self.patient_frame.grid_columnconfigure(1, weight=1)
        # 移除自動儲存的 trace，改為透過"修改資料"按鈕

        # --- 建立字型 ---
        self.font_normal = ("Segoe UI", 10)
        self.font_strikethrough = ("Segoe UI", 10, "overstrike")

        # --- 新增項目 (修正佈局：移到可滾動列表之前) ---
        self.add_frame = tk.Frame(self, bg="#f0f0f0")
        self.add_frame.pack(fill='x', padx=10, pady=5)
        self.new_item_entry = tk.Entry(self.add_frame, font=("Segoe UI", 10))
        self.new_item_entry.pack(side='left', fill='x', expand=True)
        self.new_item_entry.bind("<Return>", self.add_item)
        tk.Button(self.add_frame, text="新增", command=self.add_item, font=("Segoe UI", 9)).pack(side='right', padx=5)

        # --- 清單容器 (可滾動) ---
        list_container = tk.Frame(self)
        list_container.pack(fill='both', expand=True, padx=10, pady=5)
        canvas = tk.Canvas(list_container, bg="white", highlightthickness=0)
        scrollbar = tk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas, bg="white")
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- 最終解決方案：為 Checklist 新增獨立的滾動事件 ---
        def _on_checklist_mouse_wheel(event):
            if event.num == 4 or event.delta > 0:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5 or event.delta < 0:
                canvas.yview_scroll(1, "units")
        
        # 將滾動事件綁定到這個 Canvas 和其內部的 Frame
        canvas.bind("<MouseWheel>", _on_checklist_mouse_wheel)
        self.scrollable_frame.bind("<MouseWheel>", _on_checklist_mouse_wheel)

    def populate_checklist(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if not self.current_patient_id or self.current_patient_id not in self.all_patients_data:
            return

        current_patient = self.all_patients_data[self.current_patient_id]
        for i, item in enumerate(current_patient.get('items', [])):
            item_frame = tk.Frame(self.scrollable_frame, bg="white")
            item_frame.pack(fill='x', pady=2)

            var = tk.BooleanVar(value=item.get('checked', False))
            # --- 最終解決方案：根據勾選狀態決定是否使用刪除線字型 ---
            current_font = self.font_strikethrough if var.get() else self.font_normal
            chk = tk.Checkbutton(item_frame, text=item['text'], variable=var, bg="white", anchor='w', justify='left', wraplength=200, font=current_font)
            chk.pack(side='left', fill='x', expand=True, padx=(5,0))
            chk.config(command=lambda index=i, v=var: self.toggle_item(index, v))

            # --- 最終解決方案：綁定右鍵選單和懸停備註事件 ---
            item_frame.bind("<Button-3>", lambda event, index=i: self.show_item_context_menu(event, index))
            chk.bind("<Button-3>", lambda event, index=i: self.show_item_context_menu(event, index))
            self.create_tooltip(item_frame, item.get('note', ''))

            del_btn = tk.Button(item_frame, text="✕", command=lambda index=i: self.delete_item(index), fg="red", relief='flat', bg='white', font=("Segoe UI", 8))
            del_btn.pack(side='right', padx=5)

    def add_item(self, event=None):
        text = self.new_item_entry.get().strip()
        if text:
            if not self.current_patient_id:
                messagebox.showwarning("無效操作", "請先新增或選擇一位病人。", parent=self)
                return
            
            current_patient = self.all_patients_data[self.current_patient_id]
            current_patient.setdefault('items', []).append({'text': text, 'checked': False})
            self.new_item_entry.delete(0, 'end')
            self.save_checklist()
            self.populate_checklist()

    def delete_item(self, index):
        if not self.current_patient_id: return
        current_patient = self.all_patients_data[self.current_patient_id]
        items = current_patient.get('items', [])
        if 0 <= index < len(items):
            del items[index]
            self.save_checklist()
            self.populate_checklist()

    def toggle_item(self, index, var):
        if not self.current_patient_id: return
        current_patient = self.all_patients_data[self.current_patient_id]
        items = current_patient.get('items', [])
        if 0 <= index < len(items):
            items[index]['checked'] = var.get()
            self.save_checklist()
            # --- 最終解決方案：儲存後立即重繪列表以更新刪除線狀態 ---
            self.populate_checklist()

    def show_item_context_menu(self, event, index):
        """顯示待辦事項的右鍵選單"""
        if not self.current_patient_id: return
        
        context_menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 9))
        context_menu.add_command(label="修改任務", command=lambda: self.edit_item_text(index))
        context_menu.add_command(label="新增/修改備註", command=lambda: self.edit_item_note(index))
        context_menu.tk_popup(event.x_root, event.y_root)

    def edit_item_text(self, index):
        """修改待辦事項的文字"""
        current_patient = self.all_patients_data[self.current_patient_id]
        items = current_patient.get('items', [])
        if not (0 <= index < len(items)): return

        old_text = items[index]['text']
        new_text = simpledialog.askstring("修改任務", "請輸入新的任務內容:", initialvalue=old_text, parent=self)

        if new_text and new_text.strip() != old_text:
            items[index]['text'] = new_text.strip()
            self.save_checklist()
            self.populate_checklist()

    def edit_item_note(self, index):
        """新增或修改待辦事項的備註"""
        current_patient = self.all_patients_data[self.current_patient_id]
        items = current_patient.get('items', [])
        if not (0 <= index < len(items)): return

        old_note = items[index].get('note', '')
        new_note = simpledialog.askstring("新增/修改備註", "請輸入備註內容 (留空則刪除備註):", initialvalue=old_note, parent=self)

        if new_note is not None: # 確保使用者不是按了取消
            new_note = new_note.strip()
            items[index]['note'] = new_note
            self.save_checklist()
            self.populate_checklist() # 重新產生UI以更新tooltip

    def create_tooltip(self, widget, text):
        """為指定的 widget 建立懸停提示"""
        if not text: return # 如果沒有備註內容，則不建立提示

        def enter(event):
            if self.tooltip_window: self.tooltip_window.destroy()
            x = widget.winfo_rootx() # 與該任務的左側對齊
            y = widget.winfo_rooty() + widget.winfo_height() # 顯示在該任務的正下方
            self.tooltip_window = tw = tk.Toplevel(self)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            tw.attributes('-topmost', True)
            label = tk.Label(tw, text=text, justify='left', background="#ffffe0", relief='solid', borderwidth=1, wraplength=self.width - 10, font=("Segoe UI", 9))
            label.pack(ipadx=2, ipady=2)
        def leave(event):
            if self.tooltip_window: self.tooltip_window.destroy()
            self.tooltip_window = None
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    # --- 最終解決方案：修正病人資訊面板的顯示邏輯 ---
    def toggle_patient_info(self, event=None):
        """展開或收合病人詳細資訊面板"""
        if self.patient_info_expanded:
            self.patient_frame.pack_forget()
            self.patient_info_toggle_label.config(text="顯示病人資訊 ▼")
        else:
            self.patient_frame.pack(fill='x', padx=10, pady=5, before=self.new_item_entry.master)
            self.patient_info_toggle_label.config(text="隱藏病人資訊 ▲")
        self.patient_info_expanded = not self.patient_info_expanded

    def run_daily_task_automation(self):
        """在每天第一次開啟時，為所有病人新增 'Progress note' 任務"""
        today_str = time.strftime("%Y-%m-%d")
        last_run_date = self.all_patients_data.get("__last_daily_task_date__")

        if today_str != last_run_date:
            print(f"新的一天 ({today_str})，正在為所有病人新增 'Progress note' 任務...")
            task_to_add = "Progress note"
            for pid, pdata in self.all_patients_data.items():
                if isinstance(pdata, dict) and not pid.startswith("__"):
                    # 為避免重複，可以先檢查，但直接加入更符合每日任務的性質
                    pdata.setdefault('items', []).append({'text': task_to_add, 'checked': False, 'note': ''})
            
            self.all_patients_data["__last_daily_task_date__"] = today_str
            self.save_checklist() # 立即儲存變更

    def add_new_patient(self):
        new_patient_info = ask_new_patient_info(self)
        if not new_patient_info:
            return

        patient_id = new_patient_info["patient_id"]
        if patient_id in self.all_patients_data:
            messagebox.showerror("錯誤", "此病人 ID 已存在。", parent=self)
            return
        
        # --- 最終解決方案：為新病人建立預設的待辦事項 ---
        default_tasks = [
            {'text': 'Admission note', 'checked': False, 'note': ''},
            {'text': 'Progress note', 'checked': False, 'note': ''},
            {'text': '診斷書', 'checked': False, 'note': ''},
            {'text': 'Discharge note', 'checked': False, 'note': ''}
        ]

        self.all_patients_data[patient_id] = {
            'patient_id': patient_id, 
            'patient_name': new_patient_info["patient_name"], 
            'bed_number': new_patient_info["bed_number"], 
            'attending_doctor': '未指派', 
            'items': default_tasks,
            'tags': [] # --- 新增功能：初始化標籤列表 ---
        }
        self.current_patient_id = patient_id
        self.save_checklist()
        self.update_patient_selector()
        
    def edit_current_patient(self):
        if not self.current_patient_id:
            messagebox.showwarning("無效操作", "沒有選擇任何病人。", parent=self)
            return

        current_data = self.all_patients_data[self.current_patient_id]
        dialog = EditPatientDialog(self, "修改病人資料", current_data) # type: ignore
        if dialog.result:
            # 更新資料
            self.all_patients_data[self.current_patient_id]['patient_name'] = dialog.result['patient_name']
            self.all_patients_data[self.current_patient_id]['bed_number'] = dialog.result['bed_number']
            self.all_patients_data[self.current_patient_id]['attending_doctor'] = dialog.result['attending_doctor']
            # 儲存並刷新UI
            self.save_checklist()
            self.update_patient_details() # 更新顯示的詳細資料
            self.update_selector_display() # 更新下拉選單的顯示文字

    def open_doctor_manager(self):
        DoctorManagerWindow(self)

    def rename_current_patient_id(self):
        if not self.current_patient_id:
            messagebox.showwarning("無效操作", "沒有選擇任何病人。", parent=self)
            return

        new_id = simpledialog.askstring("重命名 ID", f"請為病人 '{self.current_patient_id}' 輸入新的 ID:", parent=self)
        if not new_id or not new_id.strip():
            return
        new_id = new_id.strip()

        if new_id == self.current_patient_id:
            return
        if new_id in self.all_patients_data:
            messagebox.showerror("錯誤", "新的病人 ID 已存在。", parent=self)
            return

        # 執行安全的 ID 替換
        self.all_patients_data[new_id] = self.all_patients_data.pop(self.current_patient_id)
        self.all_patients_data[new_id]['patient_id'] = new_id # 更新字典內部的ID
        self.current_patient_id = new_id
        self.save_checklist()
        self.update_patient_selector()

    def show_patient_listbox(self):
        """顯示自訂的病人選擇 Listbox"""
        if self.patient_listbox_popup and self.patient_listbox_popup.winfo_exists():
            self.patient_listbox_popup.destroy()
            return

        x = self.patient_selector_btn.winfo_rootx()
        y = self.patient_selector_btn.winfo_rooty() + self.patient_selector_btn.winfo_height()
        width = self.patient_selector_btn.winfo_width()

        self.patient_listbox_popup = popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.geometry(f"{width}x200+{x}+{y}")
        popup.attributes('-topmost', True)
        popup.bind("<FocusOut>", lambda e: popup.destroy())

        listbox = tk.Listbox(popup, font=("Segoe UI", 10), relief="solid", bd=1)
        listbox.pack(fill='both', expand=True)

        for pid, pdata in self.all_patients_data.items():
            if isinstance(pdata, dict) and not pid.startswith("__"):
                doctor = pdata.get('attending_doctor', '未指派')
                color = self.doctor_colors.get(doctor, self.doctor_colors.get("未指派", "#808080"))
                has_unchecked, tags_prefix, display_text = self.get_patient_display_text(pdata)
                prefix = "● " if has_unchecked else ""
                # --- 修改：在顯示文字前加上標籤符號 ---
                listbox.insert('end', f"{prefix}{tags_prefix}{display_text}")
                listbox.itemconfig('end', {'fg': color})

        def on_listbox_select(event):
            selected_indices = listbox.curselection()
            if selected_indices:
                self.on_patient_selected(listbox.get(selected_indices[0]))
            popup.destroy()

        listbox.bind("<<ListboxSelect>>", on_listbox_select)
        popup.focus_set()

    def delete_current_patient(self):
        if not self.current_patient_id:
            messagebox.showwarning("無效操作", "沒有選擇任何病人。", parent=self)
            return
        
        if messagebox.askyesno("刪除確認", f"確定要刪除病人 {self.current_patient_id} 的所有待辦事項嗎？\n此操作無法復原。", parent=self):
            del self.all_patients_data[self.current_patient_id]
            self.current_patient_id = None
            # 選擇列表中的第一個病人作為新的當前病人
            patient_ids = [k for k in self.all_patients_data if not k.startswith("__")]
            if patient_ids:
                self.current_patient_id = patient_ids[0]
            
            self.save_checklist()
            self.update_patient_selector()

    def on_patient_selected(self, selection):
        """當從自訂 Listbox 中選擇一個病人時觸發"""
        # --- 最終解決方案：修正從顯示文字中解析 ID 的邏輯 ---
        # 逐步移除所有可能的前綴，包括未完成符號和所有標記
        temp_selection = selection.lstrip("● ")
        temp_selection = temp_selection.lstrip("▲★") # 移除所有標記
        clean_selection = temp_selection.lstrip() # 移除剩餘的前導空格
        self.current_patient_id = clean_selection.split(' ')[0] # 取得 ID
        self.update_selector_display()
        # --- 最終解決方案：切換病人後，必須立即更新詳細資訊UI ---
        self.update_patient_details()
        # 接著再刷新該病人的待辦事項列表
        self.populate_checklist()
        self.save_checklist() # 儲存當前選擇

    def update_patient_selector(self):

        if self.current_patient_id and self.current_patient_id in self.all_patients_data:
            self.update_selector_display() # 使用統一的函式來設定顯示
        else:
            # 如果沒有當前病人，則清空顯示
            self.patient_selector_var.set(" 點此選擇病人...")

        self.update_patient_details()
        self.populate_checklist()

    def update_selector_display(self, *args):
        """僅更新主選擇按鈕的顯示文字"""
        if self.current_patient_id and self.current_patient_id in self.all_patients_data:
            current_patient_data = self.all_patients_data[self.current_patient_id]
            has_unchecked, tags_prefix, display_text = self.get_patient_display_text(current_patient_data)
            prefix = "● " if has_unchecked else ""
            # --- 修改：在顯示文字前加上標籤符號 ---
            self.patient_selector_var.set(f"{prefix}{tags_prefix}{display_text}")

    def on_notes_changed(self, event=None):
        """當備註文字框內容改變時觸發儲存"""
        if self.current_patient_id and self.current_patient_id in self.all_patients_data:
            notes = self.notes_text.get("1.0", "end-1c") # 獲取所有文字
            self.all_patients_data[self.current_patient_id]['general_notes'] = notes
            self.save_checklist()

    def get_patient_display_text(self, pdata):
        """根據病人資料產生標準的顯示文字"""
        pid = pdata.get('patient_id', '')
        name = pdata.get('patient_name', '')
        bed = pdata.get('bed_number', '')
        tags = pdata.get('tags', [])

        # --- 新增功能：根據標籤產生前綴符號 ---
        tags_prefix = ""
        if 'surgery' in tags:
            tags_prefix += "▲"
        if 'discharge' in tags:
            tags_prefix += "★"
        
        # --- 最終解決方案：檢查是否有未完成的待辦事項 ---
        has_unchecked_items = False
        for item in pdata.get('items', []):
            if not item.get('checked', False):
                has_unchecked_items = True
                break

        display_text = f"{pid} - {name}"
        if bed:
            display_text += f" ({bed})"
        
        return has_unchecked_items, tags_prefix, display_text

    def update_patient_details(self):
        if self.current_patient_id and self.current_patient_id in self.all_patients_data:
            current_patient_data = self.all_patients_data[self.current_patient_id]
            self.patient_id_var.set(current_patient_data.get('patient_id', ''))
            self.patient_name_var.set(current_patient_data.get('patient_name', ''))
            self.bed_number_var.set(current_patient_data.get('bed_number', ''))
            # 更新備註欄
            self.notes_text.delete("1.0", "end")
            self.notes_text.insert("1.0", current_patient_data.get('general_notes', ''))
        else:
            self.patient_id_var.set('')
            self.patient_name_var.set('')
            self.bed_number_var.set('')
            self.notes_text.delete("1.0", "end")

    def load_doctors(self):
        """載入醫師與顏色設定"""
        try:
            response = requests.get(f"{SERVER_URL}/api/doctors", timeout=10)
            # 如果伺服器回報檔案不存在 (404)，顯示特定錯誤
            if response.status_code == 404:
                messagebox.showerror("伺服器錯誤", "伺服器上找不到醫師資料檔案 (doctors.json)。", parent=self)
                return {"未指派": "#808080"} # 回傳預設值

            response.raise_for_status()
            data = response.json()
            # 即使 data 是空的 {}，也應該回傳，並在外部確保 '未指派' 存在
            if "未指派" not in data:
                data["未指派"] = "#808080"
            return data
        except requests.exceptions.RequestException as e:
            messagebox.showerror("網路錯誤", f"無法從雲端伺服器載入醫師資料: {e}", parent=self)
        return {"未指派": "#808080"}

    def save_doctors(self):
        """儲存醫師與顏色設定"""
        try:
            requests.post(f"{SERVER_URL}/api/doctors", json=self.doctor_colors, timeout=10)
        except requests.exceptions.RequestException as e:
            messagebox.showerror("網路錯誤", f"無法儲存醫師資料到雲端伺服器: {e}", parent=self)

    def load_checklist(self):
        """從伺服器載入待辦清單資料"""
        try:
            response = requests.get(f"{SERVER_URL}/api/checklist", timeout=10)
            # 如果伺服器回報檔案不存在 (404)，顯示特定錯誤
            if response.status_code == 404:
                messagebox.showerror("伺服器錯誤", "伺服器上找不到病人資料檔案 (checklist.json)。", parent=self)
                return {} # 回傳空字典

            response.raise_for_status()
            data = response.json()
            # 伺服器可能回傳一個空的 JSON 物件 {}，這是有效的
            return data
        except requests.exceptions.RequestException as e:
            messagebox.showerror("網路錯誤", f"無法從雲端伺服器載入待辦清單: {e}", parent=self)
        except json.JSONDecodeError:
            messagebox.showerror("資料錯誤", "從伺服器收到的待辦清單資料格式不正確。", parent=self)
        return {}

    def save_checklist(self):
        """將待辦清單資料儲存到伺服器"""
        self.all_patients_data["__current_patient_id__"] = self.current_patient_id
        try:
            # 使用 POST 請求將整個資料物件傳送到伺服器
            requests.post(f"{SERVER_URL}/api/checklist", json=self.all_patients_data, timeout=10)
        except requests.exceptions.RequestException as e:
            # 顯示錯誤訊息，但不中斷程式
            messagebox.showwarning("儲存失敗", f"無法將待辦清單同步到雲端伺服器:\n{e}", parent=self)

    def show_panel(self):
        self.handle.withdraw()
        self.deiconify()

    def hide_panel(self):
        self.withdraw()
        self.handle.deiconify()
    
    # --- 新增功能：病人標記相關函式 ---
    def show_patient_tag_menu(self, event):
        """在病人選擇器上顯示右鍵選單以進行標記"""
        if not self.current_patient_id:
            return

        context_menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 9))
        current_patient = self.all_patients_data[self.current_patient_id]
        tags = current_patient.get('tags', [])

        # 根據標籤是否存在顯示不同的標籤文字
        surgery_label = "✓ 開刀 (▲)" if 'surgery' in tags else "  開刀 (▲)"
        discharge_label = "✓ 今日出院 (★)" if 'discharge' in tags else "  今日出院 (★)"

        context_menu.add_command(label=surgery_label, command=lambda: self.toggle_patient_tag('surgery'))
        context_menu.add_command(label=discharge_label, command=lambda: self.toggle_patient_tag('discharge'))
        
        context_menu.tk_popup(event.x_root, event.y_root)

    def toggle_patient_tag(self, tag_name):
        """切換指定病人的標籤狀態"""
        current_patient = self.all_patients_data[self.current_patient_id]
        tags = current_patient.setdefault('tags', [])
        if tag_name in tags: tags.remove(tag_name)
        else: tags.append(tag_name)
        self.save_checklist()
        self.update_selector_display() # 更新按鈕上的顯示

    def handle_remote_update(self, new_data):
        """處理從伺服器收到的待辦清單更新"""
        self.all_patients_data = new_data
        self.current_patient_id = self.all_patients_data.get("__current_patient_id__")
        # 刷新整個UI
        self.update_patient_selector()
        self.update_patient_details()
        self.populate_checklist()

    def handle_remote_doctors_update(self, new_data):
        """處理從伺服器收到的醫師列表更新"""
        self.doctor_colors = new_data
        self.populate_list() # 如果 DoctorManagerWindow 開著，就更新它
        self.update_patient_selector() # 更新主視窗的下拉選單顏色

    def destroy(self):
        self.handle.destroy()
        super().destroy()


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
        # --- 最終解決方案：新增任何項目後，都執行一次完整的 populate 來刷新UI ---
        self.app.populate()
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
        # --- 最終解決方案：修改任何項目後，都執行一次完整的 populate 來刷新UI ---
        self.app.populate()
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

        # --- 最終解決方案：為按鈕及其父容器綁定滾動事件 ---
        self.bind("<MouseWheel>", self.app.on_mouse_wheel)
        self.main_button.bind("<MouseWheel>", self.app.on_mouse_wheel)

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

        # --- 最終解決方案：將滾動事件綁定到所有子元件，確保滾動無死角 ---
        self.bind("<MouseWheel>", self.app.on_mouse_wheel)
        self.header.bind("<MouseWheel>", self.app.on_mouse_wheel)
        self.label.bind("<MouseWheel>", self.app.on_mouse_wheel)
        self.content.bind("<MouseWheel>", self.app.on_mouse_wheel)

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
            # --- 最終解決方案：在建立選單時，明確跳過 _sort_order ---
            for name, content in [item for item in data_dict.items() if item[0] != '_sort_order']:
                if name == '(按鈕)': continue
                
                new_path = current_path + [name]
                # Prevent moving a category into itself or its own children
                # --- 最終解決方案：只在目標路徑與自身完全相同時才禁用 ---
                is_invalid_target = (new_path == self.path)
                label = "    " * len(current_path) + name
                
                if is_invalid_target: # 不能移動到自己裡面
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
            # 最終解決方案：統一顯示邏輯，使其也遵循 _sort_order
            sorted_keys = cdata.get('_sort_order', [k for k in cdata.keys() if k not in ['(按鈕)', '_sort_order']])

            for key in sorted_keys:
                if key not in cdata: continue
                value = cdata[key]
                sub_path = self.path + [key]
                sub_frame = CategoryFrame(self.content, key, self.app, self.depth + 1, sub_path)
                sub_frame.pack(fill='x', pady=1)
                self.subcategories[key] = sub_frame
            
            if '(按鈕)' in cdata:
                self.show_buttons(cdata['(按鈕)'])
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
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # 內部滾動框架，實際放置分類用
        self.inner_frame = tk.Frame(self.canvas, bg="#ffffff")  # Clean white background for the scrollable area content

        # 建立Canvas內部視窗，設定滾動視窗為內框架
        self.inner_frame_id = self.canvas.create_window((0, 0), window=self.inner_frame, anchor='nw')

        # 更新滾動區域大小
        self.inner_frame.bind("<Configure>", self.on_frame_configure)

        # 讓 inner_frame 的寬度跟隨 canvas 的寬度
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # --- 最終解決方案：將全域綁定改為區域性綁定 ---
        # 綁定滑鼠滾輪事件，僅對主程式的 Canvas 作垂直滾動
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # Windows / Mac OS
        # --- 最終解決方案：將滾動事件也綁定到內部框架，確保在框架上滾動也能觸發 ---
        self.inner_frame.bind("<MouseWheel>", self.on_mouse_wheel)


        self.populate()  # Initial population of categories

        self.icon_window = None
        self.icon_drag_start_x = 0
        self.icon_drag_start_y = 0

        # --- 最終解決方案：將企鵝圖示的預設位置移動到待辦清單圖示的下方 ---
        # 為了對齊，我們讓它們的右側邊緣都距離螢幕邊緣 30px
        self.icon_pos_x = screen_w - 30 # 新的把手寬度為 30
        self.icon_pos_y = (screen_h // 2) + 50 + 5 # 待辦清單圖示高度為100，中心點在 h/2，所以底部在 h/2+50。再加5px間距。

        # --- WebSocket 初始化 ---
        self.sio = socketio.Client()
        self.setup_socketio_events()

        # --- 為 ChecklistWindow 註冊 SocketIO 事件 ---
        @self.sio.on('checklist_updated')
        def on_checklist_updated(data):
            print("收到待辦清單更新，正在刷新...")
            if hasattr(self, 'checklist_window') and self.checklist_window:
                self.checklist_window.after(0, self.checklist_window.handle_remote_update, data)

        @self.sio.on('doctors_updated')
        def on_doctors_updated(data):
            print("收到醫師列表更新，正在刷新...")
            if hasattr(self, 'checklist_window') and self.checklist_window:
                self.checklist_window.after(0, self.checklist_window.handle_remote_doctors_update, data)

        self.connect_to_server()

        # --- 檢查更新 ---
        # 將檢查更新的邏輯移至UI初始化之後，以確保messagebox可以正常運作
        if self.check_for_updates():
            # 如果發現更新，則不繼續執行，直接退出
            # 在退出前，確保Checklist視窗也被銷毀
            if hasattr(self, 'checklist_window') and self.checklist_window:
                self.checklist_window.destroy()
            # 更新腳本會處理後續的重啟
            self.destroy() # 使用 destroy() 來安全地關閉視窗和連線
            return

        self.after(10, self.set_window_position)  # 程式啟動後延遲呼叫設定窗體位置，確保生效

        # --- 啟動 Checklist 視窗 ---
        self.checklist_window = ChecklistWindow(self)
        self.checklist_window.sio = self.sio # 將 socketio 客戶端傳遞給 checklist 視窗

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
                self.sio.connect(SERVER_URL, wait_timeout=45)
                self.sio.wait()
            except socketio.exceptions.ConnectionError as e:
                print(f"無法連接到伺服器: {e}")
                messagebox.showerror("連線錯誤", f"無法連接到伺服器 {SERVER_URL}。\n請確認伺服器正在執行且網路連線正常。")
        
        thread = threading.Thread(target=run)
        thread.daemon = True  # 設置為守護執行緒，主程式退出時會自動結束
        thread.start()

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.inner_frame_id, width=event.width)
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
                # --- 最終解決方案：在客戶端轉換結構時，就主動建立正確的 _sort_order ---
                new_content = OrderedDict()
                new_content['(按鈕)'] = container
                new_content[name] = OrderedDict()
                # --- 最終解決方案：_sort_order 只應包含真正的子分類，絕不能包含 '(按鈕)' ---
                new_content['_sort_order'] = [name]

                parent_container = self.get_container_by_path(parent_path[:-1])
                parent_container[parent_path[-1]] = new_content
            else:
                container[name] = OrderedDict() # 新增的分類應該是字典，以便未來可以新增子分類
                if '_sort_order' in container:
                    container['_sort_order'].append(name)

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

        # --- 修改：將企鵝圖示改為與待辦清單一致的滑動把手樣式 ---
        self.icon_window.overrideredirect(True)
        self.icon_window.attributes('-topmost', True)

        # 設定與待辦清單把手相同的尺寸
        self.icon_window.geometry(f"30x100+{self.icon_pos_x}+{self.icon_pos_y}")

        # 建立按鈕，設定新文字和顏色
        icon_button = tk.Button(self.icon_window, text="貼\n文", command=self.restore_from_icon, bg="#3498db", fg="white", relief="flat", font=("Segoe UI", 10, "bold"))
        icon_button.pack(fill='both', expand=True)

        # 綁定拖曳事件
        icon_button.bind("<ButtonPress-1>", self.start_drag_icon)
        icon_button.bind("<B1-Motion>", self.do_drag_icon)

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
        self.deiconify()  # 顯示主視窗
        self.set_window_position()
    
    def destroy(self):
        # 關閉程式前的保險儲存機制
        print("正在關閉程式並儲存最後狀態...")
        self.save()
        self.sio.disconnect()
        # 確保 Checklist 視窗也被正確關閉
        if hasattr(self, 'checklist_window') and self.checklist_window:
            self.checklist_window.destroy()
        super().destroy()
    
    # --- 自動更新邏輯 ---
    def check_for_updates(self):
        """檢查GitHub上是否有新版本，並執行更新。"""
        try:
            # 1. 獲取 GitHub Releases 的最新版本資訊
            api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            latest_release = response.json()
            latest_version = latest_release.get("tag_name")

            print(f"目前版本: {CURRENT_VERSION}, 最新版本: {latest_version}")

            # 2. 版本號比較
            if latest_version and latest_version > CURRENT_VERSION:
                if not messagebox.askyesno("發現新版本", f"發現新版本 {latest_version}！\n是否要立即更新？"):
                    return False

                # 3. 尋找 .exe 檔案的下載連結
                asset_url = None
                for asset in latest_release.get("assets", []):
                    if asset.get("name").endswith(".exe"):
                        asset_url = asset.get("browser_download_url")
                        break
                
                if not asset_url:
                    messagebox.showerror("更新錯誤", "在新版本中找不到 .exe 檔案。")
                    return False

                # 4. 下載新版本
                messagebox.showinfo("正在更新", "正在下載新版本，請稍候...\n程式下載完成後將會自動重啟。")
                
                exe_path = sys.executable
                new_exe_path = exe_path + ".new"
                
                with requests.get(asset_url, stream=True) as r:
                    r.raise_for_status()
                    with open(new_exe_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                
                # 5. 建立並執行替換腳本
                updater_script_path = "updater.bat"
                with open(updater_script_path, "w") as f:
                    f.write(f"""
@echo off
echo 等待主程式關閉...
timeout /t 2 /nobreak > nul
move /Y "{new_exe_path}" "{exe_path}"
echo 更新完成，正在重新啟動...
start "" "{exe_path}"
del "{updater_script_path}"
                    """)
                
                os.startfile(updater_script_path)
                return True # 返回 True 表示已啟動更新流程
        except Exception as e:
            print(f"檢查更新時發生錯誤: {e}")
            # 在啟動時，如果網路不通等原因導致檢查失敗，則靜默處理，不打擾使用者
        return False


if __name__ == '__main__':
    app = AutoPasteApp()
    app.mainloop()
