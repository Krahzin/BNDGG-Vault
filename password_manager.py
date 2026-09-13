import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import secrets
import string
import json
import os
import sys
import threading
import time
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64

# --- CONFIG & PATHS ---
def get_data_dir():
    base = os.path.expanduser("~/AppData/Roaming") if sys.platform == 'win32' else os.path.expanduser("~/.local/share")
    data_dir = os.path.join(base, "PasswordManager")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def get_icon_path(icon_filename="bndgg.ico"):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, icon_filename)

DATA_DIR = get_data_dir()
DATA_FILE = os.path.join(DATA_DIR, "vault.json")
OLD_SALT_FILE = os.path.join(DATA_DIR, "vault.salt")

# --- CRYPTO LOGIC ---
def derive_key(master_password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600000)
    return base64.urlsafe_b64encode(kdf.derive(master_password.encode()))

def encrypt_password(key: bytes, password: str) -> str:
    return Fernet(key).encrypt(password.encode()).decode()

def decrypt_password(key: bytes, encrypted: str) -> str:
    return Fernet(key).decrypt(encrypted.encode()).decode()

def load_vault_data():
    if not os.path.exists(DATA_FILE): return {"salt": None, "canary": None, "entries": {}}
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            if "entries" not in data: return {"salt": None, "canary": None, "entries": data}
            return data
    except: return {"salt": None, "canary": None, "entries": {}}

def save_vault_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=2)

# --- EDIT DIALOG WINDOW ---
class EditDialog(ctk.CTkToplevel):
    def __init__(self, parent, service_name, current_password, on_save):
        super().__init__(parent)
        self.title("Edit Entry")
        self.geometry("450x350")
        self.on_save = on_save
        self.old_name = service_name
        self.attributes("-topmost", True)
        self.grid_columnconfigure(0, weight=1)
        
        # Set icon for dialog too
        icon_path = get_icon_path()
        if os.path.exists(icon_path):
            try: self.after(200, lambda: self.iconbitmap(icon_path))
            except: pass

        ctk.CTkLabel(self, text="Edit Entry", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, pady=(20, 10))
        ctk.CTkLabel(self, text="Service Name:", font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=40, sticky="w")
        self.name_entry = ctk.CTkEntry(self, width=350); self.name_entry.grid(row=2, column=0, padx=40, pady=(0, 15), sticky="ew")
        self.name_entry.insert(0, service_name)
        ctk.CTkLabel(self, text="Password:", font=ctk.CTkFont(size=12)).grid(row=3, column=0, padx=40, sticky="w")
        self.pw_entry = ctk.CTkEntry(self, width=350); self.pw_entry.grid(row=4, column=0, padx=40, pady=(0, 15), sticky="ew")
        self.pw_entry.insert(0, current_password)
        btn_frame = ctk.CTkFrame(self, fg_color="transparent"); btn_frame.grid(row=5, column=0, pady=20)
        ctk.CTkButton(btn_frame, text="Save Changes", width=140, command=self.save_clicked).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", width=100, fg_color="#454545", command=self.destroy).pack(side="left", padx=10)

    def save_clicked(self):
        new_name, new_pw = self.name_entry.get().strip(), self.pw_entry.get()
        if new_name and new_pw: self.on_save(self.old_name, new_name, new_pw); self.destroy()

