import React, { useState, useEffect } from 'react';
import { Card } from '@/components/common/Card';
import { DemoBadge } from '@/components/common/DemoBadge';
import { api } from '@/api/client';
import { NewsArticle } from '@/types';
import { MOCK_ANNOUNCEMENTS } from '@/api/mockData';
import {
  FileText,
  Newspaper,
  Tag,
  ExternalLink,
  Search,
  Filter,
  Brain,
  Calendar,
  Award,
  ChevronRight,
  TrendingUp,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const CATEGORIES = [
  { id: 'ALL', label: 'All Research & News' },
  { id: 'BANKING', label: 'Banking & Credit' },
  { id: 'MACRO_IMF', label: 'Macro & IMF' },
  { id: 'ENERGY_OIL', label: 'Energy & Oil' },
  { id: 'TECH_AI', label: 'Technology & Exports' },
  { id: 'CEMENT', label: 'Cement & Infrastructure' },
  { id: 'CORPORATE', label: 'Corporate & Earnings' },
];

export const ResearchInsightsPage: React.FC = () => {
  const navigate = useNavigate();
  const [activeCategory, setActiveCategory] = useState('ALL');
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    async function loadNews() {
      setLoading(true);
      try {
        const res = await api.getLatestSentiment(activeCategory, undefined, 40);
        setNews(res.data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadNews();
  }, [activeCategory]);

  const filteredNews = news.filter(item => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toUpperCase();
    return item.headline.toUpperCase().includes(q) || item.summary.toUpperCase().includes(q);
  });

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* 1. Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-fg">
              Research & Market Insights
            </h1>
            <DemoBadge label="FinBERT Transformer Feed" />
          </div>
          <p className="text-xs sm:text-sm text-fg-muted mt-1">
            Curated intelligence from Dawn Business, Business Recorder, and official PSX exchange regulatory filings.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs text-fg-subtle">
          <Brain className="w-4 h-4 text-brand-600 dark:text-brand-400" />
          <span>FinBERT Accuracy: 86.0% (Macro F1: 0.855)</span>
        </div>
      </div>

      {/* 2. Category Filter Chips & Search Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        {/* Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
          {CATEGORIES.map(cat => (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={`px-3 py-1.5 rounded-full font-semibold whitespace-nowrap border transition-colors ${
                activeCategory === cat.id
                  ? 'bg-brand-500 text-white border-brand-500 shadow-sm'
                  : 'bg-bg-card border-border text-fg-muted hover:border-fg-subtle'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative max-w-xs w-full">
          <Search className="w-4 h-4 text-fg-subtle absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search headlines or summaries..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded-xl border border-border bg-bg text-xs text-fg placeholder:text-fg-subtle outline-none focus:border-brand-500"
          />
        </div>
      </div>

      {/* 3. News Articles Feed */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredNews.map(item => {
          const isPos = item.sentiment_label === 'POSITIVE';
          const isNeg = item.sentiment_label === 'NEGATIVE';
          const badgeClass = isPos
            ? 'bg-bull-bg text-bull border-bull/30'
            : isNeg
            ? 'bg-bear-bg text-bear border-bear/30'
            : 'bg-amber-500/10 text-amber-500 border-amber-500/20';

          return (
            <Card
              key={item.article_id}
              className="p-5 flex flex-col justify-between space-y-3 hover:border-brand-500/50 hover:shadow-card transition-all"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-fg-muted">{item.publisher}</span>
                    <span className="text-fg-subtle">•</span>
                    <span className="text-fg-subtle text-[11px]">
                      {new Date(item.published_at).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </span>
                  </div>

                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${badgeClass}`}>
                    {item.sentiment_label} ({Math.round(item.confidence * 100)}%)
                  </span>
                </div>

                <h3 className="font-bold text-sm sm:text-base text-fg leading-snug">
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    className="hover:text-brand-600 dark:hover:text-brand-400 transition-colors flex items-center justify-between gap-2"
                  >
                    <span>{item.headline}</span>
                    <ExternalLink className="w-3.5 h-3.5 text-fg-subtle flex-shrink-0" />
                  </a>
                </h3>

                {item.summary && (
                  <p className="text-xs text-fg-muted line-clamp-3 leading-relaxed">
                    {item.summary}
                  </p>
                )}
              </div>

              {/* Impact Analysis Quote */}
              {item.impact_analysis && (
                <div className="p-2.5 rounded-lg bg-bg-elevated/60 border border-border/80 text-[11px] text-fg-muted italic">
                  &ldquo;{item.impact_analysis}&rdquo;
                </div>
              )}

              {/* Bottom Tags */}
              <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-border/50 text-xs">
                <div className="flex flex-wrap items-center gap-1.5">
                  {item.impacted_stocks?.map(sym => (
                    <button
                      key={sym}
                      onClick={() => navigate(`/analysis/${sym}`)}
                      className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20 hover:bg-brand-500 hover:text-white transition-colors"
                    >
                      {sym}
                    </button>
                  ))}
                </div>

                <button
                  onClick={() => navigate(`/analysis/${item.impacted_stocks?.[0] || 'KSE100'}`)}
                  className="text-xs font-semibold text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1"
                >
                  <span>Analyze Stock</span>
                  <ChevronRight className="w-3 h-3" />
                </button>
              </div>
            </Card>
          );
        })}
      </div>

      {/* 4. Corporate Announcements Section */}
      <div id="announcements" className="pt-6">
        <div className="mb-4">
          <h2 className="text-xl font-bold tracking-tight text-fg">
            Exchange Filings, Payouts & Regulatory Disclosures
          </h2>
          <p className="text-xs text-fg-muted">
            Official PSX exchange documents with direct PDF source verification.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {MOCK_ANNOUNCEMENTS.map(ann => (
            <Card
              key={ann.id}
              className="p-5 flex flex-col justify-between space-y-3"
            >
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-xs px-2 py-0.5 rounded bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20">
                      {ann.symbol}
                    </span>
                    <span className="text-xs text-fg-subtle">{ann.company_name}</span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-bull-bg text-bull border border-bull/30">
                    {ann.category}
                  </span>
                </div>

                <h3 className="font-bold text-xs sm:text-sm text-fg leading-snug">
                  {ann.title}
                </h3>
              </div>

              <div className="p-2.5 rounded-lg bg-bg-elevated border border-border flex items-center justify-between text-xs">
                <span className="text-fg-subtle flex items-center gap-1">
                  <Award className="w-3.5 h-3.5 text-brand-600" />
                  <span>Action / Payout:</span>
                </span>
                <span className="font-mono font-bold text-fg">{ann.payout}</span>
              </div>

              <div className="flex items-center justify-between text-xs text-fg-subtle pt-1">
                <span>{ann.posting_date}</span>
                <a
                  href={ann.document_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-brand-600 dark:text-brand-400 hover:underline font-semibold"
                >
                  <span>Download Exchange PDF</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
};
