"""
PSXpert - Hidden Markov Model (HMM) Market Regime Engine
Estimates latent market regimes (Bullish, Bearish, Sideways/Consolidation)
from historical financial features (returns, volatility, volume).
Strictly separates training from testing to prevent lookahead bias.
"""

from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM


class MarketRegimeHMM:
    """
    Gaussian Hidden Markov Model for financial market regime classification.
    Identifies 3 latent economic regimes:
      1. BULLISH (High positive expected returns, moderate/low volatility)
      2. BEARISH (Negative expected returns, elevated volatility)
      3. SIDEWAYS (Near-zero expected returns, low/moderate volatility)
    """

    def __init__(self, n_states: int = 3, random_state: int = 42):
        self.n_states = n_states
        self.random_state = random_state
        self.model = GaussianHMM(
            n_components=n_states,
            covariance_type="diag",
            min_covar=1e-4,
            n_iter=150,
            random_state=random_state,
            algorithm="viterbi"
        )
        self.is_fitted = False
        self.state_map: Dict[int, str] = {}  # internal_state -> 'BULLISH'/'BEARISH'/'SIDEWAYS'
        self.state_stats: Dict[str, Dict[str, float]] = {}

    def extract_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, pd.DataFrame]:
        """
        Extracts stationary econometric features from OHLCV DataFrame:
        1. Log returns: ln(Close_t / Close_{t-1})
        2. Parkinson / Range Volatility: sqrt((ln(High / Low))^2 / (4 * ln(2)))
        3. Normalized 10-day rolling return volatility
        """
        data = df.copy()
        data = data.sort_values(by="trading_date").reset_index(drop=True)

        for col in ["open", "high", "low", "close", "volume"]:
            data[col] = pd.to_numeric(data[col], errors="coerce")

        data["log_return"] = np.log(data["close"] / data["close"].shift(1))
        
        # Parkinson Volatility (more efficient estimator than close-to-close std)
        hl_ratio = np.log(np.maximum(data["high"], 1e-4) / np.maximum(data["low"], 1e-4))
        data["parkinson_vol"] = np.sqrt((hl_ratio ** 2) / (4.0 * np.log(2.0)))

        # 10-day rolling return standard deviation
        data["rolling_std"] = data["log_return"].rolling(window=10).std()

        # Drop NaN warmup rows
        clean_data = data.dropna(subset=["log_return", "parkinson_vol", "rolling_std"]).copy()
        clean_data.reset_index(drop=True, inplace=True)

        features = clean_data[["log_return", "parkinson_vol", "rolling_std"]].values
        return features, clean_data

    def fit(self, train_df: pd.DataFrame) -> "MarketRegimeHMM":
        """
        Fits the Gaussian HMM exclusively on the training dataset.
        Zero lookahead bias.
        """
        features, clean_df = self.extract_features(train_df)
        if len(features) < 30:
            raise ValueError(f"Insufficient training data for HMM ({len(features)} rows; minimum 30 required)")

        self.model.fit(features)
        self.is_fitted = True

        # Identify states by mean return and volatility to assign semantic labels
        means = self.model.means_  # shape: (n_states, n_features)
        covars = self.model.covars_  # shape: (n_states, n_features, n_features)

        # Means: column 0 is log_return, column 1 is parkinson_vol
        return_means = means[:, 0]
        vol_means = means[:, 1]

        # Rank states: highest return -> BULLISH, lowest return -> BEARISH, middle -> SIDEWAYS
        sorted_indices = np.argsort(return_means)  # ascending: lowest first (Bearish)
        
        bear_state = sorted_indices[0]
        bull_state = sorted_indices[-1]
        sideways_states = [idx for idx in range(self.n_states) if idx not in (bear_state, bull_state)]
        sideways_state = sideways_states[0] if sideways_states else sorted_indices[1]

        self.state_map = {
            bull_state: "BULLISH",
            bear_state: "BEARISH",
            sideways_state: "SIDEWAYS"
        }

        # Calculate state characteristics (annualized)
        self.state_stats = {}
        for state_idx, label in self.state_map.items():
            daily_ret = float(return_means[state_idx])
            daily_vol = float(vol_means[state_idx])
            clipped_ret = np.clip(daily_ret * 252, -5.0, 5.0)
            annual_ret = (np.exp(clipped_ret) - 1.0) * 100.0
            annual_vol = daily_vol * np.sqrt(252) * 100.0

            # Expected duration in state: 1 / (1 - P(i -> i))
            trans_diag = float(self.model.transmat_[state_idx, state_idx])
            denom = max(1.0 - trans_diag, 0.02)
            avg_duration = min(1.0 / denom, 250.0)

            self.state_stats[label] = {
                "annualized_return_pct": round(float(annual_ret), 2),
                "annualized_volatility_pct": round(float(annual_vol), 2),
                "daily_mean_return": round(float(daily_ret * 100), 3),
                "daily_volatility": round(float(daily_vol * 100), 3),
                "transition_persistence": round(float(trans_diag), 4),
                "expected_duration_days": round(float(avg_duration), 1)
            }

        return self

    def predict_regimes(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Computes historical regime sequence and posterior probabilities.
        Can be run on train, test, or full dataset.
        """
        if not self.is_fitted:
            raise RuntimeError("HMM model must be fitted before predicting regimes.")

        features, clean_df = self.extract_features(df)
        if len(features) == 0:
            return {"error": "Empty features for prediction"}

        # Viterbi decoding for most likely state path
        hidden_states = self.model.predict(features)

        # Posterior state probabilities P(S_t = k | X)
        posteriors = self.model.predict_proba(features)

        regimes_history = []
        state_counts = {"BULLISH": 0, "BEARISH": 0, "SIDEWAYS": 0}

        for i in range(len(clean_df)):
            s_idx = hidden_states[i]
            regime_label = self.state_map.get(s_idx, "SIDEWAYS")
            state_counts[regime_label] += 1

            # Map probabilities to standardized labels
            prob_dict = {
                self.state_map[idx]: round(float(posteriors[i, idx]), 4)
                for idx in range(self.n_states)
            }

            regimes_history.append({
                "date": str(clean_df["trading_date"].iloc[i]),
                "close": float(clean_df["close"].iloc[i]),
                "regime": regime_label,
                "confidence": prob_dict.get(regime_label, 0.0),
                "prob_bullish": prob_dict.get("BULLISH", 0.0),
                "prob_bearish": prob_dict.get("BEARISH", 0.0),
                "prob_sideways": prob_dict.get("SIDEWAYS", 0.0)
            })

        # Latest/Current Regime
        latest_item = regimes_history[-1] if regimes_history else {}
        total_obs = max(len(regimes_history), 1)
        stationary_distribution = {
            k: round((v / total_obs) * 100.0, 1) for k, v in state_counts.items()
        }

        # Transition matrix with semantic labels
        trans_matrix = {}
        for from_idx, from_label in self.state_map.items():
            trans_matrix[from_label] = {}
            for to_idx, to_label in self.state_map.items():
                prob = float(self.model.transmat_[from_idx, to_idx])
                trans_matrix[from_label][to_label] = round(prob, 4)

        return {
            "current_regime": latest_item.get("regime", "UNKNOWN"),
            "current_confidence": latest_item.get("confidence", 0.0),
            "current_probabilities": {
                "BULLISH": latest_item.get("prob_bullish", 0.0),
                "BEARISH": latest_item.get("prob_bearish", 0.0),
                "SIDEWAYS": latest_item.get("prob_sideways", 0.0)
            },
            "stationary_distribution_pct": stationary_distribution,
            "transition_matrix": trans_matrix,
            "state_characteristics": self.state_stats,
            "history_sample": regimes_history[-180:],  # Last 180 sessions for UI
            "total_sessions_analyzed": len(regimes_history)
        }
