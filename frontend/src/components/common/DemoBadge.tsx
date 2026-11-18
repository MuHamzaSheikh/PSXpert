import React from 'react';
import { Sparkles } from 'lucide-react';

interface DemoBadgeProps {
  label?: string;
  className?: string;
  tooltip?: string;
}

export const DemoBadge: React.FC<DemoBadgeProps> = ({
  label = 'Demo Data',
  className = '',
  tooltip = 'This feature uses simulated research models while the backend agent pipeline is in active training.'
}) => {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold tracking-wide bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 select-none ${className}`}
      title={tooltip}
    >
      <Sparkles className="w-3 h-3 animate-pulse" />
      <span>{label}</span>
    </span>
  );
};
