import os
import shutil
import time
import json
from wifiportal.config import DB_FILE, SETTINGS_FILE
from wifiportal.utils import now

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return default

def save_json(path, data):
    parent = os.path.dirname(path) or "."
    base = os.path.basename(path)

    lock_path = path + ".lock"
    tmp = path + ".tmp." + str(os.getpid()) + "." + str(int(time.time() * 1000))
    prev = path + ".prev"

    lock_file = None

    try:
        lock_file = open(lock_path, "a+")
        try:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except Exception:
            pass

        if os.path.exists(path):
            try:
                shutil.copy2(path, prev)
                os.chmod(prev, 0o600)
            except Exception:
                pass

        with open(tmp, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2, sort_keys=True)
            file.write("\n")
            file.flush()
            try:
                os.fsync(file.fileno())
            except Exception:
                pass

        os.chmod(tmp, 0o600)

        with open(tmp, "r", encoding="utf-8") as check_file:
            json.load(check_file)

        os.replace(tmp, path)

        try:
            dir_fd = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            pass

    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

        try:
            if lock_file is not None:
                try:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                lock_file.close()
        except Exception:
            pass

def load_settings():
    return load_json(SETTINGS_FILE, {})

def save_settings(settings):
    save_json(SETTINGS_FILE, settings)

def _wp_strict_load_json_file(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)

def _wp_db_voucher_count(db):
    if not isinstance(db, dict):
        return 0
    vouchers = db.get("vouchers", {})
    if not isinstance(vouchers, dict):
        return 0
    return len(vouchers)

def _wp_db_device_count(db):
    if not isinstance(db, dict):
        return 0
    devices = db.get("devices", {})
    if not isinstance(devices, dict):
        return 0
    return len(devices)

def _wp_restore_db_from_known_good(reason=""):
    candidates = [
        DB_FILE + ".last-good",
        DB_FILE + ".prev",
        DB_FILE + ".manual-good",
    ]

    best_path = ""
    best_db = None
    best_vouchers = -1
    best_devices = -1

    for candidate in candidates:
        if not os.path.exists(candidate):
            continue
        try:
            candidate_db = _wp_strict_load_json_file(candidate)
            voucher_count = _wp_db_voucher_count(candidate_db)
            device_count = _wp_db_device_count(candidate_db)

            if voucher_count > best_vouchers:
                best_path = candidate
                best_db = candidate_db
                best_vouchers = voucher_count
                best_devices = device_count
        except Exception:
            continue

    if best_db is None or best_vouchers <= 0:
        return {}

    try:
        if os.path.exists(DB_FILE):
            bad_name = DB_FILE + ".bad-json-" + time.strftime("%Y%m%d-%H%M%S")
            shutil.copy2(DB_FILE, bad_name)
            try:
                os.chmod(bad_name, 0o600)
            except Exception:
                pass

        shutil.copy2(best_path, DB_FILE)
        try:
            os.chmod(DB_FILE, 0o600)
        except Exception:
            pass

        parent = os.path.dirname(DB_FILE) or "."
        try:
            dir_fd = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            pass

        print("WIFIPORTAL_DB_SELF_HEAL restored", DB_FILE, "from", best_path, "vouchers", best_vouchers, "devices", best_devices, "reason", reason)
    except Exception as error:
        print("WIFIPORTAL_DB_SELF_HEAL restore failed:", repr(error))

    return best_db

def load_db():
    try:
        db = _wp_strict_load_json_file(DB_FILE)
    except Exception as error:
        db = _wp_restore_db_from_known_good("main_db_load_failed:" + repr(error))

    if not isinstance(db, dict):
        db = _wp_restore_db_from_known_good("main_db_not_dict")

    if not isinstance(db, dict):
        db = {}

    db.setdefault("meta", {})
    db.setdefault("vouchers", {})
    db.setdefault("devices", {})
    db.setdefault("whitelist", {})
    db.setdefault("blacklist", {})
    db.setdefault("security_locks", {})
    db.setdefault("logs", [])
    return db

