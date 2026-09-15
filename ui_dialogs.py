# ui_dialogs.py
import os
import customtkinter as ctk
from storage import get_icon_path

class EditDialog(ctk.CTkToplevel):
    def __init__(self, parent, service_name, current_password, on_save):
        super().__init__(parent)
        self.title("Edit Entry")
        self.geometry("450x350")
        self.on_save = on_save
        self.old_name = service_name
        self.attributes("-topmost", True)
        self.grid_columnconfigure(0, weight=1)

        icon_path = get_icon_path()
        if os.path.exists(icon_path):
            try:
                self.after(200, lambda: self.iconbitmap(icon_path))
            except Exception as e:
                print(f"Icon error: {e}")

        ctk.CTkLabel(self, text="Edit Entry", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, pady=(20, 10))

        self.name_entry = ctk.CTkEntry(self, width=350)
        self.name_entry.grid(row=1, column=0, padx=40, pady=10, sticky="ew")
        self.name_entry.insert(0, service_name)

        self.pw_entry = ctk.CTkEntry(self, width=350, show="*")
        self.pw_entry.grid(row=2, column=0, padx=40, pady=10, sticky="ew")
        self.pw_entry.insert(0, current_password)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, pady=20)
        ctk.CTkButton(btn_frame, text="Update", width=140, command=self.save_clicked).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", width=100, fg_color="#454545", command=self.destroy).pack(side="left", padx=10)

    def save_clicked(self):
        new_name, new_pw = self.name_entry.get().strip(), self.pw_entry.get()
        if not (new_name and new_pw):
            return
        self.on_save(self.old_name, new_name, new_pw)
        self.destroy()
