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
from argon2 import low_level
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

# --- ADVANCED CRYPTO ---
def derive_key_argon2(master_password: str, salt: bytes) -> bytes:
    key = low_level.hash_secret_raw(
        secret=master_password.encode(),
        salt=salt,
        time_cost=3,
        memory_cost=65536,
        parallelism=4,
        hash_len=32,
        type=low_level.Type.ID
    )
    return base64.urlsafe_b64encode(key)

def encrypt_vault(key: bytes, data_dict: dict) -> str:
    f = Fernet(key)
    json_data = json.dumps(data_dict).encode()
    return f.encrypt(json_data).decode()

def decrypt_vault(key: bytes, encrypted_blob: str) -> dict:
    if not encrypted_blob: return {}
    f = Fernet(key)
    decrypted_data = f.decrypt(encrypted_blob.encode())
    return json.loads(decrypted_data.decode())

def load_physical_file():
    """Returns a safe dictionary, ensuring no critical keys are None."""
    default = {"salt": None, "canary": None, "vault_blob": None}
    if not os.path.exists(DATA_FILE): 
        return default
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            if not isinstance(data, dict): return default
            return data
    except Exception as e:
        print(f"Error loading physical file: {e}")
        return default

def save_physical_file(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# --- EDIT DIALOG ---
class EditDialog(ctk.CTkToplevel):
    def __init__(self, parent, service_name, current_password, on_save):
        super().__init__(parent)
        self.title("Edit Entry")
        self.geometry("450x350")
        self.on_save = on_save
        self.old_name = service_name
        self.attributes("-topmost", True)
        self.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self, text="Edit Entry", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, pady=(20, 10))
        self.name_entry = ctk.CTkEntry(self, width=350); self.name_entry.grid(row=1, column=0, padx=40, pady=10, sticky="ew")
        self.name_entry.insert(0, service_name)
        self.pw_entry = ctk.CTkEntry(self, width=350, show="*"); self.pw_entry.grid(row=2, column=0, padx=40, pady=10, sticky="ew")
        self.pw_entry.insert(0, current_password)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent"); btn_frame.grid(row=3, column=0, pady=20)
        ctk.CTkButton(btn_frame, text="Update", width=140, command=self.save_clicked).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", width=100, fg_color="#454545", command=self.destroy).pack(side="left", padx=10)

    def save_clicked(self):
        new_name, new_pw = self.name_entry.get().strip(), self.pw_entry.get()
        if new_name and new_pw: self.on_save(self.old_name, new_name, new_pw); self.destroy()

