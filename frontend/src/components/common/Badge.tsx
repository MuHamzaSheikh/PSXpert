import React from 'react';
import { cn } from '@/utils/cn';

interface BadgeProps {
  variant?: 'bull' | 'bear' | 'neutral' | 'brand' | 'subtle';
  size?: 'sm' | 'md';
  children: React.ReactNode;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'subtle',
  size = 'sm',
  children,
  className = '',
}) => {
  const base = "inline-flex items-center gap-1 font-semibold rounded-full tracking-wide select-none";
  
  const sizeStyles = {
    sm: "text-[11px] px-2 py-0.5",
    md: "text-xs px-2.5 py-1",
  };

  const variantStyles = {
    bull: "bg-bull-bg text-bull border border-bull/30",
    bear: "bg-bear-bg text-bear border border-bear/30",
    neutral: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20",
    brand: "bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20",
    subtle: "bg-bg-subtle text-fg-muted border border-border",
  };

  return (
    <span className={cn(base, sizeStyles[size], variantStyles[variant], className)}>
      {children}
    </span>
  );
};
