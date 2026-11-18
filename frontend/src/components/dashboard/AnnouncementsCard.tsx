import React from 'react';
import { Card } from '@/components/common/Card';
import { FileSpreadsheet, ExternalLink, ArrowRight, Award, Calendar, DollarSign } from 'lucide-react';
import { MOCK_ANNOUNCEMENTS } from '@/api/mockData';
import { useNavigate } from 'react-router-dom';

export const AnnouncementsCard: React.FC = () => {
  const navigate = useNavigate();

  return (
    <Card className="p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="w-4 h-4 text-brand-600 dark:text-brand-400" />
          <span className="font-semibold text-sm text-fg">Latest Company Announcements</span>
        </div>
        <button
          onClick={() => navigate('/insights#announcements')}
          className="text-xs font-semibold text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1"
        >
          <span>View All PSX Filings</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {MOCK_ANNOUNCEMENTS.map(ann => {
          const isPos = ann.sentiment === 'POSITIVE';
          return (
            <div
              key={ann.id}
              className="p-4 rounded-xl border border-border bg-bg-elevated/40 hover:bg-bg-elevated/80 transition-all flex flex-col justify-between space-y-3"
            >
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-xs px-2 py-0.5 rounded bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20">
                      {ann.symbol}
                    </span>
                    <span className="text-xs text-fg-subtle line-clamp-1">{ann.company_name}</span>
                  </div>
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
                      isPos ? 'bg-bull-bg text-bull border-bull/30' : 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                    }`}
                  >
                    {ann.sentiment}
                  </span>
                </div>

                <h3 className="font-semibold text-xs sm:text-sm text-fg line-clamp-2 leading-snug">
                  {ann.title}
                </h3>
              </div>

              {/* Structured Fact Box */}
              <div className="p-2.5 rounded-lg bg-bg-card border border-border/80 flex items-center justify-between text-xs">
                <span className="text-fg-subtle flex items-center gap-1.5">
                  <Award className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400" />
                  <span>Key Action / Metric:</span>
                </span>
                <span className="font-mono font-bold text-fg">{ann.payout}</span>
              </div>

              {/* Bottom Actions */}
              <div className="flex items-center justify-between pt-1 text-xs text-fg-subtle">
                <span className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  <span>{ann.posting_date}</span>
                </span>

                <div className="flex items-center gap-3">
                  <a
                    href={ann.document_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-brand-600 dark:text-brand-400 hover:underline font-medium"
                  >
                    <span>Official PDF</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                  <button
                    onClick={() => navigate(`/analysis/${ann.symbol}`)}
                    className="hover:text-fg font-medium"
                  >
                    Analyze
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};