# --- MAIN APP ---
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BNDGG Vault Pro")
        self.geometry("1000x800"); self.minsize(800, 600)
        ctk.set_appearance_mode("dark"); ctk.set_default_color_theme("blue")
        
        # --- ICON LOADING ---
        icon_path = get_icon_path()
        if os.path.exists(icon_path):
            try:
                # after(200) helps CustomTkinter override the default icon on Windows
                self.after(200, lambda: self.iconbitmap(icon_path))
            except:
                pass

        self.key = None
        self.vault_data = {"salt": None, "canary": None, "entries": {}}

        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)

        # --- SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_propagate(False)
        ctk.CTkLabel(self.sidebar, text="BNDGG\nVAULT", font=ctk.CTkFont(size=26, weight="bold")).pack(pady=50)
        self.unlock_label = ctk.CTkLabel(self.sidebar, text="Status: Locked", text_color="gray", font=ctk.CTkFont(size=13))
        self.unlock_label.pack(pady=(0, 10))
        self.master_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Master Password", show="*", height=35)
        self.master_entry.pack(padx=25, pady=10, fill="x")
        self.master_entry.bind("<Return>", lambda e: self.unlock())
        self.unlock_btn = ctk.CTkButton(self.sidebar, text="Unlock Vault", height=35, font=ctk.CTkFont(weight="bold"), command=self.unlock)
        self.unlock_btn.pack(padx=25, pady=10, fill="x")

        ctk.CTkFrame(self.sidebar, height=2, fg_color="#333333").pack(padx=20, pady=20, fill="x")

        ctk.CTkButton(self.sidebar, text="Export Backup", fg_color="transparent", border_width=2, command=self.export_vault).pack(padx=25, pady=10, fill="x")
        ctk.CTkButton(self.sidebar, text="Import Backup", fg_color="transparent", border_width=2, command=self.import_vault).pack(padx=25, pady=10, fill="x")
        
        self.reset_btn = ctk.CTkButton(self.sidebar, text="Reset Vault", fg_color="#d9534f", hover_color="#c9302c", command=self.reset_vault_prompt)
        self.reset_btn.pack(padx=25, pady=(30, 10), fill="x")

        # --- MAIN CONTENT ---
        self.main_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        # Generator Card
        self.gen_card = ctk.CTkFrame(self.main_frame); self.gen_card.pack(fill="x", pady=10, padx=10)
        self.gen_card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.gen_card, text="Password Generator", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")
        self.len_slider = ctk.CTkSlider(self.gen_card, from_=8, to=64, number_of_steps=56)
        self.len_slider.grid(row=1, column=0, padx=20, pady=15, sticky="w"); self.len_slider.set(16)
        self.gen_output = ctk.CTkEntry(self.gen_card, placeholder_text="Generated Password", height=35)
        self.gen_output.grid(row=1, column=1, padx=10, pady=15, sticky="ew")
        self.gen_btn = ctk.CTkButton(self.gen_card, text="Generate", width=100, height=35, command=self.generate)
        self.gen_btn.grid(row=1, column=2, padx=20, pady=15)

        # Add Card
        self.save_card = ctk.CTkFrame(self.main_frame); self.save_card.pack(fill="x", pady=10, padx=10)
        self.save_card.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(self.save_card, text="Add New Service", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")
        self.svc_input = ctk.CTkEntry(self.save_card, placeholder_text="Service (e.g. Gmail)", height=35)
        self.svc_input.grid(row=1, column=0, padx=(20, 5), pady=15, sticky="ew")
        self.pw_input = ctk.CTkEntry(self.save_card, placeholder_text="Password", show="*", height=35)
        self.pw_input.grid(row=1, column=1, padx=5, pady=15, sticky="ew")
        self.save_btn = ctk.CTkButton(self.save_card, text="Save Entry", width=120, height=35, command=self.save_password)
        self.save_btn.grid(row=1, column=2, padx=20, pady=15)

        # List Card
        self.vault_card = ctk.CTkFrame(self.main_frame); self.vault_card.pack(fill="both", expand=True, pady=10, padx=10)
        search_row = ctk.CTkFrame(self.vault_card, fg_color="transparent"); search_row.pack(fill="x", padx=10, pady=(15, 5))
        self.search_input = ctk.CTkEntry(search_row, placeholder_text="🔍 Filter your vault...", height=35)
        self.search_input.pack(side="left", fill="x", expand=True, padx=10); self.search_input.bind("<KeyRelease>", lambda e: self.refresh_list())
        self.list_container = ctk.CTkFrame(self.vault_card, fg_color="#2b2b2b", corner_radius=6); self.list_container.pack(fill="both", expand=True, padx=20, pady=10)
        self.listbox = tk.Listbox(self.list_container, bg="#2b2b2b", fg="white", borderwidth=0, highlightthickness=0, font=("Segoe UI", 12), selectbackground="#1f538d", activestyle='none')
        self.listbox.pack(fill="both", expand=True, padx=5, pady=5)
        action_row = ctk.CTkFrame(self.vault_card, fg_color="transparent"); action_row.pack(fill="x", padx=20, pady=(5, 15))
        self.copy_btn = ctk.CTkButton(action_row, text="Show & Copy Password", height=35, command=self.retrieve_password); self.copy_btn.pack(side="left", padx=5)
        self.edit_btn = ctk.CTkButton(action_row, text="Edit Entry", height=35, fg_color="#454545", hover_color="#555555", command=self.open_edit_dialog); self.edit_btn.pack(side="left", padx=5)
        self.del_btn = ctk.CTkButton(action_row, text="Delete", height=35, fg_color="#d9534f", hover_color="#c9302c", command=self.delete_password); self.del_btn.pack(side="right", padx=5)

        # Status Bar
        self.status_bar = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color="#1a1a1a"); self.status_bar.grid(row=1, column=1, sticky="ew")
        self.status_label = ctk.CTkLabel(self.status_bar, text="Ready", font=ctk.CTkFont(size=11)); self.status_label.pack(side="left", padx=20)

        self.set_controls_state("disabled")

    # --- LOGIC ---
    def unlock(self):
        master_pw = self.master_entry.get()
        if not master_pw: return
        try:
            self.vault_data = load_vault_data()
            salt = base64.b64decode(self.vault_data["salt"]) if self.vault_data["salt"] else os.urandom(16)
            if not self.vault_data["salt"]: self.vault_data["salt"] = base64.b64encode(salt).decode()
            self.key = derive_key(master_pw, salt)
            if self.vault_data["canary"]:
                if decrypt_password(self.key, self.vault_data["canary"]) != "verified": raise ValueError()
            elif self.vault_data["entries"]:
                first = next(iter(self.vault_data["entries"]))
                decrypt_password(self.key, self.vault_data["entries"][first]["encrypted"])
            if not self.vault_data["canary"]: self.vault_data["canary"] = encrypt_password(self.key, "verified"); save_vault_data(self.vault_data)
            self.set_controls_state("normal"); self.refresh_list(); self.unlock_label.configure(text="Status: Unlocked", text_color="#47d147"); self.master_entry.delete(0, 'end'); self.update_status("Vault Unlocked")
        except: messagebox.showerror("Security", "Incorrect Master Password")

    def generate(self):
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        pw = ''.join(secrets.choice(chars) for _ in range(int(self.len_slider.get())))
        self.gen_output.delete(0, 'end'); self.gen_output.insert(0, pw)

    def save_password(self):
        svc, pw = self.svc_input.get().strip(), self.pw_input.get()
        if not svc or not pw: return
        self.vault_data["entries"][svc] = {"encrypted": encrypt_password(self.key, pw), "created": datetime.now().isoformat()}
        save_vault_data(self.vault_data); self.refresh_list(); self.svc_input.delete(0, 'end'); self.pw_input.delete(0, 'end'); self.update_status(f"Added '{svc}'")

    def retrieve_password(self):
        try:
            selection = self.listbox.curselection()
            if not selection: return
            svc = self.listbox.get(selection[0])
            dec = decrypt_password(self.key, self.vault_data["entries"][svc]["encrypted"])
            self.clipboard_clear(); self.clipboard_append(dec); self.update_status(f"Copied {svc} (30s timer)")
            threading.Thread(target=self.clear_clip_timer, args=(dec,), daemon=True).start()
        except: messagebox.showerror("Error", "Could not decrypt")

    def open_edit_dialog(self):
        try:
            sel = self.listbox.curselection()
            if not sel: return
            svc = self.listbox.get(sel[0])
            dec = decrypt_password(self.key, self.vault_data["entries"][svc]["encrypted"])
            EditDialog(self, svc, dec, self.on_save_edit)
        except: pass

    def on_save_edit(self, old, new, pw):
        if old != new: del self.vault_data["entries"][old]
        self.vault_data["entries"][new] = {"encrypted": encrypt_password(self.key, pw), "created": datetime.now().isoformat()}
        save_vault_data(self.vault_data); self.refresh_list(); self.update_status(f"Updated '{new}'")

    def clear_clip_timer(self, p):
        time.sleep(30); self.after(0, lambda: self.root_clear_clip(p))

    def root_clear_clip(self, p):
        try:
            if self.clipboard_get() == p: self.clipboard_clear(); self.update_status("Clipboard cleared")
        except: pass

    def refresh_list(self):
        self.listbox.delete(0, 'end')
        for svc in sorted(self.vault_data.get("entries", {}).keys(), key=str.lower):
            if self.search_input.get().lower() in svc.lower(): self.listbox.insert('end', svc)

    def set_controls_state(self, state):
        for w in [self.gen_btn, self.save_btn, self.copy_btn, self.edit_btn, self.del_btn, self.svc_input, self.pw_input, self.search_input, self.len_slider]: w.configure(state=state)

    def update_status(self, msg): self.status_label.configure(text=msg)

    def delete_password(self):
        try:
            sel = self.listbox.curselection()
            if not sel: return
            svc = self.listbox.get(sel[0])
            if messagebox.askyesno("Confirm Delete", f"Delete '{svc}'?"): del self.vault_data["entries"][svc]; save_vault_data(self.vault_data); self.refresh_list(); self.update_status(f"Deleted '{svc}'")
        except: pass

    def export_vault(self):
        if not self.key: return
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if path:
            with open(path, "w") as f: json.dump(self.vault_data, f, indent=2)
            messagebox.showinfo("Export", "Backup created.")

    def import_vault(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path: return
        try:
            with open(path, "r") as f: data = json.load(f)
            if "entries" not in data or "salt" not in data: raise ValueError()
            if messagebox.askyesno("Confirm", "Overwrite current vault?"): self.vault_data = data; save_vault_data(self.vault_data); messagebox.showinfo("Success", "Vault imported. Please unlock."); self.set_controls_state("disabled"); self.refresh_list()
        except: messagebox.showerror("Error", "Invalid vault file")

    def reset_vault_prompt(self):
        if messagebox.askyesno("RESET VAULT", "WARNING: This will PERMANENTLY DELETE all passwords in this vault.\n\nAre you sure you want to proceed?"):
            if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
            if os.path.exists(OLD_SALT_FILE): os.remove(OLD_SALT_FILE)
            self.vault_data = {"salt": None, "canary": None, "entries": {}}
            self.key = None
            self.refresh_list()
            self.set_controls_state("disabled")
            self.unlock_label.configure(text="Status: Locked", text_color="gray")
            self.update_status("Vault has been wiped.")

if __name__ == "__main__":
    app = App()
    app.mainloop()
