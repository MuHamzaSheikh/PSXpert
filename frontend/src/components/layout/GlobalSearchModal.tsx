import React, { useEffect, useState, useRef } from 'react';
import { Search, X, TrendingUp, Building2, Layers, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/api/client';
import { Company } from '@/types';

interface GlobalSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const GlobalSearchModal: React.FC<GlobalSearchModalProps> = ({ isOpen, onClose }) => {
  const [query, setQuery] = useState('');
  const [stocks, setStocks] = useState<Company[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      api.getStocks(undefined, undefined, 600).then(res => setStocks(res.data));
      api.getSectors().then(res => setSectors(res.data));
    } else {
      setQuery('');
      setSelectedIndex(0);
    }
  }, [isOpen]);

  // Keyboard shortcut listener for Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (isOpen) onClose();
        else {
          // Trigger open if parent passes listener
        }
      }
      if (isOpen && e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const filteredStocks = query.trim() === ''
    ? stocks.slice(0, 8)
    : stocks.filter(s =>
        s.symbol.toUpperCase().includes(query.toUpperCase()) ||
        s.company_name.toUpperCase().includes(query.toUpperCase())
      ).slice(0, 16);

  const filteredSectors = query.trim() === ''
    ? []
    : sectors.filter(sec => sec.toUpperCase().includes(query.toUpperCase())).slice(0, 4);

  const totalResults = filteredStocks.length + filteredSectors.length;

  const handleSelect = (symbol: string) => {
    onClose();
    navigate(`/analysis/${symbol}`);
  };

  const handleKeyDownInList = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => (prev + 1) % Math.max(1, totalResults));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => (prev - 1 + totalResults) % Math.max(1, totalResults));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedIndex < filteredStocks.length) {
        handleSelect(filteredStocks[selectedIndex].symbol);
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 px-4 bg-black/45 backdrop-blur-md animate-in fade-in duration-150">
      <div
        className="relative w-full max-w-2xl bg-[#FFFCF6]/95 dark:bg-[#1C2022]/95 border border-[#DDD5C9] dark:border-[#DDD5C9]/25 rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[80vh] backdrop-blur-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="flex items-center px-4 py-3.5 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 bg-[#E7E0D5]/30 dark:bg-[#252A2C]/40">
          <Search className="w-5 h-5 text-[#2F7D68] mr-3 flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            className="w-full bg-transparent text-[#252A2B] dark:text-[#F4EFE6] placeholder:text-[#77736C] text-sm sm:text-base outline-none"
            placeholder="Search PSX stocks, sectors, or indices (e.g. OGDC, MEBL, Cement)..."
            value={query}
            onChange={e => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDownInList}
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="p-1 text-fg-subtle hover:text-fg rounded"
            >
              <X className="w-4 h-4" />
            </button>
          )}
          <kbd className="hidden sm:inline-flex items-center gap-1 ml-2 px-2 py-0.5 text-[11px] font-mono text-fg-subtle bg-bg-card border border-border rounded">
            ESC
          </kbd>
        </div>

        {/* Quick Suggestion Chips */}
        {query === '' && (
          <div className="px-4 py-2.5 border-b border-border bg-bg-subtle/30 flex items-center gap-2 overflow-x-auto text-xs">
            <span className="text-fg-muted font-medium flex-shrink-0">Popular:</span>
            {['KSE100', 'MEBL', 'OGDC', 'SYS', 'LUCK', 'HUBC', 'FFC'].map(sym => (
              <button
                key={sym}
                onClick={() => handleSelect(sym)}
                className="px-2.5 py-1 rounded-lg bg-bg-card border border-border hover:border-brand-500 hover:text-brand-600 dark:hover:text-brand-400 font-mono text-fg-muted transition-colors flex-shrink-0"
              >
                {sym}
              </button>
            ))}
          </div>
        )}

        {/* Results List */}
        <div className="overflow-y-auto p-2 divide-y divide-border/50">
          {/* Stocks Section */}
          {filteredStocks.length > 0 && (
            <div className="py-1">
              <div className="px-3 py-1.5 text-[11px] font-semibold text-fg-subtle uppercase tracking-wider flex items-center gap-1.5">
                <TrendingUp className="w-3.5 h-3.5" />
                <span>Listed Equities</span>
              </div>
              {filteredStocks.map((stock, i) => {
                const isSelected = i === selectedIndex;
                const isPositive = (stock.pct_change || 0) >= 0;
                return (
                  <div
                    key={stock.symbol}
                    onClick={() => handleSelect(stock.symbol)}
                    className={`flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-colors ${
                      isSelected ? 'bg-brand-500/10 border-brand-500/30 text-fg' : 'hover:bg-bg-elevated text-fg-muted hover:text-fg'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center font-mono font-bold text-xs text-brand-600 dark:text-brand-400">
                        {stock.symbol.slice(0, 3)}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-fg text-sm">{stock.symbol}</span>
                          {stock.is_shariah && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 font-medium">
                              Islamic
                            </span>
                          )}
                          {stock.is_kse100 && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20 font-medium">
                              KSE-100
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-fg-subtle line-clamp-1">{stock.company_name} • {stock.sector}</div>
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="font-mono font-semibold text-sm text-fg">
                        PKR {stock.close ? stock.close.toFixed(2) : '--'}
                      </div>
                      {stock.pct_change !== undefined && (
                        <div className={`font-mono text-xs font-medium ${isPositive ? 'text-bull' : 'text-bear'}`}>
                          {isPositive ? '+' : ''}{stock.pct_change.toFixed(2)}%
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Sectors Section */}
          {filteredSectors.length > 0 && (
            <div className="py-1">
              <div className="px-3 py-1.5 text-[11px] font-semibold text-fg-subtle uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5" />
                <span>Industry Sectors</span>
              </div>
              {filteredSectors.map((sec, i) => (
                <div
                  key={sec}
                  onClick={() => {
                    onClose();
                    navigate(`/screener?sector=${encodeURIComponent(sec)}`);
                  }}
                  className="flex items-center justify-between px-3 py-2 rounded-xl cursor-pointer hover:bg-bg-elevated text-fg-muted hover:text-fg text-sm"
                >
                  <div className="flex items-center gap-2.5">
                    <Building2 className="w-4 h-4 text-brand-600 dark:text-brand-400" />
                    <span>{sec}</span>
                  </div>
                  <ArrowRight className="w-4 h-4 text-fg-subtle" />
                </div>
              ))}
            </div>
          )}

          {query && filteredStocks.length === 0 && filteredSectors.length === 0 && (
            <div className="py-12 text-center text-fg-muted text-sm">
              <p>No PSX stocks or sectors found matching &ldquo;{query}&rdquo;</p>
              <p className="text-xs text-fg-subtle mt-1">Try searching by ticker (e.g. MEBL, SYS) or sector name</p>
            </div>
          )}
        </div>

        {/* Modal Footer Key Shortcuts */}
        <div className="px-4 py-2.5 border-t border-border bg-bg-elevated/40 text-[11px] text-fg-subtle flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span><kbd className="px-1.5 py-0.5 rounded bg-bg-card border border-border">↑</kbd> <kbd className="px-1.5 py-0.5 rounded bg-bg-card border border-border">↓</kbd> to navigate</span>
            <span><kbd className="px-1.5 py-0.5 rounded bg-bg-card border border-border">↵</kbd> to select</span>
          </div>
          <span>PSX Multi-Asset Search</span>
        </div>
      </div>
    </div>
  );
};
