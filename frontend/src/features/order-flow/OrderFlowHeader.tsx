import React, { useMemo } from 'react';
import type { OrderFlowData } from '../../types/api';

interface OrderFlowHeaderProps {
    data: OrderFlowData | null | undefined;
    futuresLtp?: number;
}

/** Format number with 1 decimal, locale-aware. Returns '--' for falsy. */
function fmt(v: number | null | undefined): string {
    if (!v && v !== 0) return '--';
    return v.toLocaleString('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

/** Format volume: 100K+ -> "1.2L", 1K+ -> "45.0K", else plain */
function fmtVol(v: number | null | undefined): string {
    if (!v && v !== 0) return '--';
    const absV = Math.abs(v);
    const sign = v < 0 ? '-' : '';
    if (absV >= 100000) return sign + (absV / 100000).toFixed(1) + 'L';
    if (absV >= 1000) return sign + (absV / 1000).toFixed(1) + 'K';
    return sign + absV.toFixed(0);
}

const OrderFlowHeader: React.FC<OrderFlowHeaderProps> = ({ data, futuresLtp }) => {
    const derived = useMemo(() => {
        if (!data) return null;

        // VWAP position relative to LTP
        let vwapPosition: 'above' | 'below' | 'at' = 'at';
        if (futuresLtp && data.vwap) {
            if (futuresLtp > data.vwap) vwapPosition = 'above';
            else if (futuresLtp < data.vwap) vwapPosition = 'below';
        }

        // Book imbalance
        const imbalancePct = (data.book_imbalance * 100).toFixed(1);
        let imbalanceLabel: string;
        let imbalanceColor: string;
        if (data.book_imbalance > 0.1) {
            imbalanceLabel = 'BID';
            imbalanceColor = 'var(--color-profit-text)';
        } else if (data.book_imbalance < -0.1) {
            imbalanceLabel = 'ASK';
            imbalanceColor = 'var(--color-loss-text)';
        } else {
            imbalanceLabel = 'BAL';
            imbalanceColor = 'var(--text-tertiary)';
        }

        return {
            vwapPosition,
            imbalancePct,
            imbalanceLabel,
            imbalanceColor,
        };
    }, [data, futuresLtp]);

    if (!data || !derived) {
        return (
            <div
                className="px-3 py-2 border-b border-[var(--border-subtle)] flex items-center text-xs text-[var(--text-muted)]"
                style={{ minHeight: 36 }}
            >
                Order Flow &mdash; waiting for data...
            </div>
        );
    }

    const { vwapPosition, imbalancePct, imbalanceLabel, imbalanceColor } = derived;
    const div = data.delta_divergence;

    return (
        <div
            className="px-3 py-2 border-b border-[var(--border-subtle)] flex items-center gap-4 text-xs flex-wrap"
            style={{ minHeight: 36 }}
        >
            {/* VWAP */}
            <div className="flex items-center gap-1">
                <span className="text-[var(--text-tertiary)]">VWAP</span>
                <span className="mono text-[var(--text-primary)] font-semibold">{fmt(data.vwap)}</span>
                {vwapPosition === 'above' && (
                    <span className="text-[var(--color-profit-text)] text-[10px]">{'\u25B2'} Above</span>
                )}
                {vwapPosition === 'below' && (
                    <span className="text-[var(--color-loss-text)] text-[10px]">{'\u25BC'} Below</span>
                )}
            </div>

            {/* POC */}
            <div className="flex items-center gap-1">
                <span className="text-[var(--text-tertiary)]">POC</span>
                <span className="mono text-[var(--text-primary)] font-semibold">{fmt(data.poc)}</span>
            </div>

            {/* Book Imbalance */}
            <div className="flex items-center gap-1">
                <span className="text-[var(--text-tertiary)]">Imbalance</span>
                <span className="mono font-semibold" style={{ color: imbalanceColor }}>
                    {imbalancePct}%
                </span>
                <span
                    className="text-[10px] px-1 py-0.5 rounded font-medium"
                    style={{
                        color: imbalanceColor,
                        backgroundColor:
                            imbalanceLabel === 'BID'
                                ? 'rgba(34, 197, 94, 0.1)'
                                : imbalanceLabel === 'ASK'
                                  ? 'rgba(239, 68, 68, 0.1)'
                                  : 'var(--surface-sunken)',
                    }}
                >
                    {imbalanceLabel}
                </span>
            </div>

            {/* Delta Divergence (only when active) */}
            {div.active && div.type && (
                <div
                    className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
                    style={{
                        color: div.type === 'bullish' ? 'var(--color-profit-text)' : 'var(--color-loss-text)',
                        backgroundColor:
                            div.type === 'bullish' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                    }}
                >
                    {div.type === 'bullish' ? '\u25B2' : '\u25BC'} Divergence ({div.bars}b, {(div.strength * 100).toFixed(0)}%)
                </div>
            )}

            {/* Total Volume (right-aligned) */}
            <div className="flex items-center gap-1 ml-auto">
                <span className="text-[var(--text-tertiary)]">Vol</span>
                <span className="mono text-[var(--text-primary)] font-semibold">{fmtVol(data.total_volume)}</span>
            </div>
        </div>
    );
};

export default React.memo(OrderFlowHeader);
