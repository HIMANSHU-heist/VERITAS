import sys


def sub(path, old, new, count=1):
    t = open(path, encoding="utf-8").read()
    if new and new in t:
        print("already applied:", path, repr(old[:48])); return
    if old in t:
        open(path, "w", encoding="utf-8").write(t.replace(old, new, count))
        print("patched:", path, repr(old[:48])); return
    if not new:
        print("already removed:", path, repr(old[:48])); return
    sys.exit(f"PATCH FAILED in {path}: text not found: {old[:80]!r}")
