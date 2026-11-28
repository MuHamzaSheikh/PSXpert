import React from 'react';
import { cn } from '@/utils/cn';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  elevated?: boolean;
  frosted?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  elevated = false,
  frosted = true,
  ...props
}) => {
  return (
    <div
      className={cn(
        "rounded-2xl transition-all duration-200 border border-[#DDD5C9]/85 dark:border-[#DDD5C9]/20 relative overflow-hidden",
        elevated
          ? "bg-[#FFFCF6]/88 dark:bg-[#1C2022]/88 shadow-[0_12px_36px_-6px_rgba(105,78,122,0.08),0_4px_12px_-2px_rgba(37,42,43,0.04)] backdrop-blur-xl"
          : "bg-[#FFFCF6]/75 dark:bg-[#1C2022]/75 shadow-[0_10px_30px_-5px_rgba(105,78,122,0.05),0_4px_12px_-2px_rgba(37,42,43,0.03)] backdrop-blur-lg",
        className
      )}
      {...props}
    >
      {/* Top subtle specular reflection line */}
      <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-white/80 dark:via-white/15 to-transparent pointer-events-none" />
      {children}
    </div>
  );
};
