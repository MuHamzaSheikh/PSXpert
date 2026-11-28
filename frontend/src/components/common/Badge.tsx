import React from 'react';
import { cn } from '@/utils/cn';

interface BadgeProps {
  variant?: 'bull' | 'bear' | 'neutral' | 'brand' | 'subtle' | 'plum' | 'jade' | 'copper';
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
  const base = "inline-flex items-center gap-1 font-semibold rounded-full tracking-wide select-none transition-colors";
  
  const sizeStyles = {
    sm: "text-[11px] px-2 py-0.5",
    md: "text-xs px-2.5 py-1",
  };

  const variantStyles = {
    bull: "bg-[#287A50]/12 text-[#287A50] dark:text-[#34A86E] border border-[#287A50]/25",
    bear: "bg-[#C64C4C]/12 text-[#C64C4C] dark:text-[#E05C5C] border border-[#C64C4C]/25",
    neutral: "bg-[#B88732]/14 text-[#B88732] dark:text-[#D9A03B] border border-[#B88732]/28",
    brand: "bg-[#2F7D68]/12 text-[#2F7D68] dark:text-[#3DA88D] border border-[#2F7D68]/25",
    plum: "bg-[#694E7A]/12 text-[#694E7A] dark:text-[#A888BF] border border-[#694E7A]/25",
    jade: "bg-[#2F7D68]/12 text-[#2F7D68] dark:text-[#3DA88D] border border-[#2F7D68]/25",
    copper: "bg-[#C47C4F]/14 text-[#C47C4F] dark:text-[#DB8C5A] border border-[#C47C4F]/30",
    subtle: "bg-[#E7E0D5]/50 dark:bg-[#252A2C]/60 text-[#77736C] dark:text-[#9E988E] border border-[#DDD5C9]/70 dark:border-[#DDD5C9]/15",
  };

  return (
    <span className={cn(base, sizeStyles[size], variantStyles[variant], className)}>
      {children}
    </span>
  );
};
