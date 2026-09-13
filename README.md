# BNDGG Vault Pro 🛡️

A modern, secure, and portable password manager built with Python.

## Features
- **Industry-Grade Security**: Uses AES-128 (Fernet) encryption and 600,000 PBKDF2 iteration key derivation.
- **Modern UI**: Built with CustomTkinter for a sleek, responsive dark-mode interface.
- **Zero Knowledge**: Your master password is never stored; only you can unlock your vault.
- **Portable**: Your vault and encryption salt are stored in a single JSON file.
- **Smart Generator**: Integrated password generator with adjustable length.
- **Auto-Security**: Automatically clears your clipboard 30 seconds after copying a password.

## Security Disclosure
This app uses standard cryptographic primitives. Your data is encrypted locally. No data ever leaves your machine.
