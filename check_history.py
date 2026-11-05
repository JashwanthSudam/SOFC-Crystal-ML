"""Run from the project folder:  python check_history.py
Checks the files, the database and any server running on port 5000/5001, then prints a verdict."""
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
print("Project folder :", HERE)

def has(path, text):
    try:
        return text in (HERE / path).read_text(encoding="utf-8")
    except Exception:
        return False

files_ok = {
    "app.py saves with IST + status": has("app.py", "def _save("),
    "auth.py stores IST":            has("auth.py", "+05:30"),
    "result.html shows save status": has("static/result.html", "Saved to your history"),
    "history.html loads ui.js":      has("static/history.html", "ui.js"),
}
for k, v in files_ok.items():
    print(f"  [{'OK' if v else 'OLD FILE'}] {k}")

# 1. write and read back directly through the database code
try:
    sys.path.insert(0, str(HERE))
    import auth
    auth.init()
    print("Database file  :", auth.DB)
    uid = auth.conn().execute("SELECT id FROM users LIMIT 1").fetchone()
    if uid:
        n0 = len(auth.list_searches(uid[0]))
        sid = auth.add_search(uid[0], "name", "CHECK-TEST", 800, "svr", -6.0, 1e-6)
        n1 = len(auth.list_searches(uid[0]))
        auth.delete_search(uid[0], sid)
        print(f"  [{'OK' if n1 == n0 + 1 else 'FAIL'}] direct database save/read ({n0} -> {n1} rows)")
    else:
        print("  (no users yet; sign up in the app first)")
    print("  Total saved searches in this database:", auth.count_searches() if hasattr(auth, "count_searches") else "n/a")
except Exception as exc:
    print("  [FAIL] database check:", exc)

# 2. ask whatever server is running
for port in (5000, 5001):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=3) as r:
            h = json.loads(r.read())
        new = "history_saving" in h
        print(f"Server on port {port}: {'NEW version' if new else 'OLD version (restart needed)'}; "
              f"saved_searches_total={h.get('saved_searches_total')}")
    except Exception as exc:
        print(f"Server on port {port}: not reachable ({type(exc).__name__})")
