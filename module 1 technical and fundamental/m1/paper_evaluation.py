"""Append-Only Forward Paper Evaluation Engine.

Provides an audit-grade paper-trading and horizon evaluation pipeline:
1. Frozen Release Contract Enforcement:
   - Cryptographic SHA-256 verification of models, schema, universe, and evaluation rules.
   - Immutable configuration persistence; resumes reject parameter mutation.
   - Point-in-time publication timestamp validation and feature eligibility gating.
2. Training Target Alignment:
   - Fundamental Ranking: Evaluates excess return against KSE-100 benchmark from session t
     adjusted close to session t+126 adjusted close over a strictly contiguous valid window.
   - Executable Portfolio Return: Separately tracked metric (T+1 Open entry to T+10/126 Close exit).
   - Technical Ground Truth Target:
     net_stock_return_pct = 100 * (close[t+10] / open[t+1] - 1) - cost_pct
     label = int(net_stock_return_pct > entry_margin_pct)
     Does NOT subtract benchmark return when constructing this label.
     Benchmark-relative return is kept as a separately named diagnostic metric.
     Requires strictly valid 11-session contiguous price window (sessions t through t+10).
3. Transactional Crash-Safety & Idempotency:
   - Every record carries an explicit committed processing_session and transaction_id.
   - Creation, execution, signal, and maturity sessions are recorded as separate fields.
   - Successful session t commit preserves intended orders scheduled for t+1 across restart.
   - Rollback removes only records from uncommitted transactions (processing_session > committed_session),
     including matured outcomes whose signal sessions were earlier.
   - Handles crash/failure during the very first session too.
4. Market-Session Continuity:
   - Rejects skipped sessions; requires contiguous market-session stepping.
   - Persistent queue for unresolved matured outcomes (e.g. trading halts/suspensions).
5. Documented Risk Controls:
   - Declared 25.0% portfolio drawdown circuit breaker with persistent halt and explicit resume rules.
   - Score-only baselines (Value Composite and Momentum) explicitly designated.
6. Prospective vs Replay Isolation:
   - Distinct directory isolation, explicit evaluation mode, wall-clock timestamps, and data cutoffs.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from .features import FUNDAMENTAL, TECHNICAL
from .decision_pipeline import feature_matrix


PRIMARY_KEYS: dict[str, list[str]] = {
    "signals_fundamental.csv": ["processing_session", "symbol"],
    "signals_technical.csv": ["processing_session", "symbol"],
    "intended_orders.csv": ["order_id"],
    "order_ledger.csv": ["order_id", "timing"],
    "rejected_orders.csv": ["processing_session", "order_id", "reason"],
    "portfolio_daily_state.csv": ["processing_session", "policy"],
    "completed_trades.csv": ["position_id", "exit_session"],
    "matured_technical_outcomes.csv": ["model_version", "signal_session", "symbol", "outcome_type"],
    "matured_fundamental_outcomes.csv": ["model_version", "signal_session", "symbol", "outcome_type"],
}


@dataclass
class PaperPosition:
    position_id: int
    policy: str
    symbol: str
    entry_session: int
    scheduled_exit_session: int
    entry_price: float
    shares: float
    cost_basis: float  # gross spend + buy fee
    last_known_close: float
    stale_days: int = 0
    is_delayed: bool = False


class PaperEvaluationEngine:
    def __init__(
        self,
        eval_dir: Path,
        release_dir: Path = Path("artifacts/frozen_research_release"),
        initial_capital: float = 10_000_000.0,
        cost_rate: float = 0.005,  # 0.25% buy, 0.25% sell = 0.50% round-trip
        max_position_weight: float = 0.10,
        holding_period: int = 10,
        decision_threshold: float = 0.50,
        top_fraction: float = 0.20,
        max_filing_age_days: int = 550,
        max_drawdown_limit_pct: float = 25.0,
        evaluation_mode: str = "HISTORICAL_REPLAY",
        model_version: str = "v1.0.0-frozen",
    ):
        self.eval_dir = Path(eval_dir)
        self.eval_dir.mkdir(parents=True, exist_ok=True)
        self.release_dir = Path(release_dir)
        if not self.release_dir.exists():
            mod_rel = Path(__file__).resolve().parent.parent / release_dir
            if mod_rel.exists():
                self.release_dir = mod_rel
        self.initial_capital = float(initial_capital)
        self.cost_rate = float(cost_rate)
        self.max_position_weight = float(max_position_weight)
        self.holding_period = int(holding_period)
        self.decision_threshold = float(decision_threshold)
        self.top_fraction = float(top_fraction)
        self.max_filing_age_days = int(max_filing_age_days)
        self.max_drawdown_limit_pct = float(max_drawdown_limit_pct)
        self.evaluation_mode = evaluation_mode
        self.model_version = str(model_version)

        # Enforce directory isolation between replay and prospective
        self._enforce_directory_safety()

        # Enforce frozen release integrity contract
        self._verify_frozen_release()

        # Load frozen models
        models_dir = self.release_dir / "models"
        self.ranker = joblib.load(models_dir / "fold_3_fundamental_xgbranker.joblib")
        self.classifier = joblib.load(models_dir / "fold_3_technical_xgboost.joblib")

        # Initialize or load state with crash recovery
        self.state_file = self.eval_dir / "engine_state.json"
        self._init_or_load_state()

    def _enforce_directory_safety(self):
        """Prevent historical replay from writing into prospective paper directory."""
        eval_resolved = self.eval_dir.resolve()
        prospective_path = Path("artifacts/paper_eval").resolve()
        mod_prospective = (Path(__file__).resolve().parent.parent / "artifacts" / "paper_eval").resolve()
        if self.evaluation_mode == "HISTORICAL_REPLAY" and eval_resolved in (prospective_path, mod_prospective):
            raise ValueError(
                "Directory safety violation: Historical replay cannot write to prospective "
                "evaluation directory 'artifacts/paper_eval'. Specify an isolated replay directory "
                "(e.g., 'artifacts/paper_eval_replay_test')."
            )

    def _verify_frozen_release(self):
        """Verify SHA-256 checksums of all release files against release_manifest.json."""
        manifest_file = self.release_dir / "release_manifest.json"
        if not manifest_file.exists():
            raise FileNotFoundError(f"Missing release manifest at {manifest_file}")

        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        release_files = manifest.get("release_files", {})

        for rel_path, expected_hash in release_files.items():
            full_path = self.release_dir / rel_path
            if not full_path.exists():
                raise FileNotFoundError(f"Frozen release file missing: {full_path}")
            actual_hash = hashlib.sha256(full_path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                raise RuntimeError(
                    f"Frozen release contract violation: SHA-256 mismatch for {rel_path}. "
                    f"Expected {expected_hash}, found {actual_hash}."
                )

    def _active_config_dict(self) -> dict[str, Any]:
        return {
            "initial_capital": self.initial_capital,
            "cost_rate": self.cost_rate,
            "max_position_weight": self.max_position_weight,
            "holding_period": self.holding_period,
            "decision_threshold": self.decision_threshold,
            "top_fraction": self.top_fraction,
            "max_filing_age_days": self.max_filing_age_days,
            "max_drawdown_limit_pct": self.max_drawdown_limit_pct,
            "evaluation_mode": self.evaluation_mode,
            "model_version": self.model_version,
        }

    def _init_or_load_state(self):
        if self.state_file.exists():
            state = json.loads(self.state_file.read_text(encoding="utf-8"))

            # Configuration immutability check on resume
            saved_config = state.get("config", {})
            for key, val in self._active_config_dict().items():
                if key in saved_config and saved_config[key] != val:
                    raise ValueError(
                        f"Configuration mutation on resume prohibited: parameter '{key}' was "
                        f"{saved_config[key]} when initialized, but engine initialized with {val}."
                    )

            self.last_processed_session = state["last_processed_session"]
            self.cash = state["cash"]
            self.peak_equity = state.get("peak_equity", {
                "Policy_A": float(self.initial_capital),
                "Policy_B": float(self.initial_capital),
            })
            self.circuit_breaker = state.get("circuit_breaker", {
                "Policy_A": {"active": False, "triggered_session": None, "reason": None},
                "Policy_B": {"active": False, "triggered_session": None, "reason": None},
            })
            self.next_order_id = state["next_order_id"]
            self.next_position_id = state["next_position_id"]
            self.positions = {
                "Policy_A": [PaperPosition(**p) for p in state["positions"].get("Policy_A", [])],
                "Policy_B": [PaperPosition(**p) for p in state["positions"].get("Policy_B", [])],
            }
            self.unresolved_matured_outcomes = state.get("unresolved_matured_outcomes", [])

            # Run transactional crash recovery check
            self._recover_uncommitted_logs_if_needed()
        else:
            self.last_processed_session = None
            self.cash = {
                "Policy_A": float(self.initial_capital),
                "Policy_B": float(self.initial_capital),
            }
            self.peak_equity = {
                "Policy_A": float(self.initial_capital),
                "Policy_B": float(self.initial_capital),
            }
            self.circuit_breaker = {
                "Policy_A": {"active": False, "triggered_session": None, "reason": None},
                "Policy_B": {"active": False, "triggered_session": None, "reason": None},
            }
            self.next_order_id = 1
            self.next_position_id = 1
            self.positions = {
                "Policy_A": [],
                "Policy_B": [],
            }
            self.unresolved_matured_outcomes = []
            # Check for crash during uncommitted first session
            self._recover_uncommitted_logs_if_needed()
            self._save_state()

    def _recover_uncommitted_logs_if_needed(self):
        """Transactional crash recovery using explicit processing_session identity."""
        committed_session = self.last_processed_session

        for filename in PRIMARY_KEYS.keys():
            csv_path = self.eval_dir / filename
            if not csv_path.exists():
                continue
            df = pd.read_csv(csv_path)
            if df.empty:
                continue

            if committed_session is None:
                # Failure during the very first session! Roll back everything cleanly.
                csv_path.unlink()
            elif "processing_session" in df.columns:
                # Roll back only records belonging to an uncommitted transaction
                valid_df = df[df["processing_session"] <= committed_session].copy()
                if len(valid_df) == 0:
                    csv_path.unlink()
                elif len(valid_df) < len(df):
                    tmp_path = self.eval_dir / f"{filename}.tmp"
                    valid_df.to_csv(tmp_path, index=False)
                    os.replace(tmp_path, csv_path)

    def _save_state(self):
        """Atomic state persistence via temporary file replace."""
        state = {
            "config": self._active_config_dict(),
            "last_processed_session": self.last_processed_session,
            "cash": self.cash,
            "peak_equity": self.peak_equity,
            "circuit_breaker": self.circuit_breaker,
            "next_order_id": self.next_order_id,
            "next_position_id": self.next_position_id,
            "positions": {
                pol: [asdict(p) for p in pos_list]
                for pol, pos_list in self.positions.items()
            },
            "unresolved_matured_outcomes": self.unresolved_matured_outcomes,
            "baselines": {
                "value_composite": "SCORE_ONLY_RANKING_BASELINE",
                "momentum": "SCORE_ONLY_RANKING_BASELINE",
            },
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        tmp_file = self.eval_dir / "engine_state.json.tmp"
        tmp_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(tmp_file, self.state_file)

    def _append_csv(self, filename: str, df: pd.DataFrame):
        """Append records with composite primary key deduplication and atomic write safety."""
        if df.empty:
            return

        path = self.eval_dir / filename
        pk_cols = PRIMARY_KEYS.get(filename, [])

        if path.exists() and pk_cols:
            existing_df = pd.read_csv(path)
            effective_pk = [c for c in pk_cols if c in df.columns and c in existing_df.columns]
            if effective_pk and not existing_df.empty:
                # Filter out records whose composite primary key is already logged
                existing_keys = set(tuple(row) for row in existing_df[effective_pk].to_numpy())
                mask = [tuple(row) not in existing_keys for row in df[effective_pk].to_numpy()]
                df = df[mask]

        if df.empty:
            return

        write_header = not path.exists()
        df.to_csv(path, mode="a", header=write_header, index=False)

    def resume_after_circuit_breaker(self, policy: str, audit_rationale: str):
        """Explicit administrative override to clear circuit breaker halt."""
        if policy not in self.circuit_breaker:
            raise ValueError(f"Unknown policy: {policy}")
        if len(audit_rationale.strip()) < 10:
            raise ValueError("Formal audit rationale (at least 10 characters) is required to clear circuit breaker.")

        self.circuit_breaker[policy] = {
            "active": False,
            "triggered_session": None,
            "reason": None,
            "cleared_at_utc": datetime.now(timezone.utc).isoformat(),
            "audit_rationale": audit_rationale,
        }
        self._save_state()

    def process_session(
        self,
        session: int,
        prices_df: pd.DataFrame,
        panel_df: pd.DataFrame,
        benchmark_df: pd.DataFrame,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Execute one complete market session in strictly contiguous, append-only order."""
        # 1. Enforce Continuity and Append-Only Invariants
        if self.last_processed_session is not None:
            if session <= self.last_processed_session:
                raise ValueError(
                    f"Append-only violation: Session {session} already processed (last was {self.last_processed_session}). "
                    "Re-evaluating or overwriting past sessions is strictly prohibited."
                )
            if session > self.last_processed_session + 1:
                raise ValueError(
                    f"Market-session continuity violation: Session gap detected. Last was {self.last_processed_session}, "
                    f"received {session}. Expected {self.last_processed_session + 1}. Skipping sessions is prohibited."
                )

        wall_clock_ts = datetime.now(timezone.utc).isoformat()
        sig_ts = timestamp or wall_clock_ts
        is_prospective = (self.evaluation_mode == "PROSPECTIVE_PAPER")
        tx_id = f"tx_s{session}"

        records_summary = {
            "session": session,
            "timestamp": sig_ts,
            "evaluation_mode": self.evaluation_mode,
            "transaction_id": tx_id,
        }

        # Index current prices and benchmark
        price_records = prices_df[prices_df["session"] == session].set_index("symbol").to_dict("index")
        bench_row = benchmark_df[benchmark_df["session"] == session]
        bench_close = float(bench_row.iloc[0].get("adjusted_close", bench_row.iloc[0].get("benchmark_close", 1.0))) if not bench_row.empty else 1.0

        # -------------------------------------------------------------
        # 1. MORNING (SESSION OPEN): EXECUTE INTENDED ORDERS
        # -------------------------------------------------------------
        pending_orders_file = self.eval_dir / "intended_orders.csv"
        fills = []
        rejections = []

        if pending_orders_file.exists():
            df_intended = pd.read_csv(pending_orders_file)

            # Execution target is session
            exec_col = "execution_session" if "execution_session" in df_intended.columns else "session"
            open_orders = df_intended[
                (df_intended[exec_col] == session) &
                (df_intended["timing"] == "OPEN") &
                (df_intended["status"] == "PENDING")
            ].copy()

            # Identify order IDs that have already executed to prevent double execution
            executed_oids = set()
            ledger_file = self.eval_dir / "order_ledger.csv"
            if ledger_file.exists():
                df_led = pd.read_csv(ledger_file)
                if not df_led.empty and "order_id" in df_led.columns:
                    executed_oids.update(df_led["order_id"].dropna().astype(int))

            rej_file = self.eval_dir / "rejected_orders.csv"
            if rej_file.exists():
                df_rej = pd.read_csv(rej_file)
                if not df_rej.empty and "order_id" in df_rej.columns:
                    executed_oids.update(df_rej["order_id"].dropna().astype(int))

            for _, o in open_orders.iterrows():
                oid = int(o["order_id"])
                if oid in executed_oids:
                    continue  # already executed

                pol = o["policy"]
                sym = o["symbol"]
                s_sig = int(o.get("signal_session", session - 1))
                s_creat = int(o.get("creation_session", s_sig))

                # Check Circuit Breaker Halt
                if self.circuit_breaker[pol]["active"]:
                    rejections.append({
                        "transaction_id": tx_id,
                        "processing_session": session,
                        "execution_session": session,
                        "session": session,
                        "evaluation_mode": self.evaluation_mode,
                        "is_prospective": is_prospective,
                        "wall_clock_timestamp_utc": wall_clock_ts,
                        "source_data_cutoff_utc": sig_ts,
                        "timestamp": sig_ts,
                        "policy": pol,
                        "symbol": sym,
                        "order_id": oid,
                        "reason": "CIRCUIT_BREAKER_HALT",
                    })
                    continue

                p_bar = price_records.get(sym)
                if not p_bar:
                    rejections.append({
                        "transaction_id": tx_id,
                        "processing_session": session,
                        "execution_session": session,
                        "session": session,
                        "evaluation_mode": self.evaluation_mode,
                        "is_prospective": is_prospective,
                        "wall_clock_timestamp_utc": wall_clock_ts,
                        "source_data_cutoff_utc": sig_ts,
                        "timestamp": sig_ts,
                        "policy": pol,
                        "symbol": sym,
                        "order_id": oid,
                        "reason": "MISSING_MARKET_BAR",
                    })
                    continue

                open_price = float(p_bar.get("open", p_bar.get("adjusted_open", 0.0)))
                volume = float(p_bar.get("volume", 0.0))
                p_valid = bool(p_bar.get("price_valid", True))

                if not p_valid or not np.isfinite(open_price) or open_price <= 0:
                    rejections.append({
                        "transaction_id": tx_id,
                        "processing_session": session,
                        "execution_session": session,
                        "session": session,
                        "evaluation_mode": self.evaluation_mode,
                        "is_prospective": is_prospective,
                        "wall_clock_timestamp_utc": wall_clock_ts,
                        "source_data_cutoff_utc": sig_ts,
                        "timestamp": sig_ts,
                        "policy": pol,
                        "symbol": sym,
                        "order_id": oid,
                        "reason": "INVALID_PRICE_QUOTE",
                    })
                    continue

                if not np.isfinite(volume) or volume <= 0:
                    rejections.append({
                        "transaction_id": tx_id,
                        "processing_session": session,
                        "execution_session": session,
                        "session": session,
                        "evaluation_mode": self.evaluation_mode,
                        "is_prospective": is_prospective,
                        "wall_clock_timestamp_utc": wall_clock_ts,
                        "source_data_cutoff_utc": sig_ts,
                        "timestamp": sig_ts,
                        "policy": pol,
                        "symbol": sym,
                        "order_id": oid,
                        "reason": "ZERO_VOLUME_HALT",
                    })
                    continue

                # Check cash bounds (funded exclusively from C_{s-1})
                current_cash = self.cash[pol]
                max_pos_budget = float(o["intended_spend"])
                buy_fee_rate = self.cost_rate / 2.0  # 0.25% buy fee
                spend = min(current_cash / (1.0 + buy_fee_rate), max_pos_budget)

                if spend < (open_price * 1.0):
                    rejections.append({
                        "transaction_id": tx_id,
                        "processing_session": session,
                        "execution_session": session,
                        "session": session,
                        "evaluation_mode": self.evaluation_mode,
                        "is_prospective": is_prospective,
                        "wall_clock_timestamp_utc": wall_clock_ts,
                        "source_data_cutoff_utc": sig_ts,
                        "timestamp": sig_ts,
                        "policy": pol,
                        "symbol": sym,
                        "order_id": oid,
                        "reason": "INSUFFICIENT_CASH",
                    })
                    continue

                shares = np.floor(spend / open_price)
                if shares <= 0:
                    rejections.append({
                        "transaction_id": tx_id,
                        "processing_session": session,
                        "execution_session": session,
                        "session": session,
                        "evaluation_mode": self.evaluation_mode,
                        "is_prospective": is_prospective,
                        "wall_clock_timestamp_utc": wall_clock_ts,
                        "source_data_cutoff_utc": sig_ts,
                        "timestamp": sig_ts,
                        "policy": pol,
                        "symbol": sym,
                        "order_id": oid,
                        "reason": "INSUFFICIENT_FUNDS_FOR_SINGLE_SHARE",
                    })
                    continue

                gross_spend = shares * open_price
                fee = gross_spend * buy_fee_rate
                total_cash_impact = gross_spend + fee
                self.cash[pol] -= total_cash_impact

                pos_id = self.next_position_id
                self.next_position_id += 1

                pos = PaperPosition(
                    position_id=pos_id,
                    policy=pol,
                    symbol=sym,
                    entry_session=session,
                    scheduled_exit_session=session + self.holding_period - 1,
                    entry_price=open_price,
                    shares=shares,
                    cost_basis=total_cash_impact,
                    last_known_close=open_price,
                )
                self.positions[pol].append(pos)

                fills.append({
                    "transaction_id": tx_id,
                    "processing_session": session,
                    "execution_session": session,
                    "session": session,
                    "evaluation_mode": self.evaluation_mode,
                    "is_prospective": is_prospective,
                    "wall_clock_timestamp_utc": wall_clock_ts,
                    "source_data_cutoff_utc": sig_ts,
                    "timestamp": sig_ts,
                    "timing": "OPEN",
                    "order_id": oid,
                    "position_id": pos_id,
                    "policy": pol,
                    "symbol": sym,
                    "side": "BUY",
                    "shares": shares,
                    "price": open_price,
                    "gross_amount": gross_spend,
                    "fee": fee,
                    "net_cash_impact": -total_cash_impact,
                    "cash_balance_after": self.cash[pol],
                    "reason": "SIGNAL_ENTRY",
                })

        # -------------------------------------------------------------
        # 2. AFTERNOON (SESSION CLOSE): EXECUTE SCHEDULED EXITS
        # -------------------------------------------------------------
        completed_trades = []
        for pol in ["Policy_A", "Policy_B"]:
            remaining_pos = []
            for pos in self.positions[pol]:
                if session >= pos.scheduled_exit_session:
                    p_bar = price_records.get(pos.symbol)
                    close_price = float(p_bar.get("close", p_bar.get("adjusted_close", 0.0))) if p_bar else 0.0
                    vol = float(p_bar.get("volume", 0.0)) if p_bar else 0.0
                    p_valid = bool(p_bar.get("price_valid", True)) if p_bar else False

                    if p_bar and p_valid and np.isfinite(close_price) and close_price > 0 and np.isfinite(vol) and vol > 0:
                        gross_proceeds = pos.shares * close_price
                        sell_fee = gross_proceeds * (self.cost_rate / 2.0)
                        net_proceeds = gross_proceeds - sell_fee
                        self.cash[pol] += net_proceeds

                        order_id = self.next_order_id
                        self.next_order_id += 1

                        fills.append({
                            "transaction_id": tx_id,
                            "processing_session": session,
                            "execution_session": session,
                            "session": session,
                            "evaluation_mode": self.evaluation_mode,
                            "is_prospective": is_prospective,
                            "wall_clock_timestamp_utc": wall_clock_ts,
                            "source_data_cutoff_utc": sig_ts,
                            "timestamp": sig_ts,
                            "timing": "CLOSE",
                            "order_id": order_id,
                            "position_id": pos.position_id,
                            "policy": pol,
                            "symbol": pos.symbol,
                            "side": "SELL",
                            "shares": pos.shares,
                            "price": close_price,
                            "gross_amount": gross_proceeds,
                            "fee": sell_fee,
                            "net_cash_impact": net_proceeds,
                            "cash_balance_after": self.cash[pol],
                            "reason": "SUSPENSION_DELAYED_EXIT" if pos.is_delayed else "SCHEDULED_EXIT",
                        })

                        pnl = net_proceeds - pos.cost_basis
                        ret_pct = 100.0 * (net_proceeds / pos.cost_basis - 1.0)
                        completed_trades.append({
                            "transaction_id": tx_id,
                            "processing_session": session,
                            "creation_session": pos.entry_session,
                            "execution_session": session,
                            "entry_session": pos.entry_session,
                            "exit_session": session,
                            "scheduled_exit_session": pos.scheduled_exit_session,
                            "is_delayed_exit": bool(pos.is_delayed),
                            "delayed_sessions_count": max(0, session - pos.scheduled_exit_session),
                            "session": session,
                            "evaluation_mode": self.evaluation_mode,
                            "is_prospective": is_prospective,
                            "wall_clock_timestamp_utc": wall_clock_ts,
                            "timestamp": sig_ts,
                            "position_id": pos.position_id,
                            "policy": pol,
                            "symbol": pos.symbol,
                            "entry_price": pos.entry_price,
                            "exit_price": close_price,
                            "shares": pos.shares,
                            "cost_basis": pos.cost_basis,
                            "net_proceeds": net_proceeds,
                            "net_pnl_pkr": pnl,
                            "executable_net_return_pct": ret_pct,
                        })
                    else:
                        # Delayed Exit Policy
                        pos.is_delayed = True
                        pos.stale_days += 1
                        remaining_pos.append(pos)
                else:
                    remaining_pos.append(pos)
            self.positions[pol] = remaining_pos

        # -------------------------------------------------------------
        # 3. MARK-TO-MARKET BALANCE SHEET & CIRCUIT BREAKER CHECK
        # -------------------------------------------------------------
        daily_state_rows = []
        for pol in ["Policy_A", "Policy_B"]:
            holdings_val = 0.0
            stale_count = 0
            for pos in self.positions[pol]:
                p_bar = price_records.get(pos.symbol)
                c_price = float(p_bar.get("close", p_bar.get("adjusted_close", 0.0))) if p_bar else 0.0
                if p_bar and np.isfinite(c_price) and c_price > 0:
                    pos.last_known_close = c_price
                    pos.stale_days = 0
                else:
                    pos.stale_days += 1
                    stale_count += 1
                holdings_val += pos.shares * pos.last_known_close

            tot_eq = self.cash[pol] + holdings_val
            exp_pct = 100.0 * (holdings_val / tot_eq) if tot_eq > 0 else 0.0

            # Update Peak Equity & Check Drawdown Limit (25%)
            self.peak_equity[pol] = max(self.peak_equity[pol], tot_eq)
            current_drawdown_pct = 100.0 * (self.peak_equity[pol] - tot_eq) / self.peak_equity[pol] if self.peak_equity[pol] > 0 else 0.0

            if current_drawdown_pct >= self.max_drawdown_limit_pct and not self.circuit_breaker[pol]["active"]:
                self.circuit_breaker[pol] = {
                    "active": True,
                    "triggered_session": session,
                    "reason": f"Portfolio drawdown {current_drawdown_pct:.2f}% breached declared limit of {self.max_drawdown_limit_pct:.1f}%",
                    "triggered_at_utc": wall_clock_ts,
                }

            daily_state_rows.append({
                "transaction_id": tx_id,
                "processing_session": session,
                "session": session,
                "evaluation_mode": self.evaluation_mode,
                "is_prospective": is_prospective,
                "wall_clock_timestamp_utc": wall_clock_ts,
                "timestamp": sig_ts,
                "policy": pol,
                "cash": self.cash[pol],
                "holdings_value": holdings_val,
                "total_equity": tot_eq,
                "peak_equity": self.peak_equity[pol],
                "drawdown_pct": current_drawdown_pct,
                "circuit_breaker_active": self.circuit_breaker[pol]["active"],
                "exposure_pct": exp_pct,
                "active_positions_count": len(self.positions[pol]),
                "stale_valuations_count": stale_count,
            })

        # -------------------------------------------------------------
        # 4. EVENING (SESSION CLOSE): VALIDATE PUBLICATION TIMESTAMPS & GENERATE SIGNALS
        # -------------------------------------------------------------
        panel_slice = panel_df[panel_df["session"] == session].copy()
        new_intended_orders = []
        fund_signals = []
        tech_signals = []

        if not panel_slice.empty:
            # Validate Publication Timestamps & Feature Eligibility
            pred_ts = pd.to_datetime(panel_slice["prediction_timestamp"], utc=True)
            avail_ts = pd.to_datetime(panel_slice.get("available_from_timestamp", pd.Series(np.nan, index=panel_slice.index)), utc=True)

            has_financials = feature_matrix(panel_slice, FUNDAMENTAL).notna().any(axis=1)
            age_days = (pred_ts - avail_ts).dt.total_seconds() / 86400.0

            # Lookahead check
            if (has_financials & age_days.lt(0)).any():
                raise ValueError(
                    f"Lookahead bias detected on session {session}: available_from_timestamp is strictly in the future."
                )

            # Feature eligibility check
            panel_slice["fundamental_eligible"] = has_financials & age_days.between(0, self.max_filing_age_days)
            panel_slice["technical_eligible"] = feature_matrix(panel_slice, TECHNICAL).notna().any(axis=1)

            # A. Fundamental Scoring
            X_f = feature_matrix(panel_slice, FUNDAMENTAL)
            fund_scores = self.ranker.predict(X_f)
            panel_slice["fundamental_score"] = fund_scores

            # Score-Only Baselines
            pe_s = pd.to_numeric(panel_slice.get("pe_ratio", pd.Series(np.nan, index=panel_slice.index)), errors="coerce")
            pb_s = pd.to_numeric(panel_slice.get("pb_ratio", pd.Series(np.nan, index=panel_slice.index)), errors="coerce")
            inv_pe = np.nan_to_num(np.where(pe_s.gt(0), 1.0 / pe_s, -1.0), nan=-1.0)
            inv_pb = np.nan_to_num(np.where(pb_s.gt(0), 1.0 / pb_s, -1.0), nan=-1.0)
            panel_slice["value_score"] = inv_pe + inv_pb
            panel_slice["momentum_score"] = pd.to_numeric(panel_slice.get("momentum_20_pct", pd.Series(0.0, index=panel_slice.index)), errors="coerce").fillna(0.0)

            # Shortlist only fundamental-eligible stocks
            eligible_mask = panel_slice["fundamental_eligible"].astype(bool)
            panel_slice["pctile"] = np.nan
            if eligible_mask.any():
                panel_slice.loc[eligible_mask, "pctile"] = (
                    panel_slice.loc[eligible_mask, "fundamental_score"].rank(pct=True, method="average")
                )
            panel_slice["is_shortlisted"] = (
                panel_slice["fundamental_eligible"] &
                panel_slice["pctile"].gt(1.0 - self.top_fraction)
            ).astype(int)

            # B. Technical Scoring
            X_t = feature_matrix(panel_slice, TECHNICAL)
            tech_probs = self.classifier.predict_proba(X_t)[:, 1]
            panel_slice["technical_prob"] = tech_probs
            panel_slice["has_tech_signal"] = (
                panel_slice["technical_eligible"] &
                (tech_probs >= self.decision_threshold)
            ).astype(int)

            # Save signals separately
            for _, r in panel_slice.iterrows():
                sym = r["symbol"]
                fund_signals.append({
                    "model_version": self.model_version,
                    "outcome_type": "fundamental",
                    "transaction_id": tx_id,
                    "processing_session": session,
                    "signal_session": session,
                    "session": session,
                    "symbol": sym,
                    "evaluation_mode": self.evaluation_mode,
                    "is_prospective": is_prospective,
                    "wall_clock_timestamp_utc": wall_clock_ts,
                    "source_data_cutoff_utc": sig_ts,
                    "timestamp": sig_ts,
                    "fundamental_score": float(r["fundamental_score"]),
                    "fundamental_eligible": int(r["fundamental_eligible"]),
                    "shortlist_flag": int(r["is_shortlisted"]),
                    "value_score": float(r["value_score"]),
                    "momentum_score": float(r["momentum_score"]),
                    "baseline_mode": "SCORE_ONLY_RANKING_BASELINE",
                })
                tech_signals.append({
                    "model_version": self.model_version,
                    "outcome_type": "technical",
                    "transaction_id": tx_id,
                    "processing_session": session,
                    "signal_session": session,
                    "session": session,
                    "symbol": sym,
                    "evaluation_mode": self.evaluation_mode,
                    "is_prospective": is_prospective,
                    "wall_clock_timestamp_utc": wall_clock_ts,
                    "source_data_cutoff_utc": sig_ts,
                    "timestamp": sig_ts,
                    "technical_prob": float(r["technical_prob"]),
                    "decision_threshold": self.decision_threshold,
                    "threshold": self.decision_threshold,
                    "signal_flag": int(r["has_tech_signal"]),
                    "target_hurdle_pct": 2.0,  # Label margin from training
                    "entry_margin_pct": 2.0,
                })

            # C. Generate Intended Orders for Session s+1 Open (if not in circuit breaker)
            # Intended orders are committed in session s, with execution_session = s+1
            # Policy A (Unfiltered Shortlist)
            if not self.circuit_breaker["Policy_A"]["active"]:
                cand_a = panel_slice[panel_slice["is_shortlisted"] == 1].sort_values("fundamental_score", ascending=False)
                held_a = {p.symbol for p in self.positions["Policy_A"]}
                cand_a = cand_a[~cand_a["symbol"].isin(held_a)]
                slots_a = max(0, int(1.0 / self.max_position_weight) - len(self.positions["Policy_A"]))

                if slots_a > 0 and len(cand_a) > 0:
                    selected_a = cand_a.head(slots_a)
                    eq_a = [r["total_equity"] for r in daily_state_rows if r["policy"] == "Policy_A"][0]
                    target_spend_a = eq_a * self.max_position_weight

                    for _, r in selected_a.iterrows():
                        oid = self.next_order_id
                        self.next_order_id += 1
                        new_intended_orders.append({
                            "transaction_id": tx_id,
                            "processing_session": session,
                            "creation_session": session,
                            "signal_session": session,
                            "execution_session": session + 1,
                            "session": session + 1,  # backward compatibility
                            "evaluation_mode": self.evaluation_mode,
                            "is_prospective": is_prospective,
                            "wall_clock_timestamp_utc": wall_clock_ts,
                            "source_data_cutoff_utc": sig_ts,
                            "timestamp": sig_ts,
                            "timing": "OPEN",
                            "order_id": oid,
                            "policy": "Policy_A",
                            "symbol": r["symbol"],
                            "side": "BUY",
                            "intended_spend": target_spend_a,
                            "status": "PENDING",
                        })

            # Policy B (Filtered Shortlist)
            if not self.circuit_breaker["Policy_B"]["active"]:
                cand_b = panel_slice[(panel_slice["is_shortlisted"] == 1) & (panel_slice["has_tech_signal"] == 1)].sort_values("fundamental_score", ascending=False)
                held_b = {p.symbol for p in self.positions["Policy_B"]}
                cand_b = cand_b[~cand_b["symbol"].isin(held_b)]
                slots_b = max(0, int(1.0 / self.max_position_weight) - len(self.positions["Policy_B"]))

                if slots_b > 0 and len(cand_b) > 0:
                    selected_b = cand_b.head(slots_b)
                    eq_b = [r["total_equity"] for r in daily_state_rows if r["policy"] == "Policy_B"][0]
                    target_spend_b = eq_b * self.max_position_weight

                    for _, r in selected_b.iterrows():
                        oid = self.next_order_id
                        self.next_order_id += 1
                        new_intended_orders.append({
                            "transaction_id": tx_id,
                            "processing_session": session,
                            "creation_session": session,
                            "signal_session": session,
                            "execution_session": session + 1,
                            "session": session + 1,  # backward compatibility
                            "evaluation_mode": self.evaluation_mode,
                            "is_prospective": is_prospective,
                            "wall_clock_timestamp_utc": wall_clock_ts,
                            "source_data_cutoff_utc": sig_ts,
                            "timestamp": sig_ts,
                            "timing": "OPEN",
                            "order_id": oid,
                            "policy": "Policy_B",
                            "symbol": r["symbol"],
                            "side": "BUY",
                            "intended_spend": target_spend_b,
                            "status": "PENDING",
                        })

        # -------------------------------------------------------------
        # 5. WRITE APPEND-ONLY LOGS TRANSACTIONALLY
        # -------------------------------------------------------------
        if fills:
            self._append_csv("order_ledger.csv", pd.DataFrame(fills))
        if rejections:
            self._append_csv("rejected_orders.csv", pd.DataFrame(rejections))
        if completed_trades:
            self._append_csv("completed_trades.csv", pd.DataFrame(completed_trades))
        if daily_state_rows:
            self._append_csv("portfolio_daily_state.csv", pd.DataFrame(daily_state_rows))
        if fund_signals:
            self._append_csv("signals_fundamental.csv", pd.DataFrame(fund_signals))
        if tech_signals:
            self._append_csv("signals_technical.csv", pd.DataFrame(tech_signals))
        if new_intended_orders:
            self._append_csv("intended_orders.csv", pd.DataFrame(new_intended_orders))

        # -------------------------------------------------------------
        # 6. EVALUATE & RESOLVE MATURED OUTCOMES
        # -------------------------------------------------------------
        self._record_and_resolve_matured_outcomes(session, prices_df, benchmark_df, sig_ts, wall_clock_ts, is_prospective, tx_id)

        # -------------------------------------------------------------
        # 7. COMMIT SESSION STATE ATOMICALLY
        # -------------------------------------------------------------
        self.last_processed_session = session
        self._save_state()

        records_summary.update({
            "fills_count": len(fills),
            "rejections_count": len(rejections),
            "completed_trades_count": len(completed_trades),
            "new_intended_orders_count": len(new_intended_orders),
            "policy_a_equity": [r["total_equity"] for r in daily_state_rows if r["policy"] == "Policy_A"][0],
            "policy_b_equity": [r["total_equity"] for r in daily_state_rows if r["policy"] == "Policy_B"][0],
            "unresolved_outcomes_count": len(self.unresolved_matured_outcomes),
        })
        return records_summary

    def _record_and_resolve_matured_outcomes(
        self,
        current_session: int,
        prices_df: pd.DataFrame,
        benchmark_df: pd.DataFrame,
        sig_ts: str,
        wall_clock_ts: str,
        is_prospective: bool,
        tx_id: str,
    ):
        """Evaluate matured outcomes matching frozen training definitions, tracking unresolved items."""
        cost_pct = self.cost_rate * 100.0  # 0.50%
        entry_margin_pct = 2.0  # 2.0% hurdle from training

        # 0. Try to resolve any previously enqueued unresolved outcomes
        still_unresolved = []
        for item in self.unresolved_matured_outcomes:
            s_sig = int(item["signal_session"])
            sym = str(item["symbol"])
            o_type = str(item["type"])
            model_ver = item.get("model_version", self.model_version)

            if o_type == "technical":
                target_horizon_s = s_sig + self.holding_period
                # CRITICAL: Always use the original t+10 closing price.
                # If late-arriving historical quote for target_horizon_s is present, evaluate using it.
                # NEVER use close[current_session]!
                p_exit = prices_df[(prices_df["session"] == target_horizon_s) & (prices_df["symbol"] == sym)]
                p_entry = prices_df[(prices_df["session"] == s_sig + 1) & (prices_df["symbol"] == sym)]

                if not p_exit.empty and not p_entry.empty:
                    v_exit = bool(p_exit.iloc[0].get("price_valid", True))
                    close_p = float(p_exit.iloc[0].get("adjusted_close", p_exit.iloc[0].get("close", 0.0)))
                    vol_exit = float(p_exit.iloc[0].get("volume", 1.0))

                    open_p = float(p_entry.iloc[0].get("adjusted_open", p_entry.iloc[0].get("open", 0.0)))
                    v_entry = bool(p_entry.iloc[0].get("price_valid", True))

                    if v_exit and v_entry and close_p > 0 and open_p > 0 and np.isfinite(close_p) and np.isfinite(open_p) and vol_exit > 0:
                        bars_window = prices_df[(prices_df["symbol"] == sym) & (prices_df["session"].between(s_sig, target_horizon_s))]
                        is_valid_window = (len(bars_window) == (self.holding_period + 1))
                        if is_valid_window:
                            good = bars_window.get("price_valid", pd.Series(True, index=bars_window.index)).eq(True)
                            open_vals = bars_window.get("adjusted_open", bars_window.get("open", pd.Series(np.nan, index=bars_window.index)))
                            close_vals = bars_window.get("adjusted_close", bars_window.get("close", pd.Series(np.nan, index=bars_window.index)))
                            good &= np.isfinite(open_vals) & open_vals.gt(0)
                            good &= np.isfinite(close_vals) & close_vals.gt(0)
                            is_valid_window = bool(good.all())

                        stk_ret = 100.0 * (close_p / open_p - 1.0)
                        net_stk_ret = stk_ret - cost_pct
                        realized_hurdle = int(net_stk_ret > entry_margin_pct) if is_valid_window else None

                        b_entry = benchmark_df[benchmark_df["session"] == s_sig + 1]
                        b_exit = benchmark_df[benchmark_df["session"] == target_horizon_s]
                        b_open = float(b_entry.iloc[0].get("adjusted_close", b_entry.iloc[0].get("benchmark_close", 1.0))) if not b_entry.empty else 1.0
                        b_close = float(b_exit.iloc[0].get("adjusted_close", b_exit.iloc[0].get("benchmark_close", 1.0))) if not b_exit.empty else 1.0
                        bm_ret = 100.0 * (b_close / b_open - 1.0) if b_open > 0 else 0.0

                        # Preserve original prediction identity
                        orig_prob = item.get("technical_prob")
                        orig_flag = item.get("signal_flag")
                        orig_thresh = item.get("decision_threshold", self.decision_threshold)
                        if orig_prob is None or orig_flag is None or pd.isna(orig_prob):
                            sig_orig = self._lookup_original_signal("technical", s_sig, sym)
                            orig_prob = sig_orig.get("technical_prob", orig_prob)
                            orig_flag = sig_orig.get("signal_flag", orig_flag)
                            orig_thresh = sig_orig.get("decision_threshold", orig_thresh)

                        resolved_row = pd.DataFrame([{
                            "model_version": model_ver,
                            "outcome_type": "technical",
                            "transaction_id": tx_id,
                            "processing_session": current_session,
                            "creation_session": s_sig,
                            "signal_session": s_sig,
                            "entry_session": s_sig + 1,
                            "execution_session": s_sig + 1,
                            "maturity_session": target_horizon_s,
                            "session": s_sig,
                            "symbol": sym,
                            "evaluation_mode": self.evaluation_mode,
                            "is_prospective": is_prospective,
                            "wall_clock_timestamp_utc": wall_clock_ts,
                            "timestamp": sig_ts,
                            "technical_prob": orig_prob,
                            "decision_threshold": orig_thresh,
                            "threshold": orig_thresh,
                            "signal_flag": orig_flag,
                            "stock_open_price": open_p,
                            "stock_close_price": close_p,
                            "gross_stock_return_pct": stk_ret,
                            "cost_deduction_pct": cost_pct,
                            "net_stock_return_pct": net_stk_ret,
                            "target_hurdle_pct": entry_margin_pct,
                            "entry_margin_pct": entry_margin_pct,
                            "realized_hurdle_label": realized_hurdle,
                            "benchmark_forward_return_pct": bm_ret,
                            "benchmark_relative_excess_return_pct": net_stk_ret - bm_ret,
                            "is_valid_price_window": is_valid_window,
                            "is_delayed_resolution": True,
                            "outcome_status": "RESOLVED_DELAYED",
                            "is_censored": False,
                        }])
                        self._append_csv("matured_technical_outcomes.csv", resolved_row)
                        continue
                    else:
                        item["attempts"] = item.get("attempts", 1) + 1
                        item["last_attempt_session"] = current_session
                        still_unresolved.append(item)
                        continue
                else:
                    item["attempts"] = item.get("attempts", 1) + 1
                    item["last_attempt_session"] = current_session
                    still_unresolved.append(item)
                    continue

            elif o_type == "fundamental":
                target_horizon_f = s_sig + 126
                p_start = prices_df[(prices_df["session"] == s_sig) & (prices_df["symbol"] == sym)]
                p_end = prices_df[(prices_df["session"] == target_horizon_f) & (prices_df["symbol"] == sym)]

                if not p_start.empty and not p_end.empty:
                    p_start_adj = float(p_start.iloc[0].get("adjusted_close", p_start.iloc[0].get("close", 0.0)))
                    p_end_adj = float(p_end.iloc[0].get("adjusted_close", p_end.iloc[0].get("close", 0.0)))
                    v_start = bool(p_start.iloc[0].get("price_valid", True))
                    v_end = bool(p_end.iloc[0].get("price_valid", True))

                    b_start = benchmark_df[benchmark_df["session"] == s_sig]
                    b_end = benchmark_df[benchmark_df["session"] == target_horizon_f]

                    if p_start_adj > 0 and p_end_adj > 0 and v_start and v_end and not b_start.empty and not b_end.empty:
                        b_start_adj = float(b_start.iloc[0].get("adjusted_close", b_start.iloc[0].get("benchmark_close", 1.0)))
                        b_end_adj = float(b_end.iloc[0].get("adjusted_close", b_end.iloc[0].get("benchmark_close", 1.0)))

                        sub_prices = prices_df[(prices_df["symbol"] == sym) & (prices_df["session"].between(s_sig, target_horizon_f))]
                        is_valid_window = (len(sub_prices) == 127) and sub_prices.get("price_valid", pd.Series(True, index=sub_prices.index)).all()

                        stk_ret = 100.0 * (p_end_adj / p_start_adj - 1.0)
                        bm_ret = 100.0 * (b_end_adj / b_start_adj - 1.0)
                        excess_target = 100.0 * (p_end_adj / p_start_adj - b_end_adj / b_start_adj)

                        p_t1_open = prices_df[(prices_df["session"] == s_sig + 1) & (prices_df["symbol"] == sym)]
                        exec_ret = None
                        if not p_t1_open.empty:
                            op = float(p_t1_open.iloc[0].get("open", p_t1_open.iloc[0].get("adjusted_open", 0.0)))
                            if op > 0:
                                exec_ret = 100.0 * (p_end_adj / op - 1.0)

                        orig_score = item.get("fundamental_score")
                        orig_flag = item.get("shortlist_flag")
                        orig_rank = item.get("rank")
                        if orig_score is None or orig_flag is None:
                            sig_orig = self._lookup_original_signal("fundamental", s_sig, sym)
                            orig_score = sig_orig.get("fundamental_score", orig_score)
                            orig_flag = sig_orig.get("shortlist_flag", orig_flag)
                            orig_rank = sig_orig.get("rank", orig_rank)

                        resolved_f_row = pd.DataFrame([{
                            "model_version": model_ver,
                            "outcome_type": "fundamental",
                            "transaction_id": tx_id,
                            "processing_session": current_session,
                            "creation_session": s_sig,
                            "signal_session": s_sig,
                            "maturity_session": target_horizon_f,
                            "session": s_sig,
                            "symbol": sym,
                            "evaluation_mode": self.evaluation_mode,
                            "is_prospective": is_prospective,
                            "wall_clock_timestamp_utc": wall_clock_ts,
                            "timestamp": sig_ts,
                            "fundamental_score": orig_score,
                            "shortlist_flag": orig_flag,
                            "rank": orig_rank,
                            "stock_start_adj_close": p_start_adj,
                            "stock_end_adj_close": p_end_adj,
                            "benchmark_start_adj_close": b_start_adj,
                            "benchmark_end_adj_close": b_end_adj,
                            "stock_cumulative_return_pct": stk_ret,
                            "benchmark_cumulative_return_pct": bm_ret,
                            "fundamental_training_target_excess_return_pct": excess_target,
                            "is_valid_target_window": is_valid_window,
                            "executable_open_to_close_return_pct": exec_ret,
                            "is_delayed_resolution": True,
                            "outcome_status": "RESOLVED_DELAYED",
                            "is_censored": False,
                        }])
                        self._append_csv("matured_fundamental_outcomes.csv", resolved_f_row)
                        continue
                    else:
                        item["attempts"] = item.get("attempts", 1) + 1
                        item["last_attempt_session"] = current_session
                        still_unresolved.append(item)
                        continue
                else:
                    item["attempts"] = item.get("attempts", 1) + 1
                    item["last_attempt_session"] = current_session
                    still_unresolved.append(item)
                    continue

        self.unresolved_matured_outcomes = still_unresolved

        # A. Technical Outcomes (horizon = 10 sessions)
        tech_file = self.eval_dir / "signals_technical.csv"
        target_tech_session = current_session - self.holding_period

        if tech_file.exists():
            df_tech = pd.read_csv(tech_file)
            sig_col = "signal_session" if "signal_session" in df_tech.columns else "session"
            matured_candidates = df_tech[df_tech[sig_col] == target_tech_session].copy()

            matured_rows = []
            for _, r in matured_candidates.iterrows():
                sym = r["symbol"]
                s_sig = int(r[sig_col])

                # Check quotes for s_sig+1 Open and current_session Close
                p_entry = prices_df[(prices_df["session"] == s_sig + 1) & (prices_df["symbol"] == sym)]
                p_exit = prices_df[(prices_df["session"] == current_session) & (prices_df["symbol"] == sym)]

                if p_entry.empty or p_exit.empty:
                    self._enqueue_unresolved("technical", s_sig, sym, current_session, "MISSING_PRICE_BARS", orig_row=r.to_dict())
                    continue

                open_p = float(p_entry.iloc[0].get("adjusted_open", p_entry.iloc[0].get("open", 0.0)))
                close_p = float(p_exit.iloc[0].get("adjusted_close", p_exit.iloc[0].get("close", 0.0)))
                v_entry = bool(p_entry.iloc[0].get("price_valid", True))
                v_exit = bool(p_exit.iloc[0].get("price_valid", True))
                vol_exit = float(p_exit.iloc[0].get("volume", 1.0))

                # If exit quote is invalid, suspended or missing, enqueue for delayed resolution
                if not v_exit or vol_exit <= 0 or close_p <= 0 or not np.isfinite(close_p):
                    self._enqueue_unresolved("technical", s_sig, sym, current_session, "SUSPENSION_OR_MISSING_EXIT_PRICE", orig_row=r.to_dict())
                    continue

                if not v_entry or open_p <= 0 or not np.isfinite(open_p):
                    self._enqueue_unresolved("technical", s_sig, sym, current_session, "INVALID_ENTRY_PRICE", orig_row=r.to_dict())
                    continue

                b_entry = benchmark_df[benchmark_df["session"] == s_sig + 1]
                b_exit = benchmark_df[benchmark_df["session"] == current_session]

                if b_entry.empty or b_exit.empty:
                    self._enqueue_unresolved("technical", s_sig, sym, current_session, "MISSING_BENCHMARK_BARS", orig_row=r.to_dict())
                    continue

                b_open = float(b_entry.iloc[0].get("adjusted_close", b_entry.iloc[0].get("benchmark_close", 1.0)))
                b_close = float(b_exit.iloc[0].get("adjusted_close", b_exit.iloc[0].get("benchmark_close", 1.0)))

                # Check contiguous 11-session window validity from s_sig to current_session (s_sig + 10)
                bars_window = prices_df[(prices_df["symbol"] == sym) & (prices_df["session"].between(s_sig, current_session))]
                is_valid_window = (len(bars_window) == (self.holding_period + 1))
                if is_valid_window:
                    good = bars_window.get("price_valid", pd.Series(True, index=bars_window.index)).eq(True)
                    open_vals = bars_window.get("adjusted_open", bars_window.get("open", pd.Series(np.nan, index=bars_window.index)))
                    close_vals = bars_window.get("adjusted_close", bars_window.get("close", pd.Series(np.nan, index=bars_window.index)))
                    good &= np.isfinite(open_vals) & open_vals.gt(0)
                    good &= np.isfinite(close_vals) & close_vals.gt(0)
                    is_valid_window = bool(good.all())

                stk_ret = 100.0 * (close_p / open_p - 1.0)
                bm_ret = 100.0 * (b_close / b_open - 1.0) if b_open > 0 else 0.0
                net_stk_ret = stk_ret - cost_pct
                
                # MATCH TRAINING EXACTLY: DO NOT subtract benchmark return from label
                realized_hurdle = int(net_stk_ret > entry_margin_pct) if is_valid_window else None
                bm_relative_excess_ret = net_stk_ret - bm_ret

                matured_rows.append({
                    "model_version": self.model_version,
                    "outcome_type": "technical",
                    "transaction_id": tx_id,
                    "processing_session": current_session,
                    "creation_session": s_sig,
                    "signal_session": s_sig,
                    "entry_session": s_sig + 1,
                    "execution_session": s_sig + 1,
                    "maturity_session": current_session,
                    "session": s_sig,  # backward compatibility
                    "symbol": sym,
                    "evaluation_mode": self.evaluation_mode,
                    "is_prospective": is_prospective,
                    "wall_clock_timestamp_utc": wall_clock_ts,
                    "timestamp": sig_ts,
                    "technical_prob": r["technical_prob"],
                    "decision_threshold": self.decision_threshold,
                    "threshold": self.decision_threshold,
                    "signal_flag": r["signal_flag"],
                    "stock_open_price": open_p,
                    "stock_close_price": close_p,
                    "gross_stock_return_pct": stk_ret,
                    "cost_deduction_pct": cost_pct,
                    "net_stock_return_pct": net_stk_ret,
                    "target_hurdle_pct": entry_margin_pct,
                    "entry_margin_pct": entry_margin_pct,
                    "realized_hurdle_label": realized_hurdle,
                    "benchmark_forward_return_pct": bm_ret,
                    "benchmark_relative_excess_return_pct": bm_relative_excess_ret,
                    "is_valid_price_window": is_valid_window,
                    "is_delayed_resolution": False,
                    "outcome_status": "RESOLVED_ON_TIME",
                    "is_censored": False,
                })

            if matured_rows:
                self._append_csv("matured_technical_outcomes.csv", pd.DataFrame(matured_rows))

        # B. Fundamental Outcomes (horizon = 126 sessions)
        # Training Definition: Start at s_sig Close, End at s_sig+126 Close on adjusted_close.
        # Excess return = 100 * (P_{t+126} / P_t - B_{t+126} / B_t).
        fund_file = self.eval_dir / "signals_fundamental.csv"
        target_fund_session = current_session - 126

        if fund_file.exists():
            df_fund = pd.read_csv(fund_file)
            sig_col_f = "signal_session" if "signal_session" in df_fund.columns else "session"
            matured_fund_cand = df_fund[df_fund[sig_col_f] == target_fund_session].copy()

            matured_f_rows = []
            for _, r in matured_fund_cand.iterrows():
                sym = r["symbol"]
                s_sig = int(r[sig_col_f])

                p_start = prices_df[(prices_df["session"] == s_sig) & (prices_df["symbol"] == sym)]
                p_end = prices_df[(prices_df["session"] == current_session) & (prices_df["symbol"] == sym)]

                if not p_start.empty and not p_end.empty:
                    p_start_adj = float(p_start.iloc[0].get("adjusted_close", p_start.iloc[0].get("close", 0.0)))
                    p_end_adj = float(p_end.iloc[0].get("adjusted_close", p_end.iloc[0].get("close", 0.0)))
                    v_start = bool(p_start.iloc[0].get("price_valid", True))
                    v_end = bool(p_end.iloc[0].get("price_valid", True))

                    b_start = benchmark_df[benchmark_df["session"] == s_sig]
                    b_end = benchmark_df[benchmark_df["session"] == current_session]

                    if p_start_adj > 0 and p_end_adj > 0 and v_start and v_end and not b_start.empty and not b_end.empty:
                        b_start_adj = float(b_start.iloc[0].get("adjusted_close", b_start.iloc[0].get("benchmark_close", 1.0)))
                        b_end_adj = float(b_end.iloc[0].get("adjusted_close", b_end.iloc[0].get("benchmark_close", 1.0)))

                        # Check contiguous valid target window (127 sessions)
                        sub_prices = prices_df[(prices_df["symbol"] == sym) & (prices_df["session"].between(s_sig, current_session))]
                        is_valid_window = (len(sub_prices) == 127) and sub_prices.get("price_valid", pd.Series(True, index=sub_prices.index)).all()

                        stk_ret = 100.0 * (p_end_adj / p_start_adj - 1.0)
                        bm_ret = 100.0 * (b_end_adj / b_start_adj - 1.0)
                        excess_target = 100.0 * (p_end_adj / p_start_adj - b_end_adj / b_start_adj)

                        # Separately named executable portfolio metric (T+1 Open to T+126 Close)
                        p_t1_open = prices_df[(prices_df["session"] == s_sig + 1) & (prices_df["symbol"] == sym)]
                        exec_ret = None
                        if not p_t1_open.empty:
                            op = float(p_t1_open.iloc[0].get("open", p_t1_open.iloc[0].get("adjusted_open", 0.0)))
                            if op > 0:
                                exec_ret = 100.0 * (p_end_adj / op - 1.0)

                        matured_f_rows.append({
                            "model_version": self.model_version,
                            "outcome_type": "fundamental",
                            "transaction_id": tx_id,
                            "processing_session": current_session,
                            "creation_session": s_sig,
                            "signal_session": s_sig,
                            "maturity_session": current_session,
                            "session": s_sig,  # backward compatibility
                            "symbol": sym,
                            "evaluation_mode": self.evaluation_mode,
                            "is_prospective": is_prospective,
                            "wall_clock_timestamp_utc": wall_clock_ts,
                            "timestamp": sig_ts,
                            "fundamental_score": r["fundamental_score"],
                            "shortlist_flag": r["shortlist_flag"],
                            "stock_start_adj_close": p_start_adj,
                            "stock_end_adj_close": p_end_adj,
                            "benchmark_start_adj_close": b_start_adj,
                            "benchmark_end_adj_close": b_end_adj,
                            "stock_cumulative_return_pct": stk_ret,
                            "benchmark_cumulative_return_pct": bm_ret,
                            "fundamental_training_target_excess_return_pct": excess_target,
                            "is_valid_target_window": is_valid_window,
                            "executable_open_to_close_return_pct": exec_ret,
                            "is_delayed_resolution": False,
                            "outcome_status": "RESOLVED_ON_TIME",
                            "is_censored": False,
                        })
                    else:
                        self._enqueue_unresolved("fundamental", s_sig, sym, current_session, "INVALID_OR_MISSING_PRICE", orig_row=r.to_dict())
                else:
                    self._enqueue_unresolved("fundamental", s_sig, sym, current_session, "MISSING_PRICE_BARS", orig_row=r.to_dict())

            if matured_f_rows:
                self._append_csv("matured_fundamental_outcomes.csv", pd.DataFrame(matured_f_rows))

    def _lookup_original_signal(self, o_type: str, s_sig: int, sym: str) -> dict[str, Any]:
        """Retrieve the exact original signal row from persisted signal CSV files."""
        filename = "signals_technical.csv" if o_type == "technical" else "signals_fundamental.csv"
        path = self.eval_dir / filename
        if path.exists():
            df = pd.read_csv(path)
            sig_col = "signal_session" if "signal_session" in df.columns else "session"
            match = df[(df[sig_col] == s_sig) & (df["symbol"] == sym)]
            if not match.empty:
                return match.iloc[0].to_dict()
        return {}

    def _enqueue_unresolved(
        self,
        o_type: str,
        s_sig: int,
        sym: str,
        current_s: int,
        reason: str,
        orig_row: dict[str, Any] | None = None,
    ):
        """Enqueue an unresolved outcome preserving full original prediction identity."""
        orig = orig_row or self._lookup_original_signal(o_type, s_sig, sym)
        for item in self.unresolved_matured_outcomes:
            if item.get("type") == o_type and int(item.get("signal_session", -1)) == s_sig and item.get("symbol") == sym:
                item["attempts"] = item.get("attempts", 1) + 1
                item["last_attempt_session"] = current_s
                item["reason"] = reason
                return

        target_horizon_session = s_sig + (self.holding_period if o_type == "technical" else 126)
        self.unresolved_matured_outcomes.append({
            "type": o_type,
            "model_version": orig.get("model_version", self.model_version),
            "signal_session": s_sig,
            "symbol": sym,
            "target_horizon_session": target_horizon_session,
            "first_failed_session": current_s,
            "scheduled_session": current_s,
            "last_attempt_session": current_s,
            "attempts": 1,
            "reason": reason,
            "technical_prob": orig.get("technical_prob"),
            "decision_threshold": orig.get("decision_threshold", self.decision_threshold),
            "signal_flag": orig.get("signal_flag"),
            "fundamental_score": orig.get("fundamental_score"),
            "shortlist_flag": orig.get("shortlist_flag"),
            "rank": orig.get("rank"),
        })

    def censor_unresolved_outcome(self, o_type: str, s_sig: int, sym: str, reason: str = "CENSORED_MISSING_HORIZON_QUOTE"):
        """Explicitly record a permanently unavailable horizon outcome as censored."""
        orig = self._lookup_original_signal(o_type, s_sig, sym)
        model_ver = orig.get("model_version", self.model_version)
        current_s = self.last_processed_session or s_sig

        if o_type == "technical":
            target_horizon_s = s_sig + self.holding_period
            censored_row = pd.DataFrame([{
                "model_version": model_ver,
                "outcome_type": "technical",
                "transaction_id": f"tx_censor_s{current_s}",
                "processing_session": current_s,
                "creation_session": s_sig,
                "signal_session": s_sig,
                "entry_session": s_sig + 1,
                "execution_session": s_sig + 1,
                "maturity_session": target_horizon_s,
                "session": s_sig,
                "symbol": sym,
                "evaluation_mode": self.evaluation_mode,
                "is_prospective": False,
                "wall_clock_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "technical_prob": orig.get("technical_prob"),
                "decision_threshold": orig.get("decision_threshold", self.decision_threshold),
                "threshold": orig.get("decision_threshold", self.decision_threshold),
                "signal_flag": orig.get("signal_flag"),
                "stock_open_price": np.nan,
                "stock_close_price": np.nan,
                "gross_stock_return_pct": np.nan,
                "cost_deduction_pct": self.cost_rate * 100.0,
                "net_stock_return_pct": np.nan,
                "target_hurdle_pct": 2.0,
                "entry_margin_pct": 2.0,
                "realized_hurdle_label": None,
                "benchmark_forward_return_pct": np.nan,
                "benchmark_relative_excess_return_pct": np.nan,
                "is_valid_price_window": False,
                "is_delayed_resolution": True,
                "outcome_status": reason,
                "is_censored": True,
            }])
            self._append_csv("matured_technical_outcomes.csv", censored_row)
        self.unresolved_matured_outcomes = [
            u for u in self.unresolved_matured_outcomes
            if not (u.get("type") == o_type and int(u.get("signal_session", -1)) == s_sig and u.get("symbol") == sym)
        ]
        self._save_state()


