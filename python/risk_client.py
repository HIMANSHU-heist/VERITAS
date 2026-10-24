import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / "cpp" / "build" / "risk_engine"


def flatten_costs(c: dict) -> dict:
    return {
        "brokerage_pct": c["brokerage"]["pct"],
        "brokerage_max_inr": c["brokerage"]["max_per_order_inr"],
        "stt_sell_pct": c["stt_sell_pct"],
        "exchange_txn_pct": c["exchange_txn_pct"],
        "sebi_pct": c["sebi_pct"],
        "stamp_buy_pct": c["stamp_buy_pct"],
        "gst_pct": c["gst_pct"],
        "slippage_bps": c["slippage_bps"],
    }


class RiskEngine:
    def __init__(self, audit_path="audit/audit.jsonl", fresh=True):
        self.audit_path = ROOT / audit_path
        if fresh and self.audit_path.exists():
            self.audit_path.unlink()
        self.p = subprocess.Popen(
            [str(EXE)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, cwd=ROOT, bufsize=1,
        )
        costs = yaml.safe_load(open(ROOT / "configs" / "costs.yaml"))
        limits = yaml.safe_load(open(ROOT / "configs" / "limits.yaml"))
        self.send({
            "type": "config",
            "costs": flatten_costs(costs),
            "limits": limits,
            "audit_path": str(self.audit_path),
        })

    def send(self, req: dict) -> dict:
        self.p.stdin.write(json.dumps(req) + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())

    def verify(self) -> dict:
        out = subprocess.run([str(EXE), "--verify", str(self.audit_path)],
                             capture_output=True, text=True)
        return json.loads(out.stdout)

    def close(self):
        self.p.stdin.close()
        self.p.wait()