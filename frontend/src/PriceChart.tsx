import React, { useMemo } from 'react';

interface PricePoint {
    time: string;
    price: number;
}

interface PriceChartProps {
    data: PricePoint[];
    color?: string;
    height?: number;
}

const PriceChart: React.FC<PriceChartProps> = ({ data, color = "#06B6D4", height = 150 }) => {
    const points = useMemo(() => {
        if (!data || data.length < 2) return "";

        const prices = data.map(d => d.price);
        const minPrice = Math.min(...prices);
        const maxPrice = Math.max(...prices);
        const range = maxPrice - minPrice || 1; // Avoid division by zero

        // Normalize points to SVG coordinates
        // X axis: 0 to 100%
        // Y axis: height to 0 (SVG Y is inverted)

        return data.map((d, i) => {
            const x = (i / (data.length - 1)) * 100;
            const normalizedPrice = (d.price - minPrice) / range;
            const y = height - (normalizedPrice * height);
            return `${x},${y}`;
        }).join(" ");
    }, [data, height]);

    if (!data || data.length === 0) {
        return <div className="flex items-center justify-center h-full text-gray-500 text-xs">No Data</div>;
    }

    const currentPrice = data[0].price;
    const startPrice = data[data.length - 1].price;
    const isUp = currentPrice >= startPrice;
    const chartColor = isUp ? "#10B981" : "#EF4444"; // Green or Red

    return (
        <div className="w-full relative" style={{ height: `${height}px` }}>
            <svg viewBox={`0 0 100 ${height}`} className="w-full h-full overflow-visible" preserveAspectRatio="none">
                {/* Gradient Definition */}
                <defs>
                    <linearGradient id="chartGradient" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stopColor={chartColor} stopOpacity="0.2" />
                        <stop offset="100%" stopColor={chartColor} stopOpacity="0" />
                    </linearGradient>
                </defs>

                {/* Area Fill */}
                <path
                    d={`M0,${height} ${points} L100,${height} Z`}
                    fill="url(#chartGradient)"
                    stroke="none"
                />

                {/* Line */}
                <polyline
                    fill="none"
                    stroke={chartColor}
                    strokeWidth="2"
                    points={points}
                    vectorEffect="non-scaling-stroke"
                />

                {/* Current Price Dot */}
                {points && (
                    <circle
                        cx="0"
                        cy={points.split(' ')[0].split(',')[1]}
                        r="3"
                        fill={chartColor}
                        className="animate-pulse"
                    />
                )}
            </svg>
        </div>
    );
};

export default PriceChart;