def run_paper_replay(
    start_session: int,
    end_session: int,
    eval_dir: Path,
    panel_path: Path = Path("data/decision_panel_v2.csv"),
    prices_path: Path = Path("data/raw_unadjusted_prices.csv"),
    benchmark_path: Path = Path("data/audited_benchmark.csv"),
    release_dir: Path = Path("artifacts/frozen_research_release"),
) -> dict[str, Any]:
    """Execute a clearly labeled paper evaluation replay across a historical test calendar."""
    eval_dir = Path(eval_dir)
    print(f"Loading data for paper evaluation replay [{start_session} -> {end_session}]...")
    panel = pd.read_csv(panel_path)
    prices = pd.read_csv(prices_path)
    bench = pd.read_csv(benchmark_path)

    # Ensure required columns
    if "open" not in prices.columns and "adjusted_open" in prices.columns:
        prices["open"] = prices["adjusted_open"]
    if "close" not in prices.columns and "adjusted_close" in prices.columns:
        prices["close"] = prices["adjusted_close"]
    if "price_valid" not in prices.columns:
        prices["price_valid"] = True
    if "price_valid" not in bench.columns:
        bench["price_valid"] = True

    if "volume" not in prices.columns or prices["volume"].isna().all():
        prices = pd.merge(prices, panel[["symbol", "session", "volume"]], on=["symbol", "session"], how="left")

    engine = PaperEvaluationEngine(
        eval_dir=eval_dir,
        release_dir=release_dir,
        evaluation_mode="HISTORICAL_REPLAY",
    )

    sessions_to_run = sorted([s for s in range(start_session, end_session + 1) if s in prices["session"].unique()])
    print(f"Running replay across {len(sessions_to_run)} trading sessions...")

    summaries = []
    for s in sessions_to_run:
        res = engine.process_session(
            session=s,
            prices_df=prices,
            panel_df=panel,
            benchmark_df=bench,
        )
        summaries.append(res)

    print(f"Replay completed for {len(summaries)} sessions. Results saved in {eval_dir}.")
    return {
        "start_session": start_session,
        "end_session": end_session,
        "total_sessions_run": len(summaries),
        "final_policy_a_equity": engine.cash["Policy_A"] + sum(p.shares * p.last_known_close for p in engine.positions["Policy_A"]),
        "final_policy_b_equity": engine.cash["Policy_B"] + sum(p.shares * p.last_known_close for p in engine.positions["Policy_B"]),
        "policy_a_active_positions": len(engine.positions["Policy_A"]),
        "policy_b_active_positions": len(engine.positions["Policy_B"]),
        "circuit_breaker_policy_a": engine.circuit_breaker["Policy_A"]["active"],
        "circuit_breaker_policy_b": engine.circuit_breaker["Policy_B"]["active"],
        "unresolved_outcomes": len(engine.unresolved_matured_outcomes),
    }


