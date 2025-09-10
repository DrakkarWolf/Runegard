#!/usr/bin/env python3
import os
import sys
import json
import socket
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image
import pystray
import gi

# ⚔️ GI version declarations must come first
gi.require_version('Notify', '0.7')
gi.require_version('Gio', '2.0')
gi.require_version('GioUnix', '2.0')
from gi.repository import Notify, GLib, Gio

# -------------------- CONFIG --------------------
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".config", "Runegard", "listener_config.json")
os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        return {
            'start_in_tray': True,
            "port": 65432
        }

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

# -------------------- RESOURCE PATH --------------------
def resource_path(relative_path):
    """Get path to resource, works both in dev and PyInstaller bundle."""
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder
    except AttributeError:
        base_path = os.path.abspath(".")
    abs_path = os.path.join(base_path, relative_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"⚔️ Expected file but got directory or missing file: {abs_path}")
    return abs_path

# -------------------- RUNEGARD APP --------------------
class RunegardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Runegard Settings")
        self.root.geometry("300x225")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.apply_nord_theme()

        self.config = load_config()
        self.tray_var = tk.BooleanVar(value=self.config.get('start_in_tray', True))
        self.port_var = tk.IntVar(value=self.config.get("port", 65432))

        # --- Port configuration ---
        port_label = tk.Label(self.root, text="Listener Port:")
        port_label.pack(pady=(10,0))
        port_entry = ttk.Entry(self.root, textvariable=self.port_var)
        port_entry.pack(pady=(0,10), padx=20)

        ttk.Checkbutton(self.root, text="Start Minimized to Tray", variable=self.tray_var).pack(padx=10, pady=5, anchor='w')
        ttk.Button(self.root, text="Save Settings", command=self.save_and_apply).pack(pady=10)
        ttk.Button(self.root, text="Exit", command=self.exit_app).pack(pady=5)

        # ⚔️ GTK notifications
        Notify.init("Runegard")

        # Tray icon using pystray
        self.icon_image = Image.open(resource_path("raven.png"))
        self.create_tray_icon()

        self.running = True
        self.listener_thread = threading.Thread(target=self.listener_loop, daemon=True)
        self.listener_thread.start()

    # --- NORD THEME ---
    def apply_nord_theme(self):
        style = ttk.Style()
        style.theme_use('clam')
        self.root.configure(bg="#2E3440")
        style.configure("TLabel", background="#2E3440", foreground="#D8DEE9")
        style.configure("TCheckbutton", background="#2E3440", foreground="#D8DEE9")
        style.configure("TButton", background="#4C566A", foreground="#D8DEE9")
        style.configure("TEntry", fieldbackground="#434C5E", foreground="#D8DEE9")

    # --- WINDOW ---
    def hide_window(self):
        self.root.withdraw()

    def save_and_apply(self):
        self.config['start_in_tray'] = self.tray_var.get()
        self.config["port"] = self.port_var.get()
        save_config(self.config)
        messagebox.showinfo("Runegard", "Settings saved.")

    def exit_app(self):
        self.running = False
        if hasattr(self, "tray_icon"):
            self.tray_icon.stop()
        self.root.quit()

    # -------------------- TRAY ICON --------------------
    def create_tray_icon(self):
        menu = pystray.Menu(
            pystray.MenuItem("Open Runegard", lambda icon, item: self.root.deiconify()),
            pystray.MenuItem("Quit", lambda icon, item: self.exit_app())
        )
        self.tray_icon = pystray.Icon("runegard", self.icon_image, "Runegard", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    # --- NETWORK LISTENER ---
    def listener_loop(self):
        host = "0.0.0.0"
        port = self.config.get("port", 65432)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            s.listen()
            print("⚔️ Runegard listening for messages...")

            while self.running:
                try:
                    s.settimeout(2.0)
                    conn, addr = s.accept()
                except socket.timeout:
                    continue

                with conn:
                    message = conn.recv(1024).decode().strip()
                    print(f"📜 Message from {addr}: {message}")

                    # ⚔️ Send Linux notification
                    n = Notify.Notification.new("Runegard", message)
                    n.show()

# -------------------- MAIN --------------------
def main():
    root = tk.Tk()
    app = RunegardApp(root)
    if app.config.get('start_in_tray', True):
        root.withdraw()  # Start minimized if enabled
    root.mainloop()

if __name__ == "__main__":
    main()