import React, { useMemo } from 'react';

interface SparklineProps {
    data: number[];
    width?: number;
    height?: number;
    className?: string;
}

const Sparkline: React.FC<SparklineProps> = ({ data, width = 80, height = 24, className = '' }) => {
    const pathData = useMemo(() => {
        if (!data || data.length < 2) return '';

        const min = Math.min(...data);
        const max = Math.max(...data);
        const range = max - min || 1;

        return data
            .map((val, i) => {
                const x = (i / (data.length - 1)) * width;
                const y = height - ((val - min) / range) * height;
                return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
            })
            .join(' ');
    }, [data, width, height]);

    if (!data || data.length < 2) return null;

    const isUp = data[data.length - 1] >= data[0];
    const color = isUp ? 'var(--color-profit)' : 'var(--color-loss)';

    return (
        <svg
            width={width}
            height={height}
            viewBox={`0 0 ${width} ${height}`}
            className={`overflow-visible ${className}`}
        >
            <defs>
                <linearGradient id={`spark-grad-${isUp ? 'up' : 'down'}`} x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity="0.2" />
                    <stop offset="100%" stopColor={color} stopOpacity="0" />
                </linearGradient>
            </defs>
            {/* Area fill */}
            <path
                d={`${pathData} L${width},${height} L0,${height} Z`}
                fill={`url(#spark-grad-${isUp ? 'up' : 'down'})`}
            />
            {/* Line */}
            <path d={pathData} fill="none" stroke={color} strokeWidth="1.5" />
            {/* Current point */}
            <circle
                cx={width}
                cy={(() => {
                    const min = Math.min(...data);
                    const max = Math.max(...data);
                    const range = max - min || 1;
                    return height - ((data[data.length - 1] - min) / range) * height;
                })()}
                r="2"
                fill={color}
                className="animate-pulse-live"
            />
        </svg>
    );
};

export default Sparkline;
