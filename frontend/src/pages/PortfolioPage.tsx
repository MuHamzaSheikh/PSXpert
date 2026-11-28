import React, { useState, useEffect } from 'react';
import { Card } from '@/components/common/Card';
import { DemoBadge } from '@/components/common/DemoBadge';
import { PortfolioHolding, PortfolioSummary, PortfolioTrade } from '@/types';
import {
  Briefcase,
  TrendingUp,
  TrendingDown,
  Plus,
  Trash2,
  DollarSign,
  PieChart,
  ShieldAlert,
  ArrowUpRight,
  ArrowDownRight,
  X,
  CheckCircle,
} from 'lucide-react';

const INITIAL_HOLDINGS: PortfolioHolding[] = [
  {
    id: 'hold_1',
    symbol: 'MEBL',
    company_name: 'Meezan Bank Ltd',
    sector: 'Commercial Banks',
    shares: 2500,
    avg_buy_price: 215.40,
    current_price: 248.50,
    total_cost: 538500,
    current_value: 621250,
    unrealized_pnl: 82750,
    unrealized_pnl_pct: 15.37,
    portfolio_weight_pct: 38.5,
  },
  {
    id: 'hold_2',
    symbol: 'OGDC',
    company_name: 'Oil & Gas Development Co',
    sector: 'Oil & Gas Exploration Companies',
    shares: 1800,
    avg_buy_price: 202.10,
    current_price: 212.72,
    total_cost: 363780,
    current_value: 382896,
    unrealized_pnl: 19116,
    unrealized_pnl_pct: 5.25,
    portfolio_weight_pct: 23.7,
  },
  {
    id: 'hold_3',
    symbol: 'SYS',
    company_name: 'Systems Ltd',
    sector: 'Technology & Communication',
    shares: 800,
    avg_buy_price: 395.00,
    current_price: 411.58,
    total_cost: 316000,
    current_value: 329264,
    unrealized_pnl: 13264,
    unrealized_pnl_pct: 4.20,
    portfolio_weight_pct: 20.4,
  },
  {
    id: 'hold_4',
    symbol: 'HUBC',
    company_name: 'Hub Power Company Ltd',
    sector: 'Power Generation & Distribution',
    shares: 1400,
    avg_buy_price: 209.50,
    current_price: 206.05,
    total_cost: 293300,
    current_value: 288470,
    unrealized_pnl: -4830,
    unrealized_pnl_pct: -1.65,
    portfolio_weight_pct: 17.4,
  },
];

