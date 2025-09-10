import os
import sys
import json
import socket
import threading
import time
import tkinter as tk
from tkinter import messagebox, PhotoImage
from tkinter import ttk
import winshell
import pystray
from PIL import Image
from notifypy import Notify
import ctypes

CONFIG_FILE = os.path.join(os.getenv('APPDATA'), 'runegard', 'listener_config.json')

# Make sure the directory exists before saving
os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

# Set App User Model ID (must be unique)
APP_ID = 'Runegard'

# This tells Windows who the app is for notifications
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        return {
            'start_in_tray': False,
            "port": 65432  # 🛡️ Default port
        }

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def get_icon_image():
    icon_path = resource_path('raven.png')
    return Image.open(icon_path)

class runegardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Runegard Settings")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.root.geometry("300x225")

        self.apply_nord_theme()

        self.config = load_config()
        self.tray_var = tk.BooleanVar(value=self.config.get('start_in_tray', True))

        # --- Port configuration ---
        port_label = tk.Label(self.root, text="Listener Port:", bg="#2E3440", fg="#D8DEE9")
        port_label.pack(pady=(10,0))

        self.port_var = tk.IntVar(value=self.config.get("port", 65432))
        port_entry = ttk.Entry(self.root, textvariable=self.port_var)
        port_entry.pack(pady=(0,10), padx=20)

        ttk.Checkbutton(self.root, text="Start Minimized to Tray", variable=self.tray_var).pack(padx=10, pady=5, anchor='w')

        self.start_on_login_var = tk.BooleanVar(value=self.is_startup_enabled())
        start_check = ttk.Checkbutton(self.root, text="Start on Login", variable=self.start_on_login_var)
        start_check.pack(padx=10, pady=5, anchor='w')

        ttk.Button(self.root, text="Save Settings", command=self.save_and_apply).pack(pady=10)
        ttk.Button(self.root, text="Exit", command=self.exit_app).pack(pady=5)

        self.notifier = Notify()
        self.notifier.application_name = "Runegard"
        self.notifier.icon = resource_path("raven.png")
        self.icon = pystray.Icon("runegard", get_icon_image(), "Runegard", self.create_menu())
        self.icon_thread = None
        self.listener_thread = None
        self.running = True

    def apply_nord_theme(self):
        style = ttk.Style()
        style.theme_use('clam')  # 'clam' supports custom colors

        nord_colors = {
            "bg": "#2E3440",
            "fg": "#D8DEE9",
            "accent": "#81A1C1",
            "button": "#4C566A",
            "entry": "#434C5E",
            "highlight": "#5E81AC"
        }

        self.root.configure(bg=nord_colors["bg"])

        style.configure("TLabel", background=nord_colors["bg"], foreground=nord_colors["fg"])
        style.configure("TCheckbutton", background=nord_colors["bg"], foreground=nord_colors["fg"])
        style.map("TCheckbutton",
                  background=[('active', nord_colors["bg"]), ('!active', nord_colors["bg"])],
                  foreground=[('active', nord_colors["fg"]), ('!active', nord_colors["fg"])])
        style.configure("TButton", background=nord_colors["button"], foreground=nord_colors["fg"])
        style.map("TButton", background=[("active", nord_colors["highlight"])])
        style.configure("TEntry", fieldbackground=nord_colors["entry"], foreground=nord_colors["fg"])

    def is_startup_enabled(self):
        startup = winshell.startup()
        shortcut_path = os.path.join(startup, "RunegardApp.lnk")
        return os.path.exists(shortcut_path)

    def create_startup_shortcut(self):
        startup = winshell.startup()
        shortcut_path = os.path.join(startup, "RunegardApp.lnk")
        target = sys.executable  # Path to python.exe or your .exe file
        script_path = os.path.abspath(sys.argv[0])  # This script's full path

        # If your program is a script, make shortcut run: python.exe "script_path"
        with winshell.shortcut(shortcut_path) as shortcut:
            shortcut.path = target
            shortcut.arguments = f'"{script_path}"'
            shortcut.working_directory = os.path.dirname(script_path)
            shortcut.description = "runegard Auto Start"
        print("✅ Startup shortcut created.")

    def remove_startup_shortcut(self):
        startup = winshell.startup()
        shortcut_path = os.path.join(startup, "runegardApp.lnk")
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)
            print("🗑️ Startup shortcut removed.")

    def create_menu(self):
        return pystray.Menu(
            pystray.MenuItem('Settings', self.show_window),
            pystray.MenuItem('Exit', self.exit_app)
        )

    def show_window(self, icon=None, item=None):
        self.root.after(0, self.root.deiconify)

    def hide_window(self):
        self.root.withdraw()

    def save_and_apply(self):
        self.config['start_in_tray'] = self.tray_var.get()
        self.config["port"] = self.port_var.get()

        if self.start_on_login_var.get():
            self.create_startup_shortcut()
        else:
            self.remove_startup_shortcut()

        save_config(self.config)
        messagebox.showinfo("runegard", "Settings saved.")

    def exit_app(self, icon=None, item=None):
        self.running = False
        self.icon.stop()
        self.root.quit()

    def wait_for_network(self, timeout=300):
        start = time.time()
        while time.time() - start < timeout and self.running:
            try:
                socket.gethostbyname('8.8.8.8')
                return True
            except socket.gaierror:
                time.sleep(3)
        return False

    def listener_loop(self):
        host = "0.0.0.0"
        port = self.config.get("port", 65432)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            s.listen()
            print("⚔️ runegard listening for messages...")

            while self.running:
                try:
                    s.settimeout(2.0)
                    conn, addr = s.accept()
                except socket.timeout:
                    continue

                with conn:
                    print(f"🛡️ Connection from {addr}")
                    message = conn.recv(1024).decode().strip()
                    print(f"📜 Message received: {message}")

                    self.notifier.title = "Runegard"
                    self.notifier.message = message
                    self.notifier.send()


    def run_tray_icon(self):
        self.icon.run()

    def start(self):
        if self.config.get('start_in_tray', True):
            self.root.withdraw()
        else:
            self.root.deiconify()

        net_ready = self.wait_for_network()
        if not net_ready:
            messagebox.showwarning("runegard", "Network not detected after timeout. Starting anyway.")

        self.icon_thread = threading.Thread(target=self.run_tray_icon, daemon=True)
        self.icon_thread.start()

        self.listener_thread = threading.Thread(target=self.listener_loop, daemon=True)
        self.listener_thread.start()

def main():
    root = tk.Tk()
    icon_path = resource_path('raven.png')
    icon_image = PhotoImage(file=icon_path)
    root.iconphoto(False, icon_image)
    app = runegardApp(root)
    app.start()
    root.mainloop()

if __name__ == '__main__':
    main()