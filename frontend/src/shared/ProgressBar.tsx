import React from 'react';

interface ProgressBarProps {
    value: number;          // 0 to max
    max?: number;           // default 100
    color?: 'green' | 'red' | 'yellow' | 'blue' | 'purple' | 'auto';
    height?: 'sm' | 'md';
    showValue?: boolean;
    className?: string;
}

const colorMap: Record<string, string> = {
    green: 'bg-[var(--color-profit)]',
    red: 'bg-[var(--color-loss)]',
    yellow: 'bg-[var(--color-warning)]',
    blue: 'bg-[var(--accent-blue)]',
    purple: 'bg-[var(--accent-purple)]',
};

const ProgressBar: React.FC<ProgressBarProps> = ({
    value,
    max = 100,
    color = 'blue',
    height = 'sm',
    showValue = false,
    className = '',
}) => {
    const pct = Math.min(Math.max((value / max) * 100, 0), 100);

    const getAutoColor = () => {
        if (pct >= 70) return colorMap.green;
        if (pct >= 40) return colorMap.yellow;
        return colorMap.red;
    };

    const barColor = color === 'auto' ? getAutoColor() : colorMap[color];
    const heightClass = height === 'sm' ? 'h-1' : 'h-1.5';

    return (
        <div className={`flex items-center gap-2 ${className}`}>
            <div className={`flex-1 ${heightClass} rounded-full bg-[var(--bg-overlay)] overflow-hidden`}>
                <div
                    className={`${heightClass} rounded-full transition-all duration-500 ease-out ${barColor}`}
                    style={{ width: `${pct}%` }}
                />
            </div>
            {showValue && (
                <span className="text-[10px] mono text-[var(--text-tertiary)] min-w-[2rem] text-right">
                    {value.toFixed(0)}%
                </span>
            )}
        </div>
    );
};

export default ProgressBar;
