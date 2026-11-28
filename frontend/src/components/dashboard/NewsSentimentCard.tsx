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
            ? 'bg-[#287A50]/15 text-[#287A50] border-[#287A50]/25'
            : isNeg
            ? 'bg-[#C64C4C]/15 text-[#C64C4C] border-[#C64C4C]/25'
            : 'bg-[#B88732]/15 text-[#B88732] border-[#B88732]/25';

          return (
            <div
              key={item.article_id}
              className="p-3.5 rounded-2xl border border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 bg-[#FFFCF6]/60 dark:bg-[#1C2022]/60 hover:bg-[#FFFCF6] dark:hover:bg-[#1C2022] transition-colors space-y-2"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-[#77736C] dark:text-[#9E988E]">{item.publisher}</span>
                  <span className="text-[#DDD5C9]">•</span>
                  <span className="text-[#77736C] dark:text-[#9E988E] text-[11px]">
                    {new Date(item.published_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-[#E7E0D5]/50 dark:bg-[#252A2C] border border-[#DDD5C9]/60 text-[#77736C] dark:text-[#9E988E]">
                    {item.category_badge}
                  </span>
                  <span className={`text-[10px] px-2.5 py-0.5 rounded-full font-bold border ${badgeClass}`}>
                    {item.sentiment_label} ({Math.round(item.confidence * 100)}%)
                  </span>
                </div>
              </div>

              <h4 className="font-semibold text-xs sm:text-sm text-[#252A2B] dark:text-[#F4EFE6] leading-snug">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-[#2F7D68] dark:hover:text-[#3DA88D] transition-colors"
                >
                  {item.headline}
                </a>
              </h4>

              {item.summary && (
                <p className="text-xs text-[#77736C] dark:text-[#9E988E] line-clamp-2 leading-relaxed">
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
