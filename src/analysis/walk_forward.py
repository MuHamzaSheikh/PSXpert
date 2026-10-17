"""
PSXpert - Anti-Overfitting Walk-Forward Validation Engine
Enforces strict chronological data splitting (Training, Validation, Out-of-Sample Test)
and rolling walk-forward validation (WFV) to prevent lookahead bias and curve-fitting.
"""

from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import pandas as pd

from src.analysis.regime_hmm import MarketRegimeHMM
from src.analysis.genetic_algorithm import (
    GeneticAlgorithmOptimizer,
    FastStrategyBacktester,
    BASELINE_PARAMS
)


class WalkForwardEngine:
    """
    Orchestrates the 6-stage Quantitative Research Pipeline:
    1. Collect prices.
    2. Calculate technical indicators.
    3. Estimate market regimes with HMM.
    4. Optimize indicator parameters with Genetic Algorithm on Training set.
    5. Evaluate on unseen validation and out-of-sample test periods.
    6. Run rolling Walk-Forward Validation (WFV) to calculate Walk-Forward Efficiency (WFE).
    """

    def __init__(
        self,
        train_ratio: float = 0.60,
        val_ratio: float = 0.20,
        test_ratio: float = 0.20,
        hmm_states: int = 3,
        ga_population: int = 30,
        ga_generations: int = 20,
        random_state: int = 42
    ):
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.hmm_states = hmm_states
        self.ga_population = ga_population
        self.ga_generations = ga_generations
        self.random_state = random_state

    def split_data(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Splits data chronologically into:
        1. Training Set (60%)
        2. Validation Set (20%)
        3. Out-of-Sample Unseen Test Set (20%)
        """
        data = df.sort_values(by="trading_date").reset_index(drop=True)
        n = len(data)

        train_end = int(n * self.train_ratio)
        val_end = int(n * (self.train_ratio + self.val_ratio))

        train_df = data.iloc[:train_end].copy().reset_index(drop=True)
        val_df = data.iloc[train_end:val_end].copy().reset_index(drop=True)
        test_df = data.iloc[val_end:].copy().reset_index(drop=True)

        return train_df, val_df, test_df

    def run_pipeline(self, df: pd.DataFrame, symbol: str = "KSE100") -> Dict[str, Any]:
        """
        Executes the full anti-overfitting quantitative pipeline.
        """
        if len(df) < 100:
            raise ValueError(f"Insufficient history for {symbol} ({len(df)} rows; minimum 100 required)")

        train_df, val_df, test_df = self.split_data(df)

        # Stage 3: HMM Market Regime Fitting (STRICTLY ON TRAIN SET)
        hmm = MarketRegimeHMM(n_states=self.hmm_states, random_state=self.random_state)
        hmm.fit(train_df)

        # Predict regimes across each chronological partition
        train_regime_res = hmm.predict_regimes(train_df)
        val_regime_res = hmm.predict_regimes(val_df)
        test_regime_res = hmm.predict_regimes(test_df)
        full_regime_res = hmm.predict_regimes(df)

        train_regimes = [item["regime"] for item in train_regime_res.get("history_sample", [])]
        val_regimes = [item["regime"] for item in val_regime_res.get("history_sample", [])]
        test_regimes = [item["regime"] for item in test_regime_res.get("history_sample", [])]

        # Stage 4: Genetic Algorithm Optimization (STRICTLY ON TRAIN SET)
        ga = GeneticAlgorithmOptimizer(
            population_size=self.ga_population,
            generations=self.ga_generations,
            random_state=self.random_state
        )
        ga_results = ga.optimize(train_df, train_regimes=train_regimes)
        opt_params = ga_results["optimized_parameters"]

        # Stage 5 & 6: Evaluate on Unseen Validation and Out-of-Sample Test Sets
        val_opt_metrics = FastStrategyBacktester.run_backtest(val_df, opt_params, val_regimes)
        val_base_metrics = FastStrategyBacktester.run_backtest(val_df, BASELINE_PARAMS, val_regimes)

        test_opt_metrics = FastStrategyBacktester.run_backtest(test_df, opt_params, test_regimes)
        test_base_metrics = FastStrategyBacktester.run_backtest(test_df, BASELINE_PARAMS, test_regimes)

        # Full Period Evaluation for UI visualization
        full_opt_metrics = FastStrategyBacktester.run_backtest(
            df,
            opt_params,
            [item["regime"] for item in full_regime_res.get("history_sample", [])]
        )

        # Calculate Out-of-Sample Performance Lift
        sharpe_lift = round(float(test_opt_metrics["sharpe_ratio"] - test_base_metrics["sharpe_ratio"]), 3)
        return_lift = round(float(test_opt_metrics["total_return_pct"] - test_base_metrics["total_return_pct"]), 2)
        dd_reduction = round(float(test_base_metrics["max_drawdown_pct"] - test_opt_metrics["max_drawdown_pct"]), 2)

        # Stage 6b: Rolling Walk-Forward Validation (3 Folds)
        wfv_results = self.run_walk_forward_folds(df, n_folds=3)

        return {
            "symbol": symbol,
            "data_summary": {
                "total_sessions": len(df),
                "train_sessions": len(train_df),
                "val_sessions": len(val_df),
                "test_sessions": len(test_df),
                "train_period": f"{train_df['trading_date'].iloc[0]} to {train_df['trading_date'].iloc[-1]}",
                "val_period": f"{val_df['trading_date'].iloc[0]} to {val_df['trading_date'].iloc[-1]}",
                "test_period": f"{test_df['trading_date'].iloc[0]} to {test_df['trading_date'].iloc[-1]} (UNSEEN OUT-OF-SAMPLE)"
            },
            "hmm_regimes": full_regime_res,
            "ga_optimization": {
                "optimized_parameters": opt_params,
                "baseline_parameters": BASELINE_PARAMS,
                "fitness_history": ga_results["fitness_history"],
                "generations_completed": ga_results["generations_completed"]
            },
            "performance_comparison": {
                "in_sample_train": {
                    "optimized": ga_results["in_sample_optimized_metrics"],
                    "baseline": ga_results["in_sample_baseline_metrics"]
                },
                "validation": {
                    "optimized": val_opt_metrics,
                    "baseline": val_base_metrics
                },
                "out_of_sample_unseen": {
                    "optimized": test_opt_metrics,
                    "baseline": test_base_metrics
                },
                "full_history": full_opt_metrics,
                "out_of_sample_lift": {
                    "sharpe_lift": sharpe_lift,
                    "return_lift_pct": return_lift,
                    "drawdown_reduction_pct": dd_reduction,
                    "outperforms_baseline": bool(test_opt_metrics["sharpe_ratio"] > test_base_metrics["sharpe_ratio"])
                }
            },
            "walk_forward_validation": wfv_results
        }

    def run_walk_forward_folds(self, df: pd.DataFrame, n_folds: int = 3) -> Dict[str, Any]:
        """
        Executes chronological rolling Walk-Forward Validation across sequential folds.
        Computes the Walk-Forward Efficiency (WFE) ratio.
        """
        data = df.sort_values(by="trading_date").reset_index(drop=True)
        total_len = len(data)
        fold_step = total_len // (n_folds + 1)

        folds_report = []
        is_sharpes = []
        oos_sharpes = []
        is_returns = []
        oos_returns = []

        for fold in range(n_folds):
            # Expanding / rolling window
            train_end = fold_step * (fold + 1)
            test_end = min(train_end + fold_step, total_len)

            fold_train = data.iloc[:train_end].copy().reset_index(drop=True)
            fold_test = data.iloc[train_end:test_end].copy().reset_index(drop=True)

            if len(fold_train) < 50 or len(fold_test) < 20:
                continue

            # Fit HMM on Fold Train
            hmm = MarketRegimeHMM(n_states=3, random_state=self.random_state + fold)
            hmm.fit(fold_train)
            f_train_res = hmm.predict_regimes(fold_train)
            f_test_res = hmm.predict_regimes(fold_test)

            f_train_regimes = [i["regime"] for i in f_train_res.get("history_sample", [])]
            f_test_regimes = [i["regime"] for i in f_test_res.get("history_sample", [])]

            # Fast GA evolution on Fold Train
            ga = GeneticAlgorithmOptimizer(
                population_size=20,
                generations=12,
                random_state=self.random_state + fold
            )
            ga_res = ga.optimize(fold_train, f_train_regimes)
            best_p = ga_res["optimized_parameters"]

            # Evaluate on Fold Test (Out-of-Sample)
            is_m = ga_res["in_sample_optimized_metrics"]
            oos_m = FastStrategyBacktester.run_backtest(fold_test, best_p, f_test_regimes)
            oos_base_m = FastStrategyBacktester.run_backtest(fold_test, BASELINE_PARAMS, f_test_regimes)

            is_sharpes.append(is_m["sharpe_ratio"])
            oos_sharpes.append(oos_m["sharpe_ratio"])
            is_returns.append(is_m["annualized_return_pct"])
            oos_returns.append(oos_m["annualized_return_pct"])

            folds_report.append({
                "fold": fold + 1,
                "train_period": f"{fold_train['trading_date'].iloc[0]} to {fold_train['trading_date'].iloc[-1]}",
                "test_period": f"{fold_test['trading_date'].iloc[0]} to {fold_test['trading_date'].iloc[-1]}",
                "in_sample_sharpe": is_m["sharpe_ratio"],
                "out_of_sample_sharpe": oos_m["sharpe_ratio"],
                "out_of_sample_return_pct": oos_m["total_return_pct"],
                "baseline_oos_return_pct": oos_base_m["total_return_pct"],
                "outperforms_baseline": bool(oos_m["sharpe_ratio"] > oos_base_m["sharpe_ratio"])
            })

        # Calculate Walk-Forward Efficiency (WFE)
        avg_is_ret = np.mean(is_returns) if is_returns else 1.0
        avg_oos_ret = np.mean(oos_returns) if oos_returns else 0.0
        wfe = round(float(avg_oos_ret / (avg_is_ret + 1e-6)), 3)

        avg_oos_sharpe = np.mean(oos_sharpes) if oos_sharpes else 0.0
        overfitting_risk = "LOW (Robust Predictive Edge)" if (wfe >= 0.45 and avg_oos_sharpe > 0) else (
            "MODERATE" if avg_oos_sharpe > 0 else "ELEVATED (Regime Decay Observed)"
        )

        return {
            "folds": folds_report,
            "mean_in_sample_sharpe": round(float(np.mean(is_sharpes)), 3) if is_sharpes else 0.0,
            "mean_out_of_sample_sharpe": round(float(avg_oos_sharpe), 3),
            "walk_forward_efficiency_ratio": wfe,
            "overfitting_risk_assessment": overfitting_risk,
            "total_folds_evaluated": len(folds_report)
        }