export const PortfolioPage: React.FC = () => {
  const [holdings, setHoldings] = useState<PortfolioHolding[]>(() => {
    try {
      const saved = localStorage.getItem('psxpert_portfolio_holdings');
      return saved ? JSON.parse(saved) : INITIAL_HOLDINGS;
    } catch {
      return INITIAL_HOLDINGS;
    }
  });

  const [isTradeModalOpen, setIsTradeModalOpen] = useState(false);
  const [tradeSymbol, setTradeSymbol] = useState('MEBL');
  const [tradeType, setTradeType] = useState<'BUY' | 'SELL'>('BUY');
  const [tradeShares, setTradeShares] = useState(100);
  const [tradePrice, setTradePrice] = useState(248.50);

  // Sync to LocalStorage
  useEffect(() => {
    localStorage.setItem('psxpert_portfolio_holdings', JSON.stringify(holdings));
  }, [holdings]);

  // Aggregate portfolio totals
  const totalValue = holdings.reduce((sum, h) => sum + h.current_value, 0);
  const totalCost = holdings.reduce((sum, h) => sum + h.total_cost, 0);
  const totalUnrealizedPnl = totalValue - totalCost;
  const totalUnrealizedPnlPct = totalCost > 0 ? (totalUnrealizedPnl / totalCost) * 100 : 0;
  const cashBalance = 350000; // Simulated cash balance

  const handleAddTrade = (e: React.FormEvent) => {
    e.preventDefault();
    const sym = tradeSymbol.toUpperCase();
    const existingIndex = holdings.findIndex(h => h.symbol === sym);

    if (tradeType === 'BUY') {
      if (existingIndex >= 0) {
        const existing = holdings[existingIndex];
        const newShares = existing.shares + Number(tradeShares);
        const newTotalCost = existing.total_cost + (Number(tradeShares) * Number(tradePrice));
        const newAvgPrice = newTotalCost / newShares;
        const newCurrentValue = newShares * existing.current_price;

        const updated = [...holdings];
        updated[existingIndex] = {
          ...existing,
          shares: newShares,
          avg_buy_price: Math.round(newAvgPrice * 100) / 100,
          total_cost: Math.round(newTotalCost),
          current_value: Math.round(newCurrentValue),
          unrealized_pnl: Math.round(newCurrentValue - newTotalCost),
          unrealized_pnl_pct: Math.round(((newCurrentValue - newTotalCost) / newTotalCost) * 10000) / 100,
        };
        setHoldings(updated);
      } else {
        const newHolding: PortfolioHolding = {
          id: `hold_${Date.now()}`,
          symbol: sym,
          company_name: `${sym} Pakistan Listed`,
          sector: 'Equities',
          shares: Number(tradeShares),
          avg_buy_price: Number(tradePrice),
          current_price: Number(tradePrice),
          total_cost: Number(tradeShares) * Number(tradePrice),
          current_value: Number(tradeShares) * Number(tradePrice),
          unrealized_pnl: 0,
          unrealized_pnl_pct: 0,
          portfolio_weight_pct: 10,
        };
        setHoldings([...holdings, newHolding]);
      }
    } else {
      // Sell action
      if (existingIndex >= 0) {
        const existing = holdings[existingIndex];
        const newShares = Math.max(0, existing.shares - Number(tradeShares));
        if (newShares === 0) {
          setHoldings(holdings.filter(h => h.symbol !== sym));
        } else {
          const updated = [...holdings];
          const newCost = newShares * existing.avg_buy_price;
          const newVal = newShares * existing.current_price;
          updated[existingIndex] = {
            ...existing,
            shares: newShares,
            total_cost: Math.round(newCost),
            current_value: Math.round(newVal),
            unrealized_pnl: Math.round(newVal - newCost),
            unrealized_pnl_pct: Math.round(((newVal - newCost) / (newCost || 1)) * 10000) / 100,
          };
          setHoldings(updated);
        }
      }
    }
    setIsTradeModalOpen(false);
  };

  const removeHolding = (id: string) => {
    setHoldings(holdings.filter(h => h.id !== id));
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* 1. Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#252A2B] dark:text-[#F4EFE6]">
              Portfolio &amp; Risk Manager
            </h1>
            <DemoBadge label="Client LocalStore" />
          </div>
          <p className="text-xs sm:text-sm text-[#77736C] dark:text-[#9E988E] mt-1">
            Track your PSX equity holdings, asset allocation, P&amp;L performance, and daily Value at Risk (VaR).
          </p>
        </div>

        <button
          onClick={() => setIsTradeModalOpen(true)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-semibold text-white bg-gradient-to-r from-[#2F7D68] to-[#236353] hover:from-[#236353] hover:to-[#1a4d40] shadow-md shadow-[#2F7D68]/20 transition-all self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>Log New Trade</span>
        </button>
      </div>

      {/* 2. Portfolio Stats Cards Row in Frosted Glass */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 space-y-1">
          <div className="text-[11px] font-semibold text-[#77736C] dark:text-[#9E988E] uppercase tracking-wider">Total Portfolio Value</div>
          <div className="text-xl sm:text-2xl font-black font-mono text-[#252A2B] dark:text-[#F4EFE6]">
            PKR {(totalValue + cashBalance).toLocaleString()}
          </div>
          <div className="text-[11px] text-[#77736C] dark:text-[#9E988E]">
            Equities: PKR {totalValue.toLocaleString()}
          </div>
        </Card>

        <Card className="p-4 space-y-1">
          <div className="text-[11px] font-semibold text-[#77736C] dark:text-[#9E988E] uppercase tracking-wider">Unrealized Gain / Loss</div>
          <div className={`text-xl sm:text-2xl font-black font-mono ${totalUnrealizedPnl >= 0 ? 'text-[#287A50] dark:text-[#34A86E]' : 'text-[#C64C4C] dark:text-[#E05C5C]'}`}>
            {totalUnrealizedPnl >= 0 ? '+' : ''}PKR {totalUnrealizedPnl.toLocaleString()}
          </div>
          <div className={`text-xs font-mono font-bold ${totalUnrealizedPnl >= 0 ? 'text-[#287A50] dark:text-[#34A86E]' : 'text-[#C64C4C] dark:text-[#E05C5C]'}`}>
            {totalUnrealizedPnl >= 0 ? '+' : ''}{totalUnrealizedPnlPct.toFixed(2)}% Return
          </div>
        </Card>

        <Card className="p-4 space-y-1">
          <div className="text-[11px] font-semibold text-[#77736C] dark:text-[#9E988E] uppercase tracking-wider">Cash Available</div>
          <div className="text-xl sm:text-2xl font-black font-mono text-[#252A2B] dark:text-[#F4EFE6]">
            PKR {cashBalance.toLocaleString()}
          </div>
          <div className="text-[11px] text-[#77736C] dark:text-[#9E988E]">Ready for deployment</div>
        </Card>

        <Card className="p-4 space-y-1">
          <div className="text-[11px] font-semibold text-[#77736C] dark:text-[#9E988E] uppercase tracking-wider">Portfolio Beta &amp; VaR</div>
          <div className="text-xl sm:text-2xl font-black font-mono text-[#694E7A] dark:text-[#A888BF]">
            0.88 β <span className="text-xs font-sans text-[#77736C] dark:text-[#9E988E] font-normal">(Defensive)</span>
          </div>
          <div className="text-[11px] font-mono text-[#77736C] dark:text-[#9E988E]">
            1-Day 95% VaR: <strong>PKR 34,200 (2.1%)</strong>
          </div>
        </Card>
      </div>

      {/* 3. Holdings Table */}
      <Card className="p-0 overflow-hidden shadow-card">
        <div className="p-4 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Briefcase className="w-4 h-4 text-[#2F7D68]" />
            <span className="font-bold text-sm text-[#252A2B] dark:text-[#F4EFE6]">Equity Holdings ({holdings.length})</span>
          </div>
          <span className="text-xs font-mono text-[#77736C] dark:text-[#9E988E]">Real-Time PSX Valuation</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#E7E0D5]/50 dark:bg-[#1C2022]/70 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 text-[11px] font-semibold text-[#77736C] dark:text-[#9E988E] uppercase tracking-wider">
              <tr>
                <th className="py-3 px-4">Symbol</th>
                <th className="py-3 px-3 text-right">Shares</th>
                <th className="py-3 px-3 text-right">Avg Cost</th>
                <th className="py-3 px-3 text-right">Current Price</th>
                <th className="py-3 px-3 text-right">Market Value</th>
                <th className="py-3 px-3 text-right">Gain / Loss</th>
                <th className="py-3 px-3 text-center">Weight</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#DDD5C9]/40 dark:divide-[#DDD5C9]/10">
              {holdings.map(h => {
                const isGain = h.unrealized_pnl >= 0;
                const weight = totalValue > 0 ? ((h.current_value / totalValue) * 100).toFixed(1) : '0';

                return (
                  <tr key={h.id} className="hover:bg-[#FFFCF6]/80 dark:hover:bg-[#1C2022]/80 transition-colors">
                    {/* Symbol */}
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-xl bg-[#2F7D68]/15 border border-[#2F7D68]/30 flex items-center justify-center font-mono font-bold text-xs text-[#2F7D68] dark:text-[#3DA88D]">
                          {h.symbol.slice(0, 3)}
                        </div>
                        <div>
                          <span className="font-mono font-bold text-sm text-[#252A2B] dark:text-[#F4EFE6]">{h.symbol}</span>
                          <div className="text-[11px] text-[#77736C] dark:text-[#9E988E] line-clamp-1">{h.company_name}</div>
                        </div>
                      </div>
                    </td>

                    {/* Shares */}
                    <td className="py-3 px-3 text-right font-mono font-bold text-[#252A2B] dark:text-[#F4EFE6]">
                      {h.shares.toLocaleString()}
                    </td>

                    {/* Avg Cost */}
                    <td className="py-3 px-3 text-right font-mono text-[#77736C] dark:text-[#9E988E]">
                      PKR {h.avg_buy_price.toFixed(2)}
                    </td>

                    {/* Current Price */}
                    <td className="py-3 px-3 text-right font-mono font-bold text-[#252A2B] dark:text-[#F4EFE6]">
                      PKR {h.current_price.toFixed(2)}
                    </td>

                    {/* Market Value */}
                    <td className="py-3 px-3 text-right font-mono font-bold text-[#252A2B] dark:text-[#F4EFE6]">
                      PKR {h.current_value.toLocaleString()}
                    </td>

                    {/* P&L */}
                    <td className="py-3 px-3 text-right font-mono">
                      <div className={`font-bold ${isGain ? 'text-[#287A50] dark:text-[#34A86E]' : 'text-[#C64C4C] dark:text-[#E05C5C]'}`}>
                        {isGain ? '+' : ''}PKR {h.unrealized_pnl.toLocaleString()}
                      </div>
                      <div className={`text-[10px] ${isGain ? 'text-[#287A50] dark:text-[#34A86E]' : 'text-[#C64C4C] dark:text-[#E05C5C]'}`}>
                        {isGain ? '+' : ''}{h.unrealized_pnl_pct.toFixed(2)}%
                      </div>
                    </td>

                    {/* Weight */}
                    <td className="py-3 px-3 text-center">
                      <span className="font-mono text-xs text-[#77736C] dark:text-[#9E988E] px-2 py-0.5 rounded-full bg-[#E7E0D5]/60 dark:bg-[#1C2022]/80 border border-[#DDD5C9]/60 dark:border-[#DDD5C9]/20">
                        {weight}%
                      </span>
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => removeHolding(h.id)}
                        className="p-1.5 rounded-full border border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 text-[#77736C] hover:text-[#C64C4C] hover:border-[#C64C4C]/40 transition-colors"
                        title="Remove holding"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* 4. Log Trade Modal */}
      {isTradeModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-md animate-in fade-in duration-150">
          <div className="w-full max-w-md bg-[#FFFCF6]/95 dark:bg-[#1C2022]/95 border border-[#DDD5C9] dark:border-[#DDD5C9]/20 rounded-3xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-3">
              <span className="font-bold text-base text-[#252A2B] dark:text-[#F4EFE6]">Log New PSX Trade</span>
              <button
                onClick={() => setIsTradeModalOpen(false)}
                className="p-1 rounded-full text-[#77736C] hover:text-[#252A2B] dark:hover:text-[#F4EFE6]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleAddTrade} className="space-y-4 text-xs">
              {/* Type: BUY / SELL */}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setTradeType('BUY')}
                  className={`flex-1 py-2 rounded-full font-bold border transition-colors ${
                    tradeType === 'BUY'
                      ? 'bg-gradient-to-r from-[#287A50] to-[#1F5C4C] text-white border-[#287A50]'
                      : 'bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 border-[#DDD5C9] text-[#77736C]'
                  }`}
                >
                  BUY
                </button>
                <button
                  type="button"
                  onClick={() => setTradeType('SELL')}
                  className={`flex-1 py-2 rounded-full font-bold border transition-colors ${
                    tradeType === 'SELL'
                      ? 'bg-gradient-to-r from-[#C64C4C] to-[#A03838] text-white border-[#C64C4C]'
                      : 'bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 border-[#DDD5C9] text-[#77736C]'
                  }`}
                >
                  SELL
                </button>
              </div>

              {/* Symbol */}
              <div className="space-y-1">
                <label className="font-semibold text-[#252A2B] dark:text-[#F4EFE6]">Symbol Ticker</label>
                <input
                  type="text"
                  required
                  value={tradeSymbol}
                  onChange={e => setTradeSymbol(e.target.value.toUpperCase())}
                  className="w-full px-3.5 py-2 rounded-full border border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-[#252A2B] dark:text-[#F4EFE6] font-mono uppercase font-bold outline-none focus:border-[#2F7D68]"
                  placeholder="e.g. MEBL, OGDC, SYS"
                />
              </div>

              {/* Shares */}
              <div className="space-y-1">
                <label className="font-semibold text-[#252A2B] dark:text-[#F4EFE6]">Number of Shares</label>
                <input
                  type="number"
                  required
                  min={1}
                  value={tradeShares}
                  onChange={e => setTradeShares(Number(e.target.value))}
                  className="w-full px-3.5 py-2 rounded-full border border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-[#252A2B] dark:text-[#F4EFE6] font-mono font-bold outline-none focus:border-[#2F7D68]"
                />
              </div>

              {/* Execution Price */}
              <div className="space-y-1">
                <label className="font-semibold text-[#252A2B] dark:text-[#F4EFE6]">Execution Price (PKR)</label>
                <input
                  type="number"
                  step="0.05"
                  required
                  value={tradePrice}
                  onChange={e => setTradePrice(Number(e.target.value))}
                  className="w-full px-3.5 py-2 rounded-full border border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-[#252A2B] dark:text-[#F4EFE6] font-mono font-bold outline-none focus:border-[#2F7D68]"
                />
              </div>

              {/* Total Calculation */}
              <div className="p-3 rounded-2xl bg-[#E7E0D5]/40 dark:bg-[#1C2022]/60 border border-[#DDD5C9]/60 dark:border-[#DDD5C9]/20 flex items-center justify-between text-xs">
                <span className="text-[#77736C] dark:text-[#9E988E]">Total Trade Value:</span>
                <span className="font-mono font-bold text-[#252A2B] dark:text-[#F4EFE6]">
                  PKR {(tradeShares * tradePrice).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
              </div>

              <div className="flex items-center gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsTradeModalOpen(false)}
                  className="flex-1 py-2 rounded-full border border-[#DDD5C9] dark:border-[#DDD5C9]/20 text-[#77736C] hover:bg-[#E7E0D5]/50 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2 rounded-full bg-gradient-to-r from-[#2F7D68] to-[#236353] hover:from-[#236353] hover:to-[#1a4d40] text-white font-bold transition-all shadow-md shadow-[#2F7D68]/20"
                >
                  Confirm Trade
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