def main():
    parser = argparse.ArgumentParser(description="PSXpert Append-Only Paper Evaluation Workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Step command
    p_step = subparsers.add_parser("step", help="Step forward one market session")
    p_step.add_argument("--session", type=int, required=True, help="Market session ID to execute")
    p_step.add_argument("--eval-dir", default="artifacts/paper_eval", help="Directory for paper evaluation logs")
    p_step.add_argument("--release-dir", default="artifacts/frozen_research_release", help="Release directory")
    p_step.add_argument("--panel", default="data/decision_panel_v2.csv", help="Panel data path")
    p_step.add_argument("--prices", default="data/raw_unadjusted_prices.csv", help="Prices path")
    p_step.add_argument("--benchmark", default="data/audited_benchmark.csv", help="Benchmark path")

    # Replay command
    p_rep = subparsers.add_parser("replay", help="Run a multi-session replay validation test")
    p_rep.add_argument("--start-session", type=int, required=True, help="First session ID")
    p_rep.add_argument("--end-session", type=int, required=True, help="Last session ID")
    p_rep.add_argument("--eval-dir", default="artifacts/paper_eval_replay_test", help="Directory for replay logs")
    p_rep.add_argument("--release-dir", default="artifacts/frozen_research_release", help="Release directory")
    p_rep.add_argument("--panel", default="data/decision_panel_v2.csv", help="Panel data path")
    p_rep.add_argument("--prices", default="data/raw_unadjusted_prices.csv", help="Prices path")
    p_rep.add_argument("--benchmark", default="data/audited_benchmark.csv", help="Benchmark path")

    # Resume circuit breaker command
    p_res = subparsers.add_parser("resume-circuit-breaker", help="Administratively clear circuit breaker halt")
    p_res.add_argument("--policy", required=True, choices=["Policy_A", "Policy_B"], help="Policy to resume")
    p_res.add_argument("--rationale", required=True, help="Documented formal audit rationale for clearing halt")
    p_res.add_argument("--eval-dir", default="artifacts/paper_eval", help="Directory for paper evaluation logs")

    # Status command
    p_stat = subparsers.add_parser("status", help="Display current paper evaluation portfolio status")
    p_stat.add_argument("--eval-dir", default="artifacts/paper_eval", help="Directory for paper evaluation logs")

    args = parser.parse_args()

    if args.command == "step":
        panel = pd.read_csv(args.panel)
        prices = pd.read_csv(args.prices)
        bench = pd.read_csv(args.benchmark)
        if "open" not in prices.columns:
            prices["open"] = prices["adjusted_open"]
        if "close" not in prices.columns:
            prices["close"] = prices["adjusted_close"]
        if "price_valid" not in prices.columns:
            prices["price_valid"] = True
        if "price_valid" not in bench.columns:
            bench["price_valid"] = True
        if "volume" not in prices.columns or prices["volume"].isna().all():
            prices = pd.merge(prices, panel[["symbol", "session", "volume"]], on=["symbol", "session"], how="left")

        engine = PaperEvaluationEngine(
            eval_dir=Path(args.eval_dir),
            release_dir=Path(args.release_dir),
            evaluation_mode="PROSPECTIVE_PAPER",
        )
        res = engine.process_session(session=args.session, prices_df=prices, panel_df=panel, benchmark_df=bench)
        print(json.dumps(res, indent=2))

    elif args.command == "replay":
        res = run_paper_replay(
            start_session=args.start_session,
            end_session=args.end_session,
            eval_dir=Path(args.eval_dir),
            panel_path=Path(args.panel),
            prices_path=Path(args.prices),
            benchmark_path=Path(args.benchmark),
            release_dir=Path(args.release_dir),
        )
        print(json.dumps(res, indent=2))

    elif args.command == "resume-circuit-breaker":
        engine = PaperEvaluationEngine(eval_dir=Path(args.eval_dir))
        engine.resume_after_circuit_breaker(policy=args.policy, audit_rationale=args.rationale)
        print(f"Circuit breaker cleared for {args.policy} with documented rationale.")

    elif args.command == "status":
        state_file = Path(args.eval_dir) / "engine_state.json"
        if not state_file.exists():
            print(f"No active paper evaluation engine found at {args.eval_dir}")
        else:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            print("=== PSXpert Paper Evaluation Status ===")
            print(f"Evaluation Mode: {state.get('config', {}).get('evaluation_mode', 'UNKNOWN')}")
            print(f"Last Processed Session: {state['last_processed_session']}")
            print(f"Policy A Cash: PKR {state['cash']['Policy_A']:,.2f}")
            print(f"Policy B Cash: PKR {state['cash']['Policy_B']:,.2f}")
            print(f"Policy A Peak Equity: PKR {state['peak_equity']['Policy_A']:,.2f}")
            print(f"Policy B Peak Equity: PKR {state['peak_equity']['Policy_B']:,.2f}")
            print(f"Policy A Circuit Breaker Active: {state['circuit_breaker']['Policy_A']['active']}")
            print(f"Policy B Circuit Breaker Active: {state['circuit_breaker']['Policy_B']['active']}")
            print(f"Unresolved Matured Outcomes: {len(state.get('unresolved_matured_outcomes', []))}")


if __name__ == "__main__":
    main()
