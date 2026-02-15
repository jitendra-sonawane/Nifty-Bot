import React from 'react';

interface StatusDotProps {
    active: boolean;
    size?: 'sm' | 'md';
    label?: string;
    className?: string;
}

const StatusDot: React.FC<StatusDotProps> = ({ active, size = 'sm', label, className = '' }) => {
    const dotSize = size === 'sm' ? 'w-2 h-2' : 'w-2.5 h-2.5';

    return (
        <span className={`inline-flex items-center gap-1.5 ${className}`}>
            <span className="relative flex">
                <span
                    className={`
            ${dotSize} rounded-full
            ${active ? 'bg-[var(--color-profit)]' : 'bg-[var(--color-loss)]'}
          `}
                />
                {active && (
                    <span
                        className={`
              absolute inset-0 rounded-full animate-ping opacity-40
              ${active ? 'bg-[var(--color-profit)]' : 'bg-[var(--color-loss)]'}
            `}
                    />
                )}
            </span>
            {label && (
                <span className={`text-[var(--text-secondary)] ${size === 'sm' ? 'text-[10px]' : 'text-xs'}`}>
                    {label}
                </span>
            )}
        </span>
    );
};

export default StatusDot;
