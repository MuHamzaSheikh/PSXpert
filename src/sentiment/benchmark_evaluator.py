"""
PSXpert - Pakistani Financial News Sentiment Benchmark Suite
Manually labelled, representative evaluation dataset of 50 Pakistani financial headlines and news excerpts.
Evaluates Lexicon Baseline vs. FinBERT with Precision, Recall, F1-score, and Confusion Matrix.
Analyzes local linguistic performance (circular debt, IMF tranches, gas tariffs, bourse rallies).
"""

from typing import Dict, List, Any, Tuple
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support

from src.sentiment.lexicon_baseline import LexiconFinancialAnalyzer
from src.sentiment.finbert_analyzer import FinBERTAnalyzer

# 50 Curated, Gold-Standard Manually Labelled Pakistani Financial News Samples
# Sourced from Dawn Business, Business Recorder, and official PSX disclosures.
GOLD_BENCHMARK_DATA = [
    # --- POSITIVE (18 Samples) ---
    {
        "id": 1,
        "text": "PSX soars 1,400 points as foreign funds buy blue-chip stocks amid economic stability hopes",
        "target_symbol": "KSE100",
        "ground_truth": "POSITIVE",
        "sector": "MACRO / PSX",
        "notes": "Bourse rally driven by foreign institutional inflows"
    },
    {
        "id": 2,
        "text": "Lucky Cement posts record annual net profit of Rs36.4 billion, declares Rs15 final dividend",
        "target_symbol": "LUCK",
        "ground_truth": "POSITIVE",
        "sector": "CEMENT",
        "notes": "Corporate earnings surge and cash dividend"
    },
    {
        "id": 3,
        "text": "OGDC and PPL strike major gas discovery at Bettani well with 42 MMCFD flow potential",
        "target_symbol": "OGDC",
        "ground_truth": "POSITIVE",
        "sector": "OIL & GAS EXPLORATION",
        "notes": "High commercial value hydrocarbon discovery"
    },
    {
        "id": 4,
        "text": "Meezan Bank reports 48% jump in quarterly earnings as Islamic financing spreads expand",
        "target_symbol": "MEBL",
        "ground_truth": "POSITIVE",
        "sector": "COMMERCIAL BANKS",
        "notes": "Banking net interest income expansion"
    },
    {
        "id": 5,
        "text": "State Bank cuts policy rate by 150 basis points to stimulate industrial borrowing and growth",
        "target_symbol": "KSE100",
        "ground_truth": "POSITIVE",
        "sector": "MACRO / SBP",
        "notes": "Monetary easing is positive for equities"
    },
    {
        "id": 6,
        "text": "IMF reaches staff-level agreement on $7 billion EFF loan review, unlocking crucial inflows",
        "target_symbol": "PSX",
        "ground_truth": "POSITIVE",
        "sector": "MACRO / IMF",
        "notes": "Bilateral balance of payments boost"
    },
    {
        "id": 7,
        "text": "Systems Limited secures $25m Middle East digital transformation contract, driving IT revenue",
        "target_symbol": "SYS",
        "ground_truth": "POSITIVE",
        "sector": "TECHNOLOGY",
        "notes": "Export software revenue growth"
    },
    {
        "id": 8,
        "text": "Mari Petroleum approves 800% bonus share issuance following substantial well production",
        "target_symbol": "MARI",
        "ground_truth": "POSITIVE",
        "sector": "OIL & GAS EXPLORATION",
        "notes": "Substantial corporate bonus issue"
    },
    {
        "id": 9,
        "text": "Fauji Fertilizer reports robust quarterly margin expansion supported by international urea price gains",
        "target_symbol": "FFC",
        "ground_truth": "POSITIVE",
        "sector": "FERTILIZER",
        "notes": "Fertilizer profitability improvement"
    },
    {
        "id": 10,
        "text": "Hub Power completes Thar energy project debt reprofiling, cutting finance cost by 35%",
        "target_symbol": "HUBC",
        "ground_truth": "POSITIVE",
        "sector": "POWER",
        "notes": "Debt restructuring reduces financial expenses"
    },
    {
        "id": 11,
        "text": "Indus Motor introduces new hybrid model as vehicle assembly operations run at full capacity",
        "target_symbol": "INDU",
        "ground_truth": "POSITIVE",
        "sector": "AUTOMOBILE",
        "notes": "Capacity utilization recovery and new model rollout"
    },
    {
        "id": 12,
        "text": "Remittances surge to historic high of $3.1 billion in March, easing external pressure on Rupee",
        "target_symbol": "KSE100",
        "ground_truth": "POSITIVE",
        "sector": "MACRO / FOREX",
        "notes": "Positive balance of payments signal"
    },
    {
        "id": 13,
        "text": "Pakistan Refinery signs formal upgrade agreement to produce Euro-V clean petroleum fuels",
        "target_symbol": "PRL",
        "ground_truth": "POSITIVE",
        "sector": "REFINERY",
        "notes": "Strategic Brownfield refinery modernization"
    },
    {
        "id": 14,
        "text": "United Bank Limited announces interim dividend of Rs11 per share alongside solid earnings",
        "target_symbol": "UBL",
        "ground_truth": "POSITIVE",
        "sector": "COMMERCIAL BANKS",
        "notes": "High yield dividend payout"
    },
    {
        "id": 15,
        "text": "Maple Leaf Cement commissions new solar power plant to reduce grid tariff dependency by 40%",
        "target_symbol": "MLCF",
        "ground_truth": "POSITIVE",
        "sector": "CEMENT",
        "notes": "Energy cost savings operational improvement"
    },
    {
        "id": 16,
        "text": "Government approves settlement package to clear pending circular debt payments to PSO",
        "target_symbol": "PSO",
        "ground_truth": "POSITIVE",
        "sector": "OIL & GAS MARKETING",
        "notes": "Liquidity injection for OMC receivables"
    },
    {
        "id": 17,
        "text": "Engro Polymer sees turnaround with quarterly net income rising on higher PVC margins",
        "target_symbol": "EPCL",
        "ground_truth": "POSITIVE",
        "sector": "CHEMICALS",
        "notes": "Cyclical turnaround"
    },
    {
        "id": 18,
        "text": "Pak Suzuki returns to quarterly profit after four consecutive quarters of foreign exchange losses",
        "target_symbol": "PSMC",
        "ground_truth": "POSITIVE",
        "sector": "AUTOMOBILE",
        "notes": "Loss-to-profit turnaround"
    },

    # --- NEGATIVE (18 Samples) ---
    {
        "id": 19,
        "text": "PSX plunges nearly 2,000 points amid intense selling pressure and political volatility",
        "target_symbol": "KSE100",
        "ground_truth": "NEGATIVE",
        "sector": "MACRO / PSX",
        "notes": "Sharp bourse sell-off"
    },
    {
        "id": 20,
        "text": "Energy sector circular debt tops Rs2.65 trillion as unpaid government subsidies mount",
        "target_symbol": "HUBC",
        "ground_truth": "NEGATIVE",
        "sector": "POWER",
        "notes": "Critical liquidity chokehold in Pakistani energy"
    },
    {
        "id": 21,
        "text": "Sui Northern faces severe gas curtailment forcing temporary shutdown of industrial fertilizer plants",
        "target_symbol": "SNGP",
        "ground_truth": "NEGATIVE",
        "sector": "FERTILIZER / GAS",
        "notes": "Supply disruption causing plant closure"
    },
    {
        "id": 22,
        "text": "NEPRA slashes return on equity for IPPs; Hub Power faces profit cut under revised PPA terms",
        "target_symbol": "HUBC",
        "ground_truth": "NEGATIVE",
        "sector": "POWER",
        "notes": "Regulatory tariff renegotiation hurting earnings"
    },
    {
        "id": 23,
        "text": "Cement dispatches drop 18% in February as high construction costs dampen local demand",
        "target_symbol": "DGKC",
        "ground_truth": "NEGATIVE",
        "sector": "CEMENT",
        "notes": "Volume contraction across sector"
    },
    {
        "id": 24,
        "text": "Rupee drops to fresh record low against dollar as foreign exchange reserves deplete",
        "target_symbol": "KSE100",
        "ground_truth": "NEGATIVE",
        "sector": "MACRO / FOREX",
        "notes": "Currency devaluation hurting import-dependent sectors"
    },
    {
        "id": 25,
        "text": "Indus Motor announces 15-day plant shutdown due to severe auto parts supply chain disruption",
        "target_symbol": "INDU",
        "ground_truth": "NEGATIVE",
        "sector": "AUTOMOBILE",
        "notes": "Operational halt due to import restrictions"
    },
    {
        "id": 26,
        "text": "Attock Refinery shuts crude distillation unit as furnace oil stockpiles overflow storage",
        "target_symbol": "ATRL",
        "ground_truth": "NEGATIVE",
        "sector": "REFINERY",
        "notes": "Refinery production curtailment"
    },
    {
        "id": 27,
        "text": "Fauji Fertilizer Bin Qasim net loss widens to Rs4.2 billion on exorbitant RLNG feedstock tariffs",
        "target_symbol": "FFBL",
        "ground_truth": "NEGATIVE",
        "sector": "FERTILIZER",
        "notes": "Widening corporate losses due to gas tariffs"
    },
    {
        "id": 28,
        "text": "Cnergyico PK defaults on crude import payment as banking credit lines dry up",
        "target_symbol": "CNERGY",
        "ground_truth": "NEGATIVE",
        "sector": "REFINERY",
        "notes": "Credit default and liquidity distress"
    },
    {
        "id": 29,
        "text": "Habib Bank profit drops 22% after booking heavy impairment provisions on foreign exposures",
        "target_symbol": "HBL",
        "ground_truth": "NEGATIVE",
        "sector": "COMMERCIAL BANKS",
        "notes": "Asset quality deterioration"
    },
    {
        "id": 30,
        "text": "Government imposes 10% super tax on banking sector earnings, wiping out dividend expectations",
        "target_symbol": "COMMERCIAL BANKS",
        "ground_truth": "NEGATIVE",
        "sector": "COMMERCIAL BANKS",
        "notes": "Fiscal drag on banking profit"
    },
    {
        "id": 31,
        "text": "National Bank penalised by regulator for compliance lapses; incurs Rs1.2 billion fine",
        "target_symbol": "NBP",
        "ground_truth": "NEGATIVE",
        "sector": "COMMERCIAL BANKS",
        "notes": "Regulatory fine and penalty"
    },
    {
        "id": 32,
        "text": "Engro Fertilizers faces operational bottleneck as Daharki plant trips due to gas line rupture",
        "target_symbol": "ENGRO",
        "ground_truth": "NEGATIVE",
        "sector": "FERTILIZER",
        "notes": "Unplanned plant trip"
    },
    {
        "id": 33,
        "text": "Auto sector sales plunge 53% year-on-year amid punitive interest rates and import curbs",
        "target_symbol": "HONDA",
        "ground_truth": "NEGATIVE",
        "sector": "AUTOMOBILE",
        "notes": "Catastrophic sales collapse"
    },
    {
        "id": 34,
        "text": "K-Electric faces tariff petition rejection from NEPRA over consumer billing dispute",
        "target_symbol": "KEL",
        "ground_truth": "NEGATIVE",
        "sector": "POWER",
        "notes": "Adverse regulatory ruling"
    },
    {
        "id": 35,
        "text": "Pak Suzuki shares drop 7% as board initiates voluntary delisting from Pakistan Stock Exchange",
        "target_symbol": "PSMC",
        "ground_truth": "NEGATIVE",
        "sector": "AUTOMOBILE",
        "notes": "Delisting discount pressure"
    },
    {
        "id": 36,
        "text": "WorldCall Telecom annual losses mount to Rs1.8 billion amid heavy debt servicing load",
        "target_symbol": "WTL",
        "ground_truth": "NEGATIVE",
        "sector": "TECHNOLOGY",
        "notes": "Unprofitable balance sheet distress"
    },

    # --- NEUTRAL / INFORMATIONAL (14 Samples) ---
    {
        "id": 37,
        "text": "Oil and Gas Development Company scheduled board meeting on October 24 to review quarterly accounts",
        "target_symbol": "OGDC",
        "ground_truth": "NEUTRAL",
        "sector": "OIL & GAS EXPLORATION",
        "notes": "Routine corporate announcement of board meeting"
    },
    {
        "id": 38,
        "text": "State Bank of Pakistan leaves benchmark policy rate unchanged at 22% in routine meeting",
        "target_symbol": "KSE100",
        "ground_truth": "NEUTRAL",
        "sector": "MACRO / SBP",
        "notes": "Status quo policy rate decision as expected"
    },
    {
        "id": 39,
        "text": "Bank Alfalah announces closure of share transfer books from April 12 to April 19 for AGM",
        "target_symbol": "BAFL",
        "ground_truth": "NEUTRAL",
        "sector": "COMMERCIAL BANKS",
        "notes": "Administrative book closure notice"
    },
    {
        "id": 40,
        "text": "Lucky Cement holds Annual General Meeting; elects 7 directors for three-year term",
        "target_symbol": "LUCK",
        "ground_truth": "NEUTRAL",
        "sector": "CEMENT",
        "notes": "Routine director elections at AGM"
    },
    {
        "id": 41,
        "text": "PSX notifies re-composition of KSE-30 index effective from October 15",
        "target_symbol": "PSX",
        "ground_truth": "NEUTRAL",
        "sector": "MACRO / PSX",
        "notes": "Semi-annual technical index rebalancing"
    },
    {
        "id": 42,
        "text": "Fauji Fertilizer transmits copies of annual audited financial statements to exchange portal",
        "target_symbol": "FFC",
        "ground_truth": "NEUTRAL",
        "sector": "FERTILIZER",
        "notes": "Regulatory disclosure filing"
    },
    {
        "id": 43,
        "text": "SBP holds auction of treasury bills; accepts bids worth Rs450 billion matching maturity target",
        "target_symbol": "COMMERCIAL BANKS",
        "ground_truth": "NEUTRAL",
        "sector": "MACRO / SBP",
        "notes": "Routine rollover T-bill auction"
    },
    {
        "id": 44,
        "text": "Hub Power informs bourse regarding appointment of new Chief Financial Officer",
        "target_symbol": "HUBC",
        "ground_truth": "NEUTRAL",
        "sector": "POWER",
        "notes": "Administrative executive appointment disclosure"
    },
    {
        "id": 45,
        "text": "Federal cabinet reviews energy policy framework with domestic gas sector stakeholders",
        "target_symbol": "OIL & GAS",
        "ground_truth": "NEUTRAL",
        "sector": "OIL & GAS",
        "notes": "Policy consultation meeting without immediate decisions"
    },
    {
        "id": 46,
        "text": "Pakistan Petroleum notifies change of registered office address in Karachi",
        "target_symbol": "PPL",
        "ground_truth": "NEUTRAL",
        "sector": "OIL & GAS EXPLORATION",
        "notes": "Purely administrative address notification"
    },
    {
        "id": 47,
        "text": "KSE-100 index trades range-bound in lackluster session, closing 12 points higher",
        "target_symbol": "KSE100",
        "ground_truth": "NEUTRAL",
        "sector": "MACRO / PSX",
        "notes": "Flattish, neutral market movement"
    },
    {
        "id": 48,
        "text": "Indus Motor announces scheduled plant maintenance closure from Saturday to Tuesday",
        "target_symbol": "INDU",
        "ground_truth": "NEUTRAL",
        "sector": "AUTOMOBILE",
        "notes": "Standard scheduled maintenance window"
    },
    {
        "id": 49,
        "text": "SECP issues guidelines for digital trading and algorithmic order execution for brokerage houses",
        "target_symbol": "PSX",
        "ground_truth": "NEUTRAL",
        "sector": "REGULATORY",
        "notes": "Regulatory procedural framework release"
    },
    {
        "id": 50,
        "text": "Pakistan Refinery issues statement clarifying recent social media speculations regarding ownership",
        "target_symbol": "PRL",
        "ground_truth": "NEUTRAL",
        "sector": "REFINERY",
        "notes": "Routine clarification without operational impact"
    }
]


