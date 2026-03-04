import React, { useMemo } from 'react';
import type { VolumeProfileBin } from '../../types/api';

interface VolumeProfileChartProps {
    profile: VolumeProfileBin[];
    poc: number;
    valueAreaHigh: number;
    valueAreaLow: number;
    height?: number;
}

const SVG_WIDTH = 320;
const LABEL_WIDTH = 60;
const BAR_AREA_LEFT = LABEL_WIDTH + 4;
const BAR_AREA_WIDTH = SVG_WIDTH - BAR_AREA_LEFT - 8;
const PAD_TOP = 22;
const PAD_BOTTOM = 4;

const VolumeProfileChart: React.FC<VolumeProfileChartProps> = ({
    profile,
    poc,
    valueAreaHigh,
    valueAreaLow,
    height = 260,
}) => {
    const geometry = useMemo(() => {
        if (!profile || profile.length === 0) return null;

        const n = profile.length;
        const drawingHeight = height - PAD_TOP - PAD_BOTTOM;
        const barH = Math.max(drawingHeight / n - 1, 2);
        const barGap = Math.max((drawingHeight - barH * n) / Math.max(n - 1, 1), 1);

        const maxVol = Math.max(...profile.map((b) => b.total), 1);

        const bins = profile.map((bin, i) => {
            const y = PAD_TOP + i * (barH + barGap);
            const buyW = (bin.buy_vol / maxVol) * BAR_AREA_WIDTH;
            const sellW = (bin.sell_vol / maxVol) * BAR_AREA_WIDTH;
            const isPoc = bin.price === poc;
            const inValueArea = bin.price >= valueAreaLow && bin.price <= valueAreaHigh;

            return {
                y,
                barH,
                buyW,
                sellW,
                price: bin.price,
                isPoc,
                inValueArea,
            };
        });

        // Find POC bin y for the dashed line
        const pocBin = bins.find((b) => b.isPoc);
        const pocY = pocBin ? pocBin.y + barH / 2 : null;

        return { bins, pocY };
    }, [profile, poc, valueAreaHigh, valueAreaLow, height]);

    if (!geometry) {
        return (
            <div
                className="flex flex-col items-center justify-center text-[var(--text-muted)] text-xs"
                style={{ height }}
            >
                No volume profile data
            </div>
        );
    }

    const { bins, pocY } = geometry;

    return (
        <div className="flex flex-col" style={{ height }}>
            {/* Title */}
            <div
                className="text-[10px] font-semibold tracking-wider uppercase px-2 pb-1"
                style={{ color: 'var(--text-tertiary)' }}
            >
                Volume Profile
            </div>

            {/* SVG Chart */}
            <svg
                viewBox={`0 0 ${SVG_WIDTH} ${height - 16}`}
                width="100%"
                height={height - 16}
                preserveAspectRatio="xMidYMid meet"
            >
                {bins.map((bin, i) => (
                    <g key={i}>
                        {/* Value area background */}
                        {bin.inValueArea && (
                            <rect
                                x={BAR_AREA_LEFT - 2}
                                y={bin.y - 0.5}
                                width={BAR_AREA_WIDTH + 4}
                                height={bin.barH + 1}
                                fill="var(--accent-indigo)"
                                opacity={0.08}
                                rx={1}
                            />
                        )}

                        {/* Buy volume bar (green) */}
                        <rect
                            x={BAR_AREA_LEFT}
                            y={bin.y}
                            width={Math.max(bin.buyW, 0)}
                            height={bin.barH}
                            fill={bin.isPoc ? 'rgba(34, 197, 94, 0.9)' : 'var(--color-profit)'}
                            opacity={bin.isPoc ? 1 : 0.7}
                            rx={1}
                        />

                        {/* Sell volume bar (red, stacked) */}
                        <rect
                            x={BAR_AREA_LEFT + bin.buyW}
                            y={bin.y}
                            width={Math.max(bin.sellW, 0)}
                            height={bin.barH}
                            fill={bin.isPoc ? 'rgba(239, 68, 68, 0.9)' : 'var(--color-loss)'}
                            opacity={bin.isPoc ? 1 : 0.7}
                            rx={1}
                        />

                        {/* Price label */}
                        <text
                            x={LABEL_WIDTH - 2}
                            y={bin.y + bin.barH / 2}
                            textAnchor="end"
                            dominantBaseline="central"
                            fill={bin.isPoc ? 'var(--text-primary)' : 'var(--text-tertiary)'}
                            fontSize={9}
                            fontFamily="var(--font-mono)"
                            fontWeight={bin.isPoc ? 700 : 400}
                        >
                            {bin.price.toFixed(1)}
                        </text>
                    </g>
                ))}

                {/* POC dashed line */}
                {pocY !== null && (
                    <line
                        x1={BAR_AREA_LEFT - 4}
                        y1={pocY}
                        x2={SVG_WIDTH - 4}
                        y2={pocY}
                        stroke="var(--accent-indigo)"
                        strokeWidth={1.5}
                        strokeDasharray="4 3"
                        opacity={0.8}
                    />
                )}
            </svg>
        </div>
    );
};

export default React.memo(VolumeProfileChart);
