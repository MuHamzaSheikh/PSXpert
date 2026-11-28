"""
Causal Hidden Markov Model (HMM) Market Regime Filter.

Unlike hmmlearn's `predict_proba()` (forward-backward smoothed P(S_t | X_{1:T}))
and `predict()` (Viterbi global path), this module implements exact causal
forward filtering P(S_t | X_{1:t}) in log-space after fitting GaussianHMM
exclusively on the chronological Training split.
"""

from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from scipy.special import logsumexp
try:
    from hmmlearn.hmm import GaussianHMM
except ImportError:
    GaussianHMM = None


class CausalMarketRegimeHMM:
    """
    Strictly causal 3-state Gaussian HMM over authentic KSE-100 index close features.
    Avoids synthetic OHLC shadows (enrich_ohlc.py) and eliminates future smoothing.
    """

    def __init__(self, n_states: int = 3, random_state: int = 42):
        self.n_states = n_states
        self.random_state = random_state
        self.model = GaussianHMM(
            n_components=n_states,
            covariance_type="diag",
            min_covar=1e-4,
            n_iter=200,
            random_state=random_state,
        )
        self.state_map: Dict[int, str] = {}
        self.is_fitted = False

    @staticmethod
    def extract_causal_index_features(index_df: pd.DataFrame) -> Tuple[np.ndarray, pd.DataFrame]:
        """
        Builds stationary causal features strictly from KSE-100 close prices:
        1. log_return_1d: ln(C_t / C_{t-1})
        2. rolling_std_5d: trailing 5-session log-return volatility
        3. rolling_std_20d: trailing 20-session log-return volatility
        """
        df = index_df.copy()
        df["trading_date"] = pd.to_datetime(df["trading_date"]).dt.date
        df = df.sort_values("trading_date").drop_duplicates("trading_date").reset_index(drop=True)
        df["close"] = pd.to_numeric(df["close"], errors="coerce")

        df["log_ret_1d"] = np.log(df["close"] / df["close"].shift(1))
        df["rolling_std_5d"] = df["log_ret_1d"].rolling(window=5, min_periods=5).std()
        df["rolling_std_20d"] = df["log_ret_1d"].rolling(window=20, min_periods=20).std()

        valid = df.dropna(subset=["log_ret_1d", "rolling_std_5d", "rolling_std_20d"]).copy().reset_index(drop=True)
        features = valid[["log_ret_1d", "rolling_std_5d", "rolling_std_20d"]].values
        return features, valid

    def fit(self, train_index_df: pd.DataFrame) -> "CausalMarketRegimeHMM":
        """Fits GaussianHMM parameters solely on the Training split index observations."""
        features, _ = self.extract_causal_index_features(train_index_df)
        if len(features) < 60:
            raise ValueError(f"Insufficient training observations for HMM: {len(features)}")

        self.feat_mean_ = np.mean(features, axis=0)
        self.feat_std_ = np.maximum(np.std(features, axis=0), 1e-8)
        scaled_features = (features - self.feat_mean_) / self.feat_std_

        self.model.fit(scaled_features)
        self.is_fitted = True

        # Semantic state labeling strictly from Train emission means (column 0 is scaled return)
        ret_means = self.model.means_[:, 0] * self.feat_std_[0] + self.feat_mean_[0]
        vol_means = self.model.means_[:, 1] * self.feat_std_[1] + self.feat_mean_[1]
        sorted_idx = np.argsort(ret_means)
        bear_idx = int(sorted_idx[0])
        bull_idx = int(sorted_idx[-1])
        side_candidates = [int(i) for i in range(self.n_states) if i not in (bear_idx, bull_idx)]
        side_idx = side_candidates[0] if side_candidates else int(sorted_idx[1])

        self.state_map = {
            bull_idx: "BULLISH",
            bear_idx: "BEARISH",
            side_idx: "SIDEWAYS",
        }
        return self

    def filter_causal_probabilities(self, full_index_df: pd.DataFrame) -> pd.DataFrame:
        """
        Computes strictly causal filtered regime probabilities P(S_t | X_{1:t})
        via sequential log-space forward recursion:
            log alpha_0(j) = log pi_j + log b_j(x_0)
            log alpha_t(j) = logsumexp_i [log alpha_{t-1}(i) + log A_{i,j}] + log b_j(x_t)
            P(S_t = j | X_{1:t}) = exp(log alpha_t(j) - logsumexp_k log alpha_t(k))

        At every date t, zero information from t+1..T enters the calculation.
        """
        if not self.is_fitted:
            raise RuntimeError("CausalMarketRegimeHMM must be fitted on Train data before filtering.")

        raw_features, valid_df = self.extract_causal_index_features(full_index_df)
        features = (raw_features - self.feat_mean_) / self.feat_std_
        t_len = len(features)
        if t_len == 0:
            raise ValueError("No valid feature rows to filter.")

        # Emission log-likelihoods at each step t depend strictly on x_t only
        log_emiss = self.model._compute_log_likelihood(features)  # shape (T, K)

        eps = 1e-300
        log_startprob = np.log(np.clip(self.model.startprob_, eps, 1.0))
        log_transmat = np.log(np.clip(self.model.transmat_, eps, 1.0))

        filtered_probs = np.zeros((t_len, self.n_states), dtype=np.float64)

        # t = 0 initialization
        log_alpha = log_startprob + log_emiss[0]
        log_norm = logsumexp(log_alpha)
        log_alpha = log_alpha - log_norm
        filtered_probs[0] = np.exp(log_alpha)

        # Forward recursion t = 1 .. T-1
        for t in range(1, t_len):
            # alpha_{t|t-1}(j) = logsumexp_i (log_alpha_{t-1}(i) + log_A_{i,j})
            log_pred = logsumexp(log_alpha[:, None] + log_transmat, axis=0)
            log_alpha = log_pred + log_emiss[t]
            log_norm = logsumexp(log_alpha)
            log_alpha = log_alpha - log_norm
            filtered_probs[t] = np.exp(log_alpha)

        # Map back to semantic labels
        inv_map = {v: k for k, v in self.state_map.items()}
        bull_col = filtered_probs[:, inv_map["BULLISH"]]
        bear_col = filtered_probs[:, inv_map["BEARISH"]]
        side_col = filtered_probs[:, inv_map["SIDEWAYS"]]

        # Numeric regime code: 1=BULLISH, 0=SIDEWAYS, -1=BEARISH
        best_idx = np.argmax(filtered_probs, axis=1)
        regime_labels = [self.state_map[int(i)] for i in best_idx]
        code_map = {"BULLISH": 1, "SIDEWAYS": 0, "BEARISH": -1}
        regime_codes = [code_map[r] for r in regime_labels]

        # Regime uncertainty (Shannon entropy in nats)
        safe_p = np.clip(filtered_probs, 1e-12, 1.0)
        entropy = -np.sum(safe_p * np.log(safe_p), axis=1)

        # Consecutive duration in current causal filtered regime (causal run length)
        durations = np.ones(t_len, dtype=np.int32)
        for t in range(1, t_len):
            durations[t] = durations[t - 1] + 1 if regime_codes[t] == regime_codes[t - 1] else 1

        # Re-align to full_index_df calendar (preserving NaN during 20-day warmup)
        out = pd.DataFrame({
            "trading_date": valid_df["trading_date"],
            "hmm_mkt_prob_bullish": np.round(bull_col, 6),
            "hmm_mkt_prob_bearish": np.round(bear_col, 6),
            "hmm_mkt_prob_sideways": np.round(side_col, 6),
            "hmm_mkt_regime_id": regime_codes,
            "hmm_mkt_regime_label": regime_labels,
            "hmm_mkt_entropy": np.round(entropy, 6),
            "hmm_mkt_regime_duration": durations,
        })

        full_dates = (
            full_index_df[["trading_date"]]
            .assign(trading_date=lambda d: pd.to_datetime(d["trading_date"]).dt.date)
            .drop_duplicates("trading_date")
            .sort_values("trading_date")
        )
        return full_dates.merge(out, on="trading_date", how="left")

    def get_model_metadata(self) -> Dict[str, Any]:
        """Returns fitted Train-only parameters for documentation/audit."""
        if not self.is_fitted:
            return {}
        return {
            "n_states": self.n_states,
            "state_map": {int(k): v for k, v in self.state_map.items()},
            "startprob": [round(float(x), 6) for x in self.model.startprob_],
            "transmat": [[round(float(x), 6) for x in row] for row in self.model.transmat_],
            "means": [[round(float(x), 6) for x in row] for row in self.model.means_],
        }

