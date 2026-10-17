"""
PSXpert - Genetic Algorithm (GA) Quantitative Parameter & Strategy Optimizer
Optimizes technical-indicator parameters and latent regime filters
under a rigorous risk-adjusted evaluation objective (Sharpe - 2*MaxDD).
Compares against standard fixed baseline parameters.
"""

from typing import Dict, List, Optional, Any, Tuple
import random
import numpy as np
import pandas as pd


# Gene specifications: (type, min_val, max_val, baseline_val)
GENE_BOUNDS = {
    "rsi_period": (int, 6, 26, 14),
    "rsi_oversold": (int, 20, 42, 30),
    "rsi_overbought": (int, 58, 80, 70),
    "ema_fast": (int, 5, 20, 12),
    "ema_slow": (int, 22, 60, 26),
    "macd_signal": (int, 5, 15, 9),
    "bb_std": (float, 1.5, 2.8, 2.0),
    "stop_loss_pct": (float, 0.02, 0.08, 0.05),
    "take_profit_pct": (float, 0.05, 0.18, 0.10),
    "use_regime_filter": (int, 0, 1, 0)
}

BASELINE_PARAMS = {k: v[3] for k, v in GENE_BOUNDS.items()}


class FastStrategyBacktester:
    """
    High-performance backtester for technical indicator rules
    and regime-conditioned execution.
    """

    @staticmethod
    def run_backtest(df: pd.DataFrame, params: Dict[str, Any], regimes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Runs strategy simulation over price series with given parameter set.
        """
        if df.empty or len(df) < 20:
            return {"fitness": -999.0, "total_return_pct": 0.0, "sharpe_ratio": 0.0, "max_drawdown_pct": 0.0, "win_rate_pct": 0.0, "total_trades": 0}

        closes = pd.to_numeric(df["close"], errors="coerce").values.astype(float)
        highs = pd.to_numeric(df["high"], errors="coerce").values.astype(float)
        lows = pd.to_numeric(df["low"], errors="coerce").values.astype(float)
        n = len(closes)

        rsi_period = int(params["rsi_period"])
        rsi_os = float(params["rsi_oversold"])
        rsi_ob = float(params["rsi_overbought"])
        ema_f_period = int(params["ema_fast"])
        ema_s_period = int(params["ema_slow"])
        macd_sig_period = int(params["macd_signal"])
        bb_std_mult = float(params["bb_std"])
        stop_loss = float(params["stop_loss_pct"])
        take_profit = float(params["take_profit_pct"])
        use_regime = int(params.get("use_regime_filter", 0))

        # Vectorized Indicators
        close_series = pd.Series(closes)
        
        # 1. EMA fast & slow
        ema_fast = close_series.ewm(span=ema_f_period, adjust=False).mean().values
        ema_slow = close_series.ewm(span=ema_s_period, adjust=False).mean().values

        # 2. MACD
        macd_line = ema_fast - ema_slow
        macd_signal = pd.Series(macd_line).ewm(span=macd_sig_period, adjust=False).mean().values

        # 3. RSI (Wilder)
        delta = close_series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1.0 / rsi_period, min_periods=rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / rsi_period, min_periods=rsi_period, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        rsi = (100.0 - (100.0 / (1.0 + rs))).values

        # 4. Bollinger Bands (20-period middle)
        bb_mid = close_series.rolling(20, min_periods=20).mean().values
        bb_std = close_series.rolling(20, min_periods=20).std().values
        bb_lower = bb_mid - (bb_std_mult * bb_std)
        bb_upper = bb_mid + (bb_std_mult * bb_std)

        # Simulation Loop
        in_position = False
        entry_price = 0.0
        equity = 1.0
        equity_curve = [1.0]
        daily_returns = []
        trades = []

        start_idx = max(rsi_period, ema_s_period, 20)

        for t in range(start_idx, n):
            c_price = closes[t]
            regime = regimes[t] if (regimes and t < len(regimes)) else "UNKNOWN"

            # Check Exit Conditions if in position
            if in_position:
                pct_change = (c_price - entry_price) / (entry_price + 1e-9)
                exit_signal = False
                exit_reason = ""

                # Stop loss or take profit
                if pct_change <= -stop_loss:
                    exit_signal = True
                    exit_reason = "Stop Loss"
                elif pct_change >= take_profit:
                    exit_signal = True
                    exit_reason = "Take Profit"
                # Technical exit: RSI overbought or EMA bearish cross
                elif rsi[t] >= rsi_ob or (ema_fast[t] < ema_slow[t] and macd_line[t] < macd_signal[t]):
                    exit_signal = True
                    exit_reason = "Technical Reversal"
                # Regime exit: if regime filter active and market flipped Bearish
                elif use_regime and regime == "BEARISH":
                    exit_signal = True
                    exit_reason = "HMM Bearish Regime Exit"

                if exit_signal:
                    in_position = False
                    equity *= (1.0 + pct_change)
                    trades.append(pct_change)
                    daily_returns.append(pct_change)
                else:
                    # Daily price return while holding
                    day_ret = (closes[t] - closes[t-1]) / closes[t-1]
                    daily_returns.append(day_ret)

            else:
                # Check Entry Conditions
                daily_returns.append(0.0)
                
                # Signal 1: RSI oversold bounce
                rsi_buy = (rsi[t] < rsi_os) and (rsi[t] > rsi[t-1])
                # Signal 2: Trend confirmation
                trend_buy = (ema_fast[t] > ema_slow[t]) and (macd_line[t] > macd_signal[t])
                # Signal 3: Price touching lower band
                bb_buy = (c_price <= bb_lower[t] * 1.01) if not np.isnan(bb_lower[t]) else False

                regime_allowed = True
                if use_regime:
                    # In regime filter mode: avoid Bearish regimes completely
                    regime_allowed = (regime != "BEARISH")

                if (rsi_buy or (trend_buy and bb_buy)) and regime_allowed:
                    in_position = True
                    entry_price = c_price

            equity_curve.append(equity)

        # Performance Metrics Computation
        total_trades = len(trades)
        win_trades = sum(1 for t in trades if t > 0)
        win_rate = (win_trades / total_trades * 100.0) if total_trades > 0 else 0.0

        daily_returns_arr = np.array(daily_returns)
        total_return = (equity - 1.0) * 100.0

        # Annualized metrics
        trading_days = max(len(daily_returns), 1)
        years = trading_days / 252.0
        annualized_return = ((equity ** (1.0 / max(years, 0.1))) - 1.0) * 100.0 if equity > 0 else -100.0

        ret_std = np.std(daily_returns_arr) * np.sqrt(252)
        sharpe = (annualized_return / (ret_std * 100.0 + 1e-6)) if ret_std > 0 else -1.0

        # Maximum Drawdown
        eq_arr = np.array(equity_curve)
        cum_max = np.maximum.accumulate(eq_arr)
        drawdowns = (cum_max - eq_arr) / cum_max
        max_dd = float(np.max(drawdowns)) * 100.0

        # Fitness function: penalize high drawdowns and low trades
        # Fitness = Sharpe - 2.0 * MaxDD_normalized
        max_dd_penalty = (max_dd / 100.0) * 2.0
        trade_penalty = 0.0 if total_trades >= 6 else (6 - total_trades) * 0.5
        fitness = float(sharpe - max_dd_penalty - trade_penalty)

        return {
            "fitness": round(float(fitness), 4),
            "total_return_pct": round(float(total_return), 2),
            "annualized_return_pct": round(float(annualized_return), 2),
            "sharpe_ratio": round(float(sharpe), 3),
            "max_drawdown_pct": round(float(max_dd), 2),
            "win_rate_pct": round(float(win_rate), 1),
            "total_trades": int(total_trades),
            "final_equity": round(float(equity), 4)
        }


class GeneticAlgorithmOptimizer:
    """
    Genetic Algorithm Parameter Optimizer.
    Evolves candidate chromosomes across multiple generations
    to maximize risk-adjusted objective on historical training sets.
    """

    def __init__(
        self,
        population_size: int = 35,
        generations: int = 25,
        crossover_prob: float = 0.85,
        mutation_prob: float = 0.20,
        tournament_size: int = 3,
        random_state: int = 42
    ):
        self.population_size = population_size
        self.generations = generations
        self.crossover_prob = crossover_prob
        self.mutation_prob = mutation_prob
        self.tournament_size = tournament_size
        self.random_state = random_state
        random.seed(random_state)
        np.random.seed(random_state)

    def _random_chromosome(self) -> Dict[str, Any]:
        """Generates a random individual within parameter boundaries."""
        chrom = {}
        for gene, (gtype, gmin, gmax, _) in GENE_BOUNDS.items():
            if gtype == int:
                chrom[gene] = random.randint(int(gmin), int(gmax))
            else:
                chrom[gene] = round(random.uniform(float(gmin), float(gmax)), 3)
        return chrom

    def _crossover(self, parent1: Dict[str, Any], parent2: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Uniform crossover between two parent chromosomes."""
        child1 = {}
        child2 = {}
        for gene in GENE_BOUNDS.keys():
            if random.random() < 0.5:
                child1[gene] = parent1[gene]
                child2[gene] = parent2[gene]
            else:
                child1[gene] = parent2[gene]
                child2[gene] = parent1[gene]
        return child1, child2

    def _mutate(self, chromosome: Dict[str, Any]) -> Dict[str, Any]:
        """Mutates individual genes with boundary preservation."""
        mutated = chromosome.copy()
        for gene, (gtype, gmin, gmax, _) in GENE_BOUNDS.items():
            if random.random() < self.mutation_prob:
                if gtype == int:
                    delta = random.choice([-2, -1, 1, 2])
                    mutated[gene] = int(np.clip(mutated[gene] + delta, gmin, gmax))
                else:
                    delta = random.uniform(-0.02, 0.02)
                    mutated[gene] = round(float(np.clip(mutated[gene] + delta, gmin, gmax)), 3)
        return mutated

    def optimize(
        self,
        train_df: pd.DataFrame,
        train_regimes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Runs GA evolution exclusively on the Training dataset.
        Returns optimized parameters, convergence curve, and baseline comparison.
        """
        # Baseline Evaluation
        baseline_metrics = FastStrategyBacktester.run_backtest(train_df, BASELINE_PARAMS, train_regimes)

        # Initialize Population
        population = [self._random_chromosome() for _ in range(self.population_size)]
        # Seed the baseline as one of the individuals
        population[0] = BASELINE_PARAMS.copy()

        fitness_history = []
        best_chromosome = None
        best_fitness = -1e9
        best_metrics = None

        for gen in range(self.generations):
            # Evaluate fitness of all individuals
            evaluated = []
            for ind in population:
                m = FastStrategyBacktester.run_backtest(train_df, ind, train_regimes)
                fit = m["fitness"]
                evaluated.append((fit, ind, m))

            # Sort descending by fitness
            evaluated.sort(key=lambda x: x[0], reverse=True)

            gen_best_fit = evaluated[0][0]
            gen_best_ind = evaluated[0][1]
            gen_best_m = evaluated[0][2]
            avg_fit = np.mean([e[0] for e in evaluated])

            if gen_best_fit > best_fitness:
                best_fitness = gen_best_fit
                best_chromosome = gen_best_ind.copy()
                best_metrics = gen_best_m.copy()

            fitness_history.append({
                "generation": gen + 1,
                "best_fitness": round(float(gen_best_fit), 4),
                "avg_fitness": round(float(avg_fit), 4),
                "best_sharpe": round(float(gen_best_m["sharpe_ratio"]), 3),
                "best_return_pct": round(float(gen_best_m["total_return_pct"]), 2)
            })

            # Elitism: retain top 2 fittest
            new_population = [evaluated[0][1], evaluated[1][1]]

            # Reproduction
            while len(new_population) < self.population_size:
                # Tournament Selection
                t1 = random.sample(evaluated, self.tournament_size)
                p1 = max(t1, key=lambda x: x[0])[1]
                t2 = random.sample(evaluated, self.tournament_size)
                p2 = max(t2, key=lambda x: x[0])[1]

                # Crossover
                if random.random() < self.crossover_prob:
                    c1, c2 = self._crossover(p1, p2)
                else:
                    c1, c2 = p1.copy(), p2.copy()

                # Mutation
                c1 = self._mutate(c1)
                c2 = self._mutate(c2)

                new_population.append(c1)
                if len(new_population) < self.population_size:
                    new_population.append(c2)

            population = new_population

        return {
            "optimized_parameters": best_chromosome,
            "baseline_parameters": BASELINE_PARAMS,
            "in_sample_optimized_metrics": best_metrics,
            "in_sample_baseline_metrics": baseline_metrics,
            "fitness_history": fitness_history,
            "generations_completed": self.generations,
            "population_size": self.population_size
        }
