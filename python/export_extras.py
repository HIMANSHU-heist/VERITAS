"""Veto report + agent lessons -> web/data/veto.json and web/data/lessons.json."""
import json

from python.risk_client import ROOT

OUT = ROOT / "web" / "data"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    v = ROOT / "results" / "veto_report.json"
    if v.exists():
        (OUT / "veto.json").write_text(v.read_text())
    lp = ROOT / "data" / "lessons.jsonl"
    rows = [json.loads(l) for l in open(lp) if l.strip()] if lp.exists() else []
    (OUT / "lessons.json").write_text(json.dumps(rows, ensure_ascii=False))
    print(f"wrote veto.json ({v.exists()}) and lessons.json ({len(rows)} lessons)")


if __name__ == "__main__":
    main()
