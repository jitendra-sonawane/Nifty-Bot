import React from 'react';

type BadgeVariant = 'buy_ce' | 'buy_pe' | 'hold' | 'waiting' | 'profit' | 'loss' | 'info' | 'warning' | 'neutral' | 'paper' | 'real';

interface BadgeProps {
    variant: BadgeVariant;
    children: React.ReactNode;
    size?: 'sm' | 'md';
    dot?: boolean;
    className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
    buy_ce: 'bg-[rgba(34,197,94,0.12)] text-[var(--color-profit-text)] border-[rgba(34,197,94,0.25)]',
    buy_pe: 'bg-[rgba(239,68,68,0.12)] text-[var(--color-loss-text)] border-[rgba(239,68,68,0.25)]',
    hold: 'bg-[rgba(107,114,128,0.12)] text-[var(--text-secondary)] border-[rgba(107,114,128,0.25)]',
    waiting: 'bg-[rgba(6,182,212,0.12)] text-[#22d3ee] border-[rgba(6,182,212,0.25)]',
    profit: 'bg-[rgba(34,197,94,0.12)] text-[var(--color-profit-text)] border-[rgba(34,197,94,0.25)]',
    loss: 'bg-[rgba(239,68,68,0.12)] text-[var(--color-loss-text)] border-[rgba(239,68,68,0.25)]',
    info: 'bg-[rgba(59,130,246,0.12)] text-[#60a5fa] border-[rgba(59,130,246,0.25)]',
    warning: 'bg-[rgba(245,158,11,0.12)] text-[#fbbf24] border-[rgba(245,158,11,0.25)]',
    neutral: 'bg-[var(--bg-overlay)] text-[var(--text-secondary)] border-[var(--border-default)]',
    paper: 'bg-[rgba(59,130,246,0.12)] text-[#60a5fa] border-[rgba(59,130,246,0.3)]',
    real: 'bg-[rgba(239,68,68,0.12)] text-[var(--color-loss-text)] border-[rgba(239,68,68,0.3)]',
};

const Badge: React.FC<BadgeProps> = ({ variant, children, size = 'sm', dot = false, className = '' }) => {
    return (
        <span
            className={`
        inline-flex items-center gap-1.5 border font-semibold rounded-full whitespace-nowrap
        ${size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-[11px]'}
        ${variantStyles[variant]}
        ${className}
      `}
        >
            {dot && (
                <span
                    className={`w-1.5 h-1.5 rounded-full ${variant === 'buy_ce' || variant === 'profit' ? 'bg-[var(--color-profit)]' :
                            variant === 'buy_pe' || variant === 'loss' || variant === 'real' ? 'bg-[var(--color-loss)]' :
                                variant === 'warning' ? 'bg-[var(--color-warning)]' :
                                    variant === 'waiting' ? 'bg-[var(--accent-cyan)]' :
                                        'bg-[var(--text-tertiary)]'
                        }`}
                />
            )}
            {children}
        </span>
    );
};

export function getSignalVariant(signal: string): BadgeVariant {
    if (signal?.includes('BUY_CE')) return 'buy_ce';
    if (signal?.includes('BUY_PE')) return 'buy_pe';
    if (signal?.includes('SELL')) return 'loss';
    if (signal === 'HOLD') return 'hold';
    return 'waiting';
}

export default Badge;
