import React from 'react';
import { AlertTriangle, Info, X } from 'lucide-react';

interface DisclaimerBannerProps {
  dismissible?: boolean;
  variant?: 'compact' | 'full';
}

export const DisclaimerBanner: React.FC<DisclaimerBannerProps> = ({
  dismissible = false,
  variant = 'compact'
}) => {
  const [visible, setVisible] = React.useState(true);

  if (!visible) return null;

  if (variant === 'compact') {
    return (
      <div className="w-full bg-brand-500/10 border-b border-brand-500/20 px-4 py-2 text-xs text-fg-muted flex items-center justify-between">
        <div className="flex items-center gap-2 max-w-7xl mx-auto w-full">
          <Info className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400 flex-shrink-0" />
          <span>
            <strong>Research & Diagnostic Notice:</strong> Indicators, pattern detections, and multi-agent AI assessments are algorithmic diagnostic tools — <em>never</em> guaranteed buy/sell signals or financial advice.
          </span>
        </div>
        {dismissible && (
          <button
            onClick={() => setVisible(false)}
            className="p-1 hover:text-fg text-fg-muted"
            aria-label="Dismiss disclaimer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/5 text-xs text-fg-muted space-y-1.5">
      <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-semibold text-sm">
        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
        <span>Diagnostic Analysis & Investment Disclaimer</span>
      </div>
      <p className="leading-relaxed">
        PSXpert is an academic and research analytics platform for the Pakistan Stock Exchange (PSX). Quantitative indicators, candlestick patterns, and neural language model inferences are strictly diagnostic aids designed to identify statistical tendencies and momentum shifts. They do not constitute securities recommendations, legal advice, or financial advisory. Past market performance is no guarantee of future returns.
      </p>
    </div>
  );
};
