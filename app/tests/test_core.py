"""Core tests — run with: .venv\\Scripts\\python -m unittest discover -s tests"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bndgg.core import crypto, generator, totp  # noqa: E402
from bndgg.core.strength import estimate  # noqa: E402
from bndgg.core.vault import Entry, Vault  # noqa: E402


class CryptoTest(unittest.TestCase):
    def test_roundtrip(self) -> None:
        header = crypto.new_header()
        key = crypto.derive_key("correct horse battery staple", header)
        envelope = crypto.seal(header, key, {"hello": "world"})
        key2, payload, _ = crypto.open_envelope(envelope, "correct horse battery staple")
        self.assertEqual(key, key2)
        self.assertEqual(payload["hello"], "world")

    def test_wrong_password(self) -> None:
        header = crypto.new_header()
        key = crypto.derive_key("right", header)
        envelope = crypto.seal(header, key, {"a": 1})
        with self.assertRaises(crypto.InvalidPassword):
            crypto.open_envelope(envelope, "wrong")

    def test_tampered_payload(self) -> None:
        header = crypto.new_header()
        key = crypto.derive_key("pw", header)
        envelope = crypto.seal(header, key, {"a": 1})
        raw = bytearray(crypto.b64d(envelope["payload"]))
        raw[0] ^= 0xFF
        envelope["payload"] = crypto.b64e(bytes(raw))
        with self.assertRaises(crypto.InvalidPassword):
            crypto.open_envelope(envelope, "pw")

    def test_tampered_kdf_params(self) -> None:
        header = crypto.new_header()
        key = crypto.derive_key("pw", header)
        envelope = crypto.seal(header, key, {"a": 1})
        envelope["kdf"]["time_cost"] = 1  # header is authenticated as AAD
        with self.assertRaises(crypto.InvalidPassword):
            crypto.open_envelope(envelope, "pw")

    def test_rejects_absurd_kdf(self) -> None:
        header = crypto.new_header()
        header["kdf"]["memory_cost"] = 10**9
        with self.assertRaises(crypto.VaultFormatError):
            crypto.derive_key("pw", header)


class VaultTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "vault.json"

    def tearDown(self) -> None:
        self.dir.cleanup()

    def test_create_add_unlock(self) -> None:
        vault = Vault.create(self.path, "master-password-1")
        vault.add_entry(Entry(name="GitHub", username="me", password="s3cret!"))
        vault.add_entry(Entry(name="Mail", password="hunter2"))
        vault.lock()

        reopened = Vault(self.path)
        reopened.unlock("master-password-1")
        self.assertEqual(len(reopened.entries), 2)
        self.assertEqual(reopened.find_by_name("github").username, "me")

    def test_wrong_password(self) -> None:
        Vault.create(self.path, "master-password-1")
        with self.assertRaises(crypto.InvalidPassword):
            Vault(self.path).unlock("nope")

    def test_file_is_valid_json_and_has_no_plaintext(self) -> None:
        vault = Vault.create(self.path, "master-password-1")
        vault.add_entry(Entry(name="Bank", password="TopSecret123!"))
        raw = self.path.read_text(encoding="utf-8")
        data = json.loads(raw)
        self.assertEqual(data["format"], "bndgg-vault")
        self.assertNotIn("TopSecret123!", raw)
        self.assertNotIn("Bank", raw)

    def test_backup_created_on_save(self) -> None:
        vault = Vault.create(self.path, "master-password-1")
        vault.add_entry(Entry(name="One", password="a"))
        vault.add_entry(Entry(name="Two", password="b"))
        self.assertTrue(self.path.with_name("vault.json.bak").exists())

    def test_change_master_password(self) -> None:
        vault = Vault.create(self.path, "master-password-1")
        vault.add_entry(Entry(name="X", password="y"))
        vault.change_master_password("master-password-1", "master-password-2")
        vault.lock()
        reopened = Vault(self.path)
        with self.assertRaises(crypto.InvalidPassword):
            reopened.unlock("master-password-1")
        reopened.unlock("master-password-2")
        self.assertEqual(len(reopened.entries), 1)

    def test_update_keeps_history(self) -> None:
        vault = Vault.create(self.path, "master-password-1")
        entry = vault.add_entry(Entry(name="X", password="old-pass"))
        updated = Entry.from_dict(entry.to_dict())
        updated.password = "new-pass"
        vault.update_entry(entry.id, updated)
        self.assertEqual(vault.get(entry.id).history[0]["password"], "old-pass")

    def test_export_and_import(self) -> None:
        source = Vault.create(Path(self.dir.name) / "a.json", "pw-source-1")
        source.add_entry(Entry(name="Alpha", password="one"))
        backup = Path(self.dir.name) / "backup.json"
        source.export_encrypted(backup)

        target = Vault.create(Path(self.dir.name) / "b.json", "pw-target-1")
        count = target.import_encrypted(backup, "pw-source-1", merge=True)
        self.assertEqual(count, 1)
        self.assertIsNotNone(target.find_by_name("Alpha"))

    def test_search_and_tags(self) -> None:
        vault = Vault.create(self.path, "master-password-1")
        vault.add_entry(Entry(name="GitHub", username="octocat", tags=["work"]))
        vault.add_entry(Entry(name="Reddit", tags=["fun"]))
        self.assertEqual(len(vault.sorted_entries("octo")), 1)
        self.assertEqual(len(vault.sorted_entries(tag="fun")), 1)
        self.assertEqual(vault.all_tags(), ["fun", "work"])


class GeneratorTest(unittest.TestCase):
    def test_class_guarantees(self) -> None:
        for _ in range(50):
            value = generator.generate_password(12)
            self.assertTrue(any(c.isupper() for c in value))
            self.assertTrue(any(c.islower() for c in value))
            self.assertTrue(any(c.isdigit() for c in value))
            self.assertTrue(any(not c.isalnum() for c in value))
            self.assertEqual(len(value), 12)

    def test_length_bounds(self) -> None:
        self.assertEqual(len(generator.generate_password(1)), 4)
        self.assertEqual(len(generator.generate_password(500)), 128)

    def test_exclude_ambiguous(self) -> None:
        for _ in range(20):
            value = generator.generate_password(40, exclude_ambiguous=True)
            self.assertFalse(any(c in generator.AMBIGUOUS for c in value))

    def test_passphrase(self) -> None:
        phrase = generator.generate_passphrase(4, separator="-")
        self.assertEqual(len(phrase.split("-")), 4)


class StrengthTest(unittest.TestCase):
    def test_ordering(self) -> None:
        self.assertLess(estimate("password").score, estimate("Tr0ub4dor&3").score)
        self.assertLess(estimate("abc123").score, estimate("vN7$kQ2!mR9@wZ4#").score)

    def test_empty(self) -> None:
        self.assertEqual(estimate("").score, 0)

    def test_crack_time_is_text(self) -> None:
        self.assertIsInstance(estimate("correct horse battery staple").crack_time, str)


class TotpTest(unittest.TestCase):
    def test_rfc_vector(self) -> None:
        secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
        self.assertEqual(totp.code(secret, at=59), "287082")

    def test_otpauth_url(self) -> None:
        url = ("otpauth://totp/Example:me?secret=JBSWY3DPEHPK3PXP"
               "&issuer=Example")
        self.assertEqual(totp.normalize_secret(url), "JBSWY3DPEHPK3PXP")
        self.assertTrue(totp.is_valid(url))


if __name__ == "__main__":
    unittest.main()
