import React, { useMemo } from 'react';
import type { OrderFlowData } from '../../types/api';

interface OrderBookPanelProps {
    data: OrderFlowData | null | undefined;
    height?: number;
}

function fmtQty(v: number): string {
    if (v >= 100000) return (v / 100000).toFixed(1) + 'L';
    if (v >= 1000) return (v / 1000).toFixed(1) + 'K';
    return v.toFixed(0);
}

const OrderBookPanel: React.FC<OrderBookPanelProps> = ({ data, height = 260 }) => {
    const gaugeData = useMemo(() => {
        if (!data) return null;
        const { bid_total, ask_total, book_imbalance } = data;
        const total = bid_total + ask_total;
        if (total <= 0) return null;
        const bidPct = (bid_total / total) * 100;
        const askPct = (ask_total / total) * 100;
        return { bid_total, ask_total, book_imbalance, bidPct, askPct };
    }, [data]);

    if (!gaugeData) {
        return (
            <div className="flex items-center justify-center text-xs text-[var(--text-tertiary)]" style={{ height }}>
                No order book data
            </div>
        );
    }

    const { bid_total, ask_total, book_imbalance, bidPct, askPct } = gaugeData;
    const imbPct = (book_imbalance * 100).toFixed(1);
    const biasLabel = book_imbalance > 0.55 ? 'BULLISH' : book_imbalance < 0.45 ? 'BEARISH' : 'NEUTRAL';
    const biasColor = book_imbalance > 0.55
        ? 'var(--color-profit-text)'
        : book_imbalance < 0.45
            ? 'var(--color-loss-text)'
            : 'var(--text-secondary)';

    const svgW = 260;
    const svgH = 140;
    const barW = 200;
    const barH = 20;
    const barX = (svgW - barW) / 2;
    const barY = 60;

    return (
        <div>
            <div className="text-[10px] font-semibold text-[var(--text-tertiary)] mb-1 px-1">ORDER BOOK IMBALANCE</div>
            <div className="flex flex-col items-center" style={{ minHeight: height - 30 }}>
                <svg viewBox={`0 0 ${svgW} ${svgH}`} width="100%" style={{ maxHeight: svgH }}>
                    {/* Bias label */}
                    <text x={svgW / 2} y={25} textAnchor="middle" fontSize={16} fontWeight={700}
                        fill={biasColor}>{biasLabel}</text>
                    <text x={svgW / 2} y={42} textAnchor="middle" fontSize={11}
                        fill="var(--text-tertiary)" fontFamily="var(--font-mono)">{imbPct}%</text>

                    {/* Stacked bar: bids (green) | asks (red) */}
                    <rect x={barX} y={barY} width={barW} height={barH} rx={4}
                        fill="rgba(239,68,68,0.3)" />
                    <rect x={barX} y={barY} width={barW * (bidPct / 100)} height={barH} rx={4}
                        fill="rgba(34,197,94,0.6)" />

                    {/* Center line */}
                    <line x1={barX + barW / 2} y1={barY - 2} x2={barX + barW / 2} y2={barY + barH + 2}
                        stroke="var(--text-tertiary)" strokeWidth={1} opacity={0.4} />

                    {/* Labels */}
                    <text x={barX} y={barY + barH + 16} fontSize={10}
                        fill="var(--color-profit-text)" fontFamily="var(--font-mono)">
                        BID {fmtQty(bid_total)}
                    </text>
                    <text x={barX + barW} y={barY + barH + 16} textAnchor="end" fontSize={10}
                        fill="var(--color-loss-text)" fontFamily="var(--font-mono)">
                        ASK {fmtQty(ask_total)}
                    </text>

                    {/* Percentage labels inside bar */}
                    <text x={barX + 6} y={barY + barH / 2 + 4} fontSize={10} fontWeight={600}
                        fill="white" fontFamily="var(--font-mono)">{bidPct.toFixed(0)}%</text>
                    <text x={barX + barW - 6} y={barY + barH / 2 + 4} textAnchor="end"
                        fontSize={10} fontWeight={600} fill="white"
                        fontFamily="var(--font-mono)">{askPct.toFixed(0)}%</text>
                </svg>

                <div className="text-[10px] text-[var(--text-tertiary)] text-center mt-1 px-4">
                    {book_imbalance > 0.6
                        ? 'Strong buying pressure — bids significantly outweigh asks'
                        : book_imbalance < 0.4
                            ? 'Strong selling pressure — asks significantly outweigh bids'
                            : 'Balanced order book — no significant directional pressure'}
                </div>
            </div>
        </div>
    );
};

export default React.memo(OrderBookPanel);
