import React, { useMemo } from 'react';
import type { OrderFlowData } from '../../types/api';

interface VWAPChartProps {
    data: OrderFlowData | null | undefined;
    futuresLtp?: number;
    height?: number;
}

const SVG_WIDTH = 400;
const PAD_LEFT = 58;
const PAD_RIGHT = 80;
const PAD_TOP = 24;
const PAD_BOTTOM = 12;
const CHART_LEFT = PAD_LEFT;
const CHART_RIGHT = SVG_WIDTH - PAD_RIGHT;
const CHART_WIDTH = CHART_RIGHT - CHART_LEFT;
const CENTER_X = CHART_LEFT + CHART_WIDTH / 2;

/** Format price for labels */
function fmtPrice(v: number): string {
    return v.toLocaleString('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

const VWAPChart: React.FC<VWAPChartProps> = ({ data, futuresLtp, height = 280 }) => {
    const geometry = useMemo(() => {
        if (!data) return null;

        const svgHeight = height - 16; // room for title
        const drawingHeight = svgHeight - PAD_TOP - PAD_BOTTOM;

        // Collect all non-zero price levels
        const prices: number[] = [];
        if (data.vwap) prices.push(data.vwap);
        if (data.vwap_upper) prices.push(data.vwap_upper);
        if (data.vwap_lower) prices.push(data.vwap_lower);
        if (data.poc) prices.push(data.poc);
        if (data.value_area_high) prices.push(data.value_area_high);
        if (data.value_area_low) prices.push(data.value_area_low);
        if (futuresLtp) prices.push(futuresLtp);

        if (prices.length === 0) return null;

        const minPrice = Math.min(...prices) - 20;
        const maxPrice = Math.max(...prices) + 20;
        const priceRange = maxPrice - minPrice || 1;

        /** Map price to Y coordinate (bottom = low, top = high) */
        const priceToY = (p: number): number => {
            return PAD_TOP + (1 - (p - minPrice) / priceRange) * drawingHeight;
        };

        // VWAP levels
        const vwapY = priceToY(data.vwap);
        const upperY = data.vwap_upper ? priceToY(data.vwap_upper) : null;
        const lowerY = data.vwap_lower ? priceToY(data.vwap_lower) : null;

        // POC
        const pocY = data.poc ? priceToY(data.poc) : null;

        // Value area
        const vaHighY = data.value_area_high ? priceToY(data.value_area_high) : null;
        const vaLowY = data.value_area_low ? priceToY(data.value_area_low) : null;

        // LTP
        const ltpY = futuresLtp ? priceToY(futuresLtp) : null;

        return {
            svgHeight,
            vwapY,
            upperY,
            lowerY,
            pocY,
            vaHighY,
            vaLowY,
            ltpY,
        };
    }, [data, futuresLtp, height]);

    if (!data || !geometry) {
        return (
            <div
                className="flex flex-col items-center justify-center text-[var(--text-muted)] text-xs"
                style={{ height }}
            >
                No VWAP data
            </div>
        );
    }

    const { svgHeight, vwapY, upperY, lowerY, pocY, vaHighY, vaLowY, ltpY } = geometry;

    return (
        <div className="flex flex-col" style={{ height }}>
            {/* Title */}
            <div
                className="text-[10px] font-semibold tracking-wider uppercase px-2 pb-1"
                style={{ color: 'var(--text-tertiary)' }}
            >
                VWAP &amp; Levels
            </div>

            {/* SVG Chart */}
            <svg
                viewBox={`0 0 ${SVG_WIDTH} ${svgHeight}`}
                width="100%"
                height={svgHeight}
                preserveAspectRatio="xMidYMid meet"
            >
                {/* Deviation band shaded area */}
                {upperY !== null && lowerY !== null && (
                    <rect
                        x={CHART_LEFT}
                        y={upperY}
                        width={CHART_WIDTH}
                        height={lowerY - upperY}
                        fill="rgba(234, 179, 8, 0.08)"
                        rx={2}
                    />
                )}

                {/* Value area background rect */}
                {vaHighY !== null && vaLowY !== null && (
                    <rect
                        x={CHART_LEFT + 2}
                        y={vaHighY}
                        width={CHART_WIDTH - 4}
                        height={vaLowY - vaHighY}
                        fill="var(--accent-indigo)"
                        opacity={0.06}
                        rx={2}
                    />
                )}

                {/* VWAP upper band (dashed yellow) */}
                {upperY !== null && (
                    <>
                        <line
                            x1={CHART_LEFT}
                            y1={upperY}
                            x2={CHART_RIGHT}
                            y2={upperY}
                            stroke="rgba(234, 179, 8, 0.5)"
                            strokeWidth={1}
                            strokeDasharray="4 3"
                        />
                        <text
                            x={PAD_LEFT - 4}
                            y={upperY}
                            textAnchor="end"
                            dominantBaseline="central"
                            fontSize={9}
                            fontFamily="var(--font-mono)"
                            fill="var(--text-tertiary)"
                        >
                            {fmtPrice(data.vwap_upper)}
                        </text>
                        <text
                            x={CHART_RIGHT + 4}
                            y={upperY}
                            textAnchor="start"
                            dominantBaseline="central"
                            fontSize={8}
                            fill="rgba(234, 179, 8, 0.7)"
                        >
                            +1{'\u03C3'}
                        </text>
                    </>
                )}

                {/* VWAP lower band (dashed yellow) */}
                {lowerY !== null && (
                    <>
                        <line
                            x1={CHART_LEFT}
                            y1={lowerY}
                            x2={CHART_RIGHT}
                            y2={lowerY}
                            stroke="rgba(234, 179, 8, 0.5)"
                            strokeWidth={1}
                            strokeDasharray="4 3"
                        />
                        <text
                            x={PAD_LEFT - 4}
                            y={lowerY}
                            textAnchor="end"
                            dominantBaseline="central"
                            fontSize={9}
                            fontFamily="var(--font-mono)"
                            fill="var(--text-tertiary)"
                        >
                            {fmtPrice(data.vwap_lower)}
                        </text>
                        <text
                            x={CHART_RIGHT + 4}
                            y={lowerY}
                            textAnchor="start"
                            dominantBaseline="central"
                            fontSize={8}
                            fill="rgba(234, 179, 8, 0.7)"
                        >
                            -1{'\u03C3'}
                        </text>
                    </>
                )}

                {/* VWAP solid line (yellow) */}
                <line
                    x1={CHART_LEFT}
                    y1={vwapY}
                    x2={CHART_RIGHT}
                    y2={vwapY}
                    stroke="rgb(234, 179, 8)"
                    strokeWidth={2}
                />
                <text
                    x={PAD_LEFT - 4}
                    y={vwapY}
                    textAnchor="end"
                    dominantBaseline="central"
                    fontSize={9}
                    fontFamily="var(--font-mono)"
                    fill="rgb(234, 179, 8)"
                    fontWeight={700}
                >
                    {fmtPrice(data.vwap)}
                </text>
                <text
                    x={CHART_RIGHT + 4}
                    y={vwapY}
                    textAnchor="start"
                    dominantBaseline="central"
                    fontSize={9}
                    fill="rgb(234, 179, 8)"
                    fontWeight={600}
                >
                    VWAP
                </text>

                {/* POC dashed line (indigo) */}
                {pocY !== null && (
                    <>
                        <line
                            x1={CHART_LEFT}
                            y1={pocY}
                            x2={CHART_RIGHT}
                            y2={pocY}
                            stroke="var(--accent-indigo)"
                            strokeWidth={1.5}
                            strokeDasharray="5 3"
                            opacity={0.8}
                        />
                        <text
                            x={PAD_LEFT - 4}
                            y={pocY}
                            textAnchor="end"
                            dominantBaseline="central"
                            fontSize={9}
                            fontFamily="var(--font-mono)"
                            fill="var(--accent-indigo)"
                        >
                            {fmtPrice(data.poc)}
                        </text>
                        <text
                            x={CHART_RIGHT + 4}
                            y={pocY}
                            textAnchor="start"
                            dominantBaseline="central"
                            fontSize={9}
                            fill="var(--accent-indigo)"
                            fontWeight={600}
                        >
                            POC
                        </text>
                    </>
                )}

                {/* Value Area High label */}
                {vaHighY !== null && (
                    <text
                        x={CHART_RIGHT + 4}
                        y={vaHighY}
                        textAnchor="start"
                        dominantBaseline="central"
                        fontSize={8}
                        fill="var(--accent-indigo)"
                        opacity={0.6}
                    >
                        VA-H
                    </text>
                )}

                {/* Value Area Low label */}
                {vaLowY !== null && (
                    <text
                        x={CHART_RIGHT + 4}
                        y={vaLowY}
                        textAnchor="start"
                        dominantBaseline="central"
                        fontSize={8}
                        fill="var(--accent-indigo)"
                        opacity={0.6}
                    >
                        VA-L
                    </text>
                )}

                {/* LTP circle + label */}
                {ltpY !== null && futuresLtp && (
                    <>
                        <circle
                            cx={CENTER_X}
                            cy={ltpY}
                            r={5}
                            fill={futuresLtp >= data.vwap ? 'var(--color-profit)' : 'var(--color-loss)'}
                            stroke={futuresLtp >= data.vwap ? 'var(--color-profit-text)' : 'var(--color-loss-text)'}
                            strokeWidth={1.5}
                        />
                        <text
                            x={PAD_LEFT - 4}
                            y={ltpY}
                            textAnchor="end"
                            dominantBaseline="central"
                            fontSize={9}
                            fontFamily="var(--font-mono)"
                            fill="var(--text-primary)"
                            fontWeight={700}
                        >
                            {fmtPrice(futuresLtp)}
                        </text>
                        <text
                            x={CENTER_X + 10}
                            y={ltpY}
                            textAnchor="start"
                            dominantBaseline="central"
                            fontSize={9}
                            fill="var(--text-primary)"
                            fontWeight={600}
                        >
                            LTP
                        </text>
                    </>
                )}
            </svg>
        </div>
    );
};

export default React.memo(VWAPChart);
