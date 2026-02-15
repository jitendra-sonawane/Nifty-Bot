import React from 'react';

interface CardProps {
    children: React.ReactNode;
    className?: string;
    compact?: boolean;
    glow?: 'blue' | 'purple' | 'profit' | 'none';
    header?: React.ReactNode;
    onClick?: () => void;
    style?: React.CSSProperties;
}

const Card: React.FC<CardProps> = ({
    children,
    className = '',
    compact = false,
    glow = 'none',
    header,
    onClick,
    style,
}) => {
    const glowStyles: Record<string, string> = {
        none: '',
        blue: 'shadow-[0_0_20px_rgba(59,130,246,0.06)]',
        purple: 'shadow-[0_0_20px_rgba(139,92,246,0.06)]',
        profit: 'shadow-[0_0_12px_rgba(34,197,94,0.08)]',
    };

    return (
        <div
            onClick={onClick}
            style={style}
            className={`
        surface-elevated
        ${compact ? 'p-3' : 'p-4'}
        ${glowStyles[glow]}
        ${onClick ? 'cursor-pointer hover:bg-[var(--bg-hover)] transition-colors' : ''}
        ${className}
      `}
        >
            {header && (
                <div className="flex items-center justify-between mb-3">
                    {header}
                </div>
            )}
            {children}
        </div>
    );
};

export default Card;