# --- MAIN APP ---
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BNDGG Vault Pro")
        self.geometry("1000x850")
        self.minsize(800, 700)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        icon_path = get_icon_path()
        if os.path.exists(icon_path):
            try: self.after(200, lambda: self.iconbitmap(icon_path))
            except Exception as e: print(f"Icon error: {e}")

        self.key = None
        self.entries = {}
        self.last_activity = time.time()
        self.auto_lock_minutes = 10

        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        self.setup_ui()
        
        threading.Thread(target=self.auto_lock_check, daemon=True).start()
        self.set_controls_state("disabled")

    def setup_ui(self):
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_propagate(False)
        ctk.CTkLabel(self.sidebar, text="BNDGG\nVAULT", font=ctk.CTkFont(size=28, weight="bold")).pack(pady=50)
        self.unlock_label = ctk.CTkLabel(self.sidebar, text="Status: Locked", text_color="gray")
        self.unlock_label.pack(pady=(0, 10))
        self.master_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Master Password", show="*", height=40)
        self.master_entry.pack(padx=25, pady=10, fill="x")
        self.master_entry.bind("<Return>", lambda e: self.unlock())
        self.unlock_btn = ctk.CTkButton(self.sidebar, text="Unlock Vault", height=40, font=ctk.CTkFont(weight="bold"), command=self.unlock)
        self.unlock_btn.pack(padx=25, pady=10, fill="x")
        ctk.CTkFrame(self.sidebar, height=2, fg_color="#333333").pack(padx=20, pady=20, fill="x")
        ctk.CTkButton(self.sidebar, text="Export Encrypted Backup", fg_color="transparent", border_width=2, command=self.export_vault).pack(padx=25, pady=10, fill="x")
        ctk.CTkButton(self.sidebar, text="Import Encrypted Backup", fg_color="transparent", border_width=2, command=self.import_vault).pack(padx=25, pady=10, fill="x")
        self.reset_btn = ctk.CTkButton(self.sidebar, text="Reset Vault", fg_color="#d9534f", hover_color="#c9302c", command=self.reset_vault_prompt)
        self.reset_btn.pack(padx=25, pady=(40, 10), fill="x")

        self.main_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        gen_card = ctk.CTkFrame(self.main_frame); gen_card.pack(fill="x", pady=10, padx=10); gen_card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(gen_card, text="Password Generator", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=20, pady=15, sticky="w")
        self.len_slider = ctk.CTkSlider(gen_card, from_=8, to=64, number_of_steps=56); self.len_slider.grid(row=1, column=0, padx=20, pady=15, sticky="w"); self.len_slider.set(16)
        self.gen_output = ctk.CTkEntry(gen_card, placeholder_text="Generated Password", height=40); self.gen_output.grid(row=1, column=1, padx=10, pady=15, sticky="ew")
        self.gen_btn = ctk.CTkButton(gen_card, text="Generate", width=120, height=40, command=self.generate); self.gen_btn.grid(row=1, column=2, padx=20, pady=15)

        save_card = ctk.CTkFrame(self.main_frame); save_card.pack(fill="x", pady=10, padx=10); save_card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(save_card, text="Add New Entry", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=20, pady=15, sticky="w")
        self.svc_input = ctk.CTkEntry(save_card, placeholder_text="Service Name", height=40); self.svc_input.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        pw_container = ctk.CTkFrame(save_card, fg_color="transparent"); pw_container.grid(row=1, column=1, padx=5, pady=10, sticky="ew"); pw_container.grid_columnconfigure(0, weight=1)
        self.pw_input = ctk.CTkEntry(pw_container, placeholder_text="Password", show="*", height=40); self.pw_input.grid(row=0, column=0, sticky="ew")
        self.toggle_btn = ctk.CTkButton(pw_container, text="👁", width=40, height=40, fg_color="#333333", command=self.toggle_visibility); self.toggle_btn.grid(row=0, column=1, padx=(5, 0))
        self.save_btn = ctk.CTkButton(save_card, text="Save Entry", width=120, height=40, command=self.save_password); self.save_btn.grid(row=1, column=2, padx=20, pady=10)

        self.vault_card = ctk.CTkFrame(self.main_frame); self.vault_card.pack(fill="both", expand=True, pady=10, padx=10)
        self.search_input = ctk.CTkEntry(self.vault_card, placeholder_text="🔍 Filter vault...", height=40); self.search_input.pack(fill="x", padx=20, pady=15); self.search_input.bind("<KeyRelease>", lambda e: self.refresh_list())
        self.listbox = tk.Listbox(self.vault_card, bg="#2b2b2b", fg="white", borderwidth=0, highlightthickness=0, font=("Segoe UI", 12), selectbackground="#1f538d", activestyle='none'); self.listbox.pack(fill="both", expand=True, padx=20, pady=10)
        action_row = ctk.CTkFrame(self.vault_card, fg_color="transparent"); action_row.pack(fill="x", padx=20, pady=15)
        self.copy_btn = ctk.CTkButton(action_row, text="Copy Password", height=40, command=self.retrieve_password); self.copy_btn.pack(side="left", padx=5)
        self.edit_btn = ctk.CTkButton(action_row, text="Edit", width=80, height=40, fg_color="#454545", command=self.open_edit_dialog); self.edit_btn.pack(side="left", padx=5)
        self.del_btn = ctk.CTkButton(action_row, text="Delete", width=80, height=40, fg_color="#d9534f", command=self.delete_password); self.del_btn.pack(side="right", padx=5)

        self.status_bar = ctk.CTkFrame(self, height=35, corner_radius=0, fg_color="#121212"); self.status_bar.grid(row=1, column=1, sticky="ew")
        self.status_label = ctk.CTkLabel(self.status_bar, text="Vault Locked", font=ctk.CTkFont(size=11)); self.status_label.pack(side="left", padx=20)

    def unlock(self):
        master_pw = self.master_entry.get()
        if not master_pw: return
        try:
            file_data = load_physical_file()
            raw_salt = file_data.get("salt")
            if raw_salt:
                salt = base64.b64decode(raw_salt)
            else:
                salt = os.urandom(16)
                file_data["salt"] = base64.b64encode(salt).decode()

            self.key = derive_key_argon2(master_pw, salt)
            
            if file_data.get("vault_blob"):
                self.entries = decrypt_vault(self.key, file_data["vault_blob"])
            else:
                self.entries = {}

            if file_data.get("canary"):
                canary = decrypt_vault(self.key, file_data["canary"])
                if canary.get("status") != "verified": raise ValueError("Canary mismatch")
            else:
                file_data["canary"] = encrypt_vault(self.key, {"status": "verified"})
                save_physical_file(file_data)

            self.set_controls_state("normal")
            self.refresh_list()
            self.unlock_label.configure(text="Status: Unlocked", text_color="#47d147")
            self.update_status("Unlocked")
            self.master_entry.delete(0, 'end')
        except Exception as e:
            print(f"Unlock error: {e}")
            self.key = None
            messagebox.showerror("Security", f"Incorrect Master Password\n\nDetails: {e}")

    def save_password(self):
        svc, pw = self.svc_input.get().strip(), self.pw_input.get()
        if not svc or not pw: return
        self.entries[svc] = {"password": pw, "created": datetime.now().isoformat()}
        file_data = load_physical_file()
        file_data["vault_blob"] = encrypt_vault(self.key, self.entries)
        save_physical_file(file_data)
        self.refresh_list()
        self.svc_input.delete(0, 'end')
        self.pw_input.delete(0, 'end')
        self.update_status(f"Saved {svc}")

    def export_vault(self):
        if not self.key:
            messagebox.showerror("Error", "Unlock the vault before exporting.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile="BNDGG_Backup.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            confirmoverwrite=True
        )
        if not path:
            return
        try:
            # Ensure physical file matches in-memory entries
            file_data = load_physical_file()
            file_data["vault_blob"] = encrypt_vault(self.key, self.entries)
            save_physical_file(file_data)

            # Export the whole encrypted vault (salt + canary + blob)
            with open(path, "w") as f:
                json.dump(file_data, f, indent=2)

            messagebox.showinfo("Export", "Encrypted backup created successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

    def import_vault(self):
        path = filedialog.askopenfilename(
            title="Select BNDGG Encrypted Backup",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)

            # Validate it's a real encrypted vault backup
            if not isinstance(data, dict) or "salt" not in data or "vault_blob" not in data:
                raise ValueError("This is not a valid BNDGG encrypted backup file.")

            if not messagebox.askyesno(
                "Confirm Import",
                "This will replace your current vault with the backup.\n\n"
                "You'll need to unlock it with the backup's master password.\n\nContinue?"
            ):
                return

            # Write the backup over the current vault file
            save_physical_file(data)

            # Lock the app so the user unlocks the new vault
            self.key = None
            self.entries = {}
            self.set_controls_state("disabled")
            self.refresh_list()
            self.unlock_label.configure(text="Status: Locked", text_color="gray")
            self.master_entry.delete(0, 'end')
            self.update_status("Imported - unlock with master password")

            messagebox.showinfo("Success", "Vault imported successfully!\n\nPlease unlock with the backup's master password.")
        except Exception as e:
            messagebox.showerror("Error", f"Import failed: {e}")

    def toggle_visibility(self):
        show = "" if self.pw_input.cget("show") == "*" else "*"
        self.pw_input.configure(show=show); self.toggle_btn.configure(text="🔒" if show == "" else "👁")

    def auto_lock_check(self):
        while True:
            time.sleep(30)
            if self.key and (time.time() - self.last_activity > self.auto_lock_minutes * 60):
                self.after(0, self.lock_vault)

    def lock_vault(self):
        self.key = None; self.entries = {}; self.set_controls_state("disabled"); self.refresh_list(); self.update_status("Locked")

    def reset_activity(self, e=None): self.last_activity = time.time()
    
    def generate(self):
        pw = ''.join(secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*") for _ in range(int(self.len_slider.get())))
        self.gen_output.delete(0, 'end'); self.gen_output.insert(0, pw)
        
    def refresh_list(self):
        self.listbox.delete(0, 'end'); term = self.search_input.get().lower()
        for s in sorted(self.entries.keys(), key=str.lower):
            if term in s.lower(): self.listbox.insert('end', s)
            
    def set_controls_state(self, s):
        for w in [self.gen_btn, self.save_btn, self.copy_btn, self.edit_btn, self.del_btn, self.svc_input, self.pw_input, self.search_input, self.len_slider, self.toggle_btn]: w.configure(state=s)
        
    def update_status(self, m): self.status_label.configure(text=m)
    
    def retrieve_password(self):
        try:
            sel = self.listbox.curselection(); svc = self.listbox.get(sel[0]); pw = self.entries[svc]["password"]
            self.clipboard_clear(); self.clipboard_append(pw); self.update_status("Copied!"); threading.Thread(target=self.clear_clip, args=(pw,), daemon=True).start()
        except Exception as e: print(f"Retrieve error: {e}")
        
    def clear_clip(self, p): time.sleep(30); self.after(0, lambda: self.safe_clear(p))
    
    def safe_clear(self, p):
        try:
            if self.clipboard_get() == p: self.clipboard_clear(); self.update_status("Cleared")
        except Exception as e: print(f"Clipboard clear error: {e}")
        
    def open_edit_dialog(self):
        try: 
            sel = self.listbox.curselection(); svc = self.listbox.get(sel[0]); EditDialog(self, svc, self.entries[svc]["password"], self.on_save_edit)
        except Exception as e: print(f"Edit dialog error: {e}")
        
    def on_save_edit(self, o, n, p):
        if o != n: del self.entries[o]
        self.entries[n] = {"password": p, "created": datetime.now().isoformat()}
        f = load_physical_file(); f["vault_blob"] = encrypt_vault(self.key, self.entries); save_physical_file(f); self.refresh_list()
        
    def delete_password(self):
        try:
            sel = self.listbox.curselection(); svc = self.listbox.get(sel[0])
            if messagebox.askyesno("Delete", f"Delete {svc}?"):
                del self.entries[svc]; f = load_physical_file(); f["vault_blob"] = encrypt_vault(self.key, self.entries); save_physical_file(f); self.refresh_list()
        except Exception as e: print(f"Delete error: {e}")
        
    def reset_vault_prompt(self):
        if messagebox.askyesno("WIPE", "Delete everything?"):
            if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
            self.lock_vault()

if __name__ == "__main__":
    app = App()
    app.bind_all("<Any-KeyPress>", app.reset_activity); app.bind_all("<Any-Button>", app.reset_activity)
    app.mainloop()