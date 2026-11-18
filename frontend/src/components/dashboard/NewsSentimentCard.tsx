import React from 'react';
import { Card } from '@/components/common/Card';
import { Newspaper, ExternalLink, ArrowRight, Brain, Tag } from 'lucide-react';
import { NewsArticle } from '@/types';
import { useNavigate } from 'react-router-dom';

interface NewsSentimentCardProps {
  news: NewsArticle[];
}

export const NewsSentimentCard: React.FC<NewsSentimentCardProps> = ({ news = [] }) => {
  const navigate = useNavigate();

  return (
    <Card className="p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <Newspaper className="w-4 h-4 text-brand-600 dark:text-brand-400" />
          <span className="font-semibold text-sm text-fg">FinBERT AI Financial News Feed</span>
        </div>
        <button
          onClick={() => navigate('/insights')}
          className="text-xs font-semibold text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1"
        >
          <span>All Scored News</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="space-y-3">
        {news.slice(0, 4).map(item => {
          const isPos = item.sentiment_label === 'POSITIVE';
          const isNeg = item.sentiment_label === 'NEGATIVE';
          const badgeClass = isPos
            ? 'bg-bull-bg text-bull border-bull/30'
            : isNeg
            ? 'bg-bear-bg text-bear border-bear/30'
            : 'bg-amber-500/10 text-amber-500 border-amber-500/20';

          return (
            <div
              key={item.article_id}
              className="p-3.5 rounded-xl border border-border bg-bg-elevated/30 hover:bg-bg-elevated/70 transition-colors space-y-2"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-fg-muted">{item.publisher}</span>
                  <span className="text-fg-subtle">•</span>
                  <span className="text-fg-subtle text-[11px]">
                    {new Date(item.published_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[10px] px-2 py-0.5 rounded bg-bg-card border border-border text-fg-subtle">
                    {item.category_badge}
                  </span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${badgeClass}`}>
                    {item.sentiment_label} ({Math.round(item.confidence * 100)}%)
                  </span>
                </div>
              </div>

              <h4 className="font-semibold text-xs sm:text-sm text-fg leading-snug">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
                >
                  {item.headline}
                </a>
              </h4>

              {item.summary && (
                <p className="text-xs text-fg-muted line-clamp-2 leading-relaxed">
                  {item.summary}
                </p>
              )}

              {/* Impacted Stocks Tags */}
              {item.impacted_stocks && item.impacted_stocks.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                  <span className="text-[10px] text-fg-subtle font-medium flex items-center gap-1">
                    <Tag className="w-3 h-3 text-brand-600" />
                    <span>Impacted:</span>
                  </span>
                  {item.impacted_stocks.map(sym => (
                    <button
                      key={sym}
                      onClick={() => navigate(`/analysis/${sym}`)}
                      className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20 hover:bg-brand-500 hover:text-white transition-colors"
                    >
                      {sym}
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
};
