import React from 'react';
import { cn } from '@/utils/cn';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  elevated?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  elevated = false,
  ...props
}) => {
  return (
    <div
      className={cn(
        "rounded-2xl border border-border transition-colors duration-150",
        elevated ? "bg-bg-elevated" : "bg-bg-card shadow-subtle",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};
