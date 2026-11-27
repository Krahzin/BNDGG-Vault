# Legacy v1 sources (archived)

These are the original BNDGG Vault files, kept for reference. The v2 app does not
import anything from this folder.

| File | What it was |
|---|---|
| `password_manager.py` | CustomTkinter app |
| `crypto.py` | Argon2id + Fernet (AES-128-CBC + HMAC) |
| `storage.py` | `%APPDATA%\PasswordManager\vault.json` |
| `ui_dialogs.py` | Edit-entry dialog |
| `password_manager.spec` | Old PyInstaller spec |

Old vaults are still readable: create a new v2 vault, then use
**Settings → Vault → Import legacy v1…** and enter the old master password.