def save_db(db):
    db.setdefault("meta", {})
    db["meta"]["updated_at"] = now()

    try:
        last_good_file = DB_FILE + ".last-good"

        old_db = load_json(DB_FILE, {})
        old_vouchers = old_db.get("vouchers", {}) if isinstance(old_db, dict) else {}
        new_vouchers = db.get("vouchers", {}) if isinstance(db, dict) else {}

        old_count = len(old_vouchers) if isinstance(old_vouchers, dict) else 0
        new_count = len(new_vouchers) if isinstance(new_vouchers, dict) else 0

        last_good_db = load_json(last_good_file, {})
        last_good_vouchers = last_good_db.get("vouchers", {}) if isinstance(last_good_db, dict) else {}
        last_good_count = len(last_good_vouchers) if isinstance(last_good_vouchers, dict) else 0

        baseline_count = max(old_count, last_good_count)

        if baseline_count >= 10 and new_count <= max(3, baseline_count // 3):
            suspect = DB_FILE + ".suspect-shrink"
            try:
                save_json(suspect, db)
            except Exception:
                pass
            raise RuntimeError(
                "Refuse to overwrite voucher database: suspicious shrink "
                f"{baseline_count} -> {new_count}. Suspect data saved to {suspect}. "
                f"Last good database: {last_good_file}"
            )
    except RuntimeError:
        raise
    except Exception:
        old_count = 0
        new_count = 0
        last_good_count = 0
        last_good_file = DB_FILE + ".last-good"

    save_json(DB_FILE, db)

    try:
        saved_db = load_json(DB_FILE, {})
        saved_vouchers = saved_db.get("vouchers", {}) if isinstance(saved_db, dict) else {}
        saved_count = len(saved_vouchers) if isinstance(saved_vouchers, dict) else 0

        current_last_good_db = load_json(last_good_file, {})
        current_last_good_vouchers = current_last_good_db.get("vouchers", {}) if isinstance(current_last_good_db, dict) else {}
        current_last_good_count = len(current_last_good_vouchers) if isinstance(current_last_good_vouchers, dict) else 0

        if saved_count >= current_last_good_count or current_last_good_count < 10:
            save_json(last_good_file, saved_db)
    except Exception:
        pass

def append_log(event_type, message, voucher_code="", mac="", ip="", result="OK"):
    db = load_db()
    logs = db.setdefault("logs", [])
    logs.append({
        "time": now(),
        "type": event_type,
        "message": message,
        "voucher_code": voucher_code,
        "mac": mac,
        "ip": ip,
        "result": result
    })
    if len(logs) > 500:
        db["logs"] = logs[-500:]
    save_db(db)

def create_backup():
    backup_dir = "/etc/wifiportal/backup"
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_file = os.path.join(backup_dir, f"wifiportal-backup-{timestamp}.json")
    db = load_db()
    settings = load_settings()
    from wifiportal.utils import format_time
    data = {
        "created_at": now(),
        "created_time": format_time(now()),
        "version": 1,
        "settings": settings,
        "database": db
    }
    save_json(backup_file, data)
    return backup_file

def list_backups():
    backup_dir = "/etc/wifiportal/backup"
    items = []
    try:
        for name in os.listdir(backup_dir):
            if not name.endswith(".json"):
                continue
            full_path = os.path.join(backup_dir, name)
            if not os.path.isfile(full_path):
                continue
            items.append({
                "name": name,
                "path": full_path,
                "size": os.path.getsize(full_path),
                "mtime": int(os.path.getmtime(full_path))
            })
    except Exception:
        pass
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items

def cleanup_old_backups(keep=7):
    backups = list_backups()
    deleted = []
    for item in backups[keep:]:
        try:
            os.remove(item["path"])
            deleted.append(item["name"])
        except Exception:
            pass
    return deleted

def restore_backup_file(backup_name):
    backup_name = os.path.basename(str(backup_name or ""))
    backup_path = os.path.join("/etc/wifiportal/backup", backup_name)
    if not os.path.exists(backup_path):
        return False, "备份文件不存在"

    data = load_json(backup_path, {})
    if "database" not in data or "settings" not in data:
        return False, "备份文件格式错误"

    save_json(DB_FILE, data["database"])
    save_json(SETTINGS_FILE, data["settings"])
    return True, "备份已恢复"