class BenchmarkEvaluator:
    def __init__(self):
        print("Initializing Benchmark Models (Baseline Lexicon + FinBERT)...")
        self.baseline_model = LexiconFinancialAnalyzer()
        self.finbert_model = FinBERTAnalyzer()
        self.labels = ["POSITIVE", "NEGATIVE", "NEUTRAL"]

    def run_evaluation(self) -> Dict[str, Any]:
        """
        Runs both models on the 50-sample gold benchmark.
        Calculates:
        - Accuracy, Precision, Recall, F1-Score (per-class, macro, weighted)
        - Confusion Matrix (3x3)
        - Error analysis across local Pakistani financial terminology
        """
        y_true = [item["ground_truth"] for item in GOLD_BENCHMARK_DATA]
        texts = [item["text"] for item in GOLD_BENCHMARK_DATA]

        # 1. Evaluate Lexicon Baseline
        baseline_preds = []
        for t in texts:
            res = self.baseline_model.analyze(t)
            baseline_preds.append(res["sentiment_label"])

        # 2. Evaluate FinBERT Transformer
        finbert_preds = []
        for t in texts:
            res = self.finbert_model.analyze_text(t)
            finbert_preds.append(res["sentiment_label"])

        # Metrics calculation
        b_report = classification_report(y_true, baseline_preds, labels=self.labels, output_dict=True, zero_division=0)
        f_report = classification_report(y_true, finbert_preds, labels=self.labels, output_dict=True, zero_division=0)

        b_cm = confusion_matrix(y_true, baseline_preds, labels=self.labels)
        f_cm = confusion_matrix(y_true, finbert_preds, labels=self.labels)

        # Linguistic / Local Domain Error Analysis
        baseline_errors = []
        finbert_errors = []

        for idx, item in enumerate(GOLD_BENCHMARK_DATA):
            true_l = item["ground_truth"]
            b_l = baseline_preds[idx]
            f_l = finbert_preds[idx]

            if b_l != true_l:
                baseline_errors.append({
                    "id": item["id"],
                    "text": item["text"],
                    "true": true_l,
                    "pred": b_l,
                    "sector": item["sector"],
                    "notes": item["notes"]
                })

            if f_l != true_l:
                finbert_errors.append({
                    "id": item["id"],
                    "text": item["text"],
                    "true": true_l,
                    "pred": f_l,
                    "sector": item["sector"],
                    "notes": item["notes"]
                })

        return {
            "total_samples": len(GOLD_BENCHMARK_DATA),
            "class_distribution": {
                "POSITIVE": y_true.count("POSITIVE"),
                "NEGATIVE": y_true.count("NEGATIVE"),
                "NEUTRAL": y_true.count("NEUTRAL")
            },
            "baseline": {
                "report": b_report,
                "confusion_matrix": b_cm,
                "errors": baseline_errors,
                "macro_f1": b_report["macro avg"]["f1-score"],
                "weighted_f1": b_report["weighted avg"]["f1-score"],
                "accuracy": b_report["accuracy"]
            },
            "finbert": {
                "report": f_report,
                "confusion_matrix": f_cm,
                "errors": finbert_errors,
                "macro_f1": f_report["macro avg"]["f1-score"],
                "weighted_f1": f_report["weighted avg"]["f1-score"],
                "accuracy": f_report["accuracy"]
            }
        }
