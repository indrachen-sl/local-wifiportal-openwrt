import os
import tempfile
import threading
import unittest
from unittest.mock import patch

from wifiportal import db, firewall, server


class RegressionTests(unittest.TestCase):
    def test_admin_password_rotation_invalidates_old_session_secret(self):
        settings = {"admin": {}}
        old_secret = server.SESSION_SECRET
        try:
            with patch.object(server, "load_settings", return_value=settings), \
                 patch.object(server, "save_settings"), \
                 patch.object(server, "append_log"):
                ok, _ = server.update_admin_password("new-password-123")
            self.assertTrue(ok)
            self.assertNotEqual(server.SESSION_SECRET, old_secret)
            self.assertEqual(server.SESSION_SECRET, settings["admin"]["session_secret"])
        finally:
            server.SESSION_SECRET = old_secret

    def test_realtime_api_requires_admin(self):
        class Request:
            path = "/admin/api/devices-realtime"
            called = False

            def require_admin(self):
                return False

            def admin_devices_realtime_api(self):
                self.called = True

        request = Request()
        server.Handler.do_GET(request)
        self.assertFalse(request.called)

    def test_database_transactions_keep_concurrent_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "vouchers.json")
            with patch.object(db, "DB_FILE", path):
                db.save_db({"vouchers": {}, "devices": {}, "logs": []})

                def add_voucher(index):
                    with db.db_transaction():
                        state = db.load_db()
                        state["vouchers"][str(index)] = {"code": str(index)}
                        db.save_db(state)

                threads = [threading.Thread(target=add_voucher, args=(index,)) for index in range(20)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
                self.assertEqual(len(db.load_db()["vouchers"]), 20)

    def test_intentional_shrink_updates_last_good(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "vouchers.json")
            with patch.object(db, "DB_FILE", path):
                original = {"vouchers": {str(index): {} for index in range(30)}}
                db.save_db(original)
                reduced = {"vouchers": {"0": {}}}
                with self.assertRaises(RuntimeError):
                    db.save_db(reduced)
                db.save_db(reduced, allow_shrink=True)
                self.assertEqual(len(db.load_json(path + ".last-good", {})["vouchers"]), 1)
                with open(path, "w", encoding="utf-8") as file:
                    file.write("{broken json")
                self.assertEqual(len(db.load_db()["vouchers"]), 1)

    def test_voucher_expiry_is_copied_to_bound_and_top_device(self):
        mac = "AA:BB:CC:DD:EE:FF"
        voucher = {"enabled": True, "expire_at": 1234567890, "devices": {mac: {"online": True}}}
        top = {"voucher_code": "CODE", "online": True}
        state = {"devices": {mac: top}}
        rows = server.sync_voucher_devices(state, "CODE", voucher, expiry=True)
        self.assertEqual(voucher["devices"][mac]["expire_at"], 1234567890)
        self.assertEqual(top["expire_at"], 1234567890)
        self.assertEqual(len(rows), 1)

    def test_qos_reports_failed_tc_rule(self):
        with patch.object(firewall, "qos_enabled", return_value=True), \
             patch.object(firewall, "qos_init", return_value=(True, "ok")), \
             patch.object(firewall, "qos_remove_device"), \
             patch.object(firewall, "qos_run", return_value=(1, "", "tc failed")), \
             patch.object(firewall, "append_log"):
            self.assertFalse(firewall.qos_apply_device("AA:BB:CC:DD:EE:FF", "192.168.10.2", 1024, 0))

    def test_print_expired_includes_used_voucher(self):
        class Request:
            path = "/admin/vouchers-print?status=expired"
            body = ""

            def send_html(self, body):
                self.body = body

        request = Request()
        state = {"vouchers": {"USED-CODE": {"first_used_at": 1, "expire_at": 2, "enabled": True}}}
        with patch.object(server, "load_db", return_value=state), \
             patch.object(server, "load_settings", return_value={}), \
             patch.object(server, "print_vouchers_page", side_effect=lambda vouchers, *args, **kwargs: str(len(vouchers))):
            server.Handler.show_admin_vouchers_print(request)
        self.assertEqual(request.body, "1")

    def test_restoring_sessions_skips_revoked_whitelist(self):
        mac = "AA:BB:CC:DD:EE:FF"
        state = {"whitelist": {}, "blacklist": {}, "vouchers": {},
                 "devices": {mac: {"online": True, "voucher_code": "WHITELIST"}}}
        with patch.object(firewall, "check_nft_table_exists", return_value=True), \
             patch.object(firewall, "load_db", return_value=state), \
             patch.object(firewall, "nft_add_whitelist") as allow:
            firewall.restore_firewall_sessions()
        allow.assert_not_called()


if __name__ == "__main__":
    unittest.main()
