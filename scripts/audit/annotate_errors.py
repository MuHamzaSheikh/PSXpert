"""Annotates top 50 regression errors with corporate action and price jump context."""

from __future__ import annotations

import pandas as pd
import numpy as np

def main():
    top50 = pd.read_csv("reports/model_evaluation/top50_regression_errors.csv")
    payouts = pd.read_csv("psx all data/4_corporate_payouts/kse100_corporate_payouts_2001_2026.csv")
    ann = pd.read_csv("psx all data/5_corporate_announcements/corporate_announcements_clean.csv")

    annotated_actions = []
    annotated_ann = []

    for idx, row in top50.iterrows():
        sym = row["symbol"]
        dt = pd.to_datetime(row["trading_date"])
        
        # Check payouts within 45 days
        sym_pay = payouts[payouts["symbol"] == sym].copy()
        sym_pay["pdt"] = pd.to_datetime(sym_pay["announcement_date"])
        near_pay = sym_pay[(sym_pay["pdt"] >= dt - pd.Timedelta(days=30)) & (sym_pay["pdt"] <= dt + pd.Timedelta(days=45))]
        actions = []
        if len(near_pay) > 0:
            for _, pr in near_pay.iterrows():
                actions.append(f"{pr['payout_type']}:{pr['announcement_date']}({pr['dividend_per_share_pkr']}PKR)")
        action_str = "; ".join(actions) if actions else "None recorded in payouts"
        annotated_actions.append(action_str)

        # Check DPS corporate announcements
        sym_ann = ann[ann["symbol"] == sym].copy()
        if "posting_date" in sym_ann.columns:
            sym_ann["adt"] = pd.to_datetime(sym_ann["posting_date"])
        elif "postingDate" in sym_ann.columns:
            sym_ann["adt"] = pd.to_datetime(sym_ann["postingDate"])
        near_ann = sym_ann[(sym_ann["adt"] >= dt - pd.Timedelta(days=15)) & (sym_ann["adt"] <= dt + pd.Timedelta(days=35))]
        ann_titles = []
        if len(near_ann) > 0:
            for _, ar in near_ann.head(3).iterrows():
                ann_titles.append(f"{str(ar.get('posting_date', ''))[:10]}: {str(ar.get('title', ''))[:40]}")
        ann_str = "; ".join(ann_titles) if ann_titles else "None in DPS announcements"
        annotated_ann.append(ann_str)

    top50["corporate_payout_evidence"] = annotated_actions
    top50["dps_announcement_evidence"] = annotated_ann
    top50.to_csv("reports/model_evaluation/top50_regression_errors_audited.csv", index=False)
    print("Saved reports/model_evaluation/top50_regression_errors_audited.csv")
    print(top50[["symbol", "trading_date", "close", "fwd_close_20d", "target_ret_20d", "pred_comb", "corporate_payout_evidence"]].head(20).to_string())

if __name__ == "__main__":
    main()
