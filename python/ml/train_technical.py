"""Train LightGBM, calibrate conformal sets on a LATER window, evaluate on the latest window."""
import joblib
import numpy as np
from lightgbm import LGBMClassifier

from python.ml.conformal import calibrate, coverage, prediction_sets
from python.ml.features import build_dataset

ROUND_TRIP_COST_PCT = 0.146   # from the C++ risk engine output (2% position, equity intraday)
ALPHAS = [0.05, 0.1, 0.2, 0.3, 0.4, 0.5]


def main():
    X, feats = build_dataset()
    n = len(X)
    i1, i2 = int(n * 0.6), int(n * 0.8)
    tr, ca, te = X.iloc[:i1], X.iloc[i1:i2], X.iloc[i2:]
    print(f"rows={n}  train={len(tr)}  calib={len(ca)}  test={len(te)}")
    print(f"train {tr['date'].min().date()}..{tr['date'].max().date()} | "
          f"calib {ca['date'].min().date()}..{ca['date'].max().date()} | "
          f"test {te['date'].min().date()}..{te['date'].max().date()}")

    model = LGBMClassifier(n_estimators=200, learning_rate=0.03, num_leaves=8,
                           min_child_samples=30, subsample=0.8, subsample_freq=1,
                           colsample_bytree=0.8, reg_lambda=1.0, random_state=42, verbose=-1)
    model.fit(tr[feats], tr["y"])

    p_ca = model.predict_proba(ca[feats])
    p_te = model.predict_proba(te[feats])
    y_te = te["y"].values
    ret = te["ret_oc"].values * 100  # percent

    base_acc = float((p_te.argmax(1) == y_te).mean())
    maj_acc = max(y_te.mean(), 1 - y_te.mean())
    print(f"\nBaselines on test: model accuracy (trade every day) = {base_acc:.3f} | "
          f"always-majority = {maj_acc:.3f}")
    sig_all = np.where(p_te.argmax(1) == 1, 1, -1)
    g = sig_all * ret
    print(f"Trade-every-day: gross {g.mean()*100:.1f} bps/trade, "
          f"net {(g.mean()-ROUND_TRIP_COST_PCT)*100:.1f} bps/trade over {len(g)} trades\n")

    print(f"{'alpha':>5} {'target_cov':>10} {'coverage':>9} {'abstain%':>9} {'trades':>7} "
          f"{'acc_on_trades':>14} {'gross_bps':>10} {'net_bps':>8}")
    for a in ALPHAS:
        q = calibrate(p_ca, ca["y"].values, a)
        S = prediction_sets(p_te, q)
        cov = coverage(S, y_te)
        single = S.sum(1) == 1
        n_tr = int(single.sum())
        if n_tr:
            pred = S.argmax(1)[single]
            acc = float((pred == y_te[single]).mean())
            sig = np.where(pred == 1, 1, -1)
            gross = float((sig * ret[single]).mean())
            net = gross - ROUND_TRIP_COST_PCT
            print(f"{a:5.2f} {1-a:10.2f} {cov:9.3f} {100*(1-n_tr/len(te)):9.1f} {n_tr:7d} "
                  f"{acc:14.3f} {gross*100:10.1f} {net*100:8.1f}")
        else:
            print(f"{a:5.2f} {1-a:10.2f} {cov:9.3f} {100.0:9.1f} {0:7d} {'-':>14} {'-':>10} {'-':>8}")

    cal_scores = {k: np.sort(1 - p_ca[ca["y"].values == k, k]) for k in (0, 1)}
    joblib.dump({"model": model, "features": feats, "cal_scores": cal_scores,
                 "avg_abs_ret_pct": float(np.abs(tr["ret_oc"]).mean() * 100)},
                "data/models/technical.joblib")
    print("\nsaved data/models/technical.joblib")


if __name__ == "__main__":
    main()