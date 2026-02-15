import React, { useMemo } from 'react';
import type { PricePoint } from '../../types/api';

interface PriceChartProps {
    data: PricePoint[];
    height?: number;
}

const PriceChart: React.FC<PriceChartProps> = ({ data, height = 260 }) => {
    const svgWidth = 100;

    const { pathLine, pathArea, isUp, latestY } = useMemo(() => {
        if (!data || data.length < 2)
            return { pathLine: '', pathArea: '', isUp: true, latestY: 0 };

        const prices = data.map((d) => d.price);
        const minP = Math.min(...prices);
        const maxP = Math.max(...prices);
        const range = maxP - minP || 1;
        const pad = 8; // padding from edges

        const pts = data.map((d, i) => {
            const x = (i / (data.length - 1)) * svgWidth;
            const y = pad + (1 - (d.price - minP) / range) * (height - pad * 2);
            return { x, y };
        });

        const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ');
        const area = `${line} L${svgWidth},${height} L0,${height} Z`;

        return {
            pathLine: line,
            pathArea: area,
            isUp: prices[prices.length - 1] >= prices[0],
            latestY: pts[pts.length - 1]?.y ?? 0,
        };
    }, [data, height]);

    if (!data || data.length < 2) {
        return (
            <div
                className="flex items-center justify-center text-[var(--text-muted)] text-sm"
                style={{ height }}
            >
                Waiting for price data…
            </div>
        );
    }

    const color = isUp ? 'var(--color-profit)' : 'var(--color-loss)';
    const gradId = `chart-grad-${isUp ? 'up' : 'dn'}`;

    return (
        <div className="w-full relative" style={{ height }}>
            <svg
                viewBox={`0 0 ${svgWidth} ${height}`}
                className="w-full h-full"
                preserveAspectRatio="none"
            >
                <defs>
                    <linearGradient id={gradId} x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stopColor={color} stopOpacity="0.15" />
                        <stop offset="100%" stopColor={color} stopOpacity="0" />
                    </linearGradient>
                </defs>

                {/* Grid lines */}
                {[0.25, 0.5, 0.75].map((pct) => (
                    <line
                        key={pct}
                        x1="0"
                        x2={svgWidth}
                        y1={height * pct}
                        y2={height * pct}
                        stroke="var(--border-subtle)"
                        strokeWidth="0.3"
                        vectorEffect="non-scaling-stroke"
                    />
                ))}

                {/* Area fill */}
                <path d={pathArea} fill={`url(#${gradId})`} />

                {/* Price line */}
                <path
                    d={pathLine}
                    fill="none"
                    stroke={color}
                    strokeWidth="1.5"
                    vectorEffect="non-scaling-stroke"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                />

                {/* Live dot */}
                <circle
                    cx={svgWidth}
                    cy={latestY}
                    r="3"
                    fill={color}
                    className="animate-pulse-live"
                />
            </svg>
        </div>
    );
};

export default PriceChart;
