import React, { useMemo } from 'react';
import type { IntelligenceContext } from '../types/api';

interface MarketOverviewBarProps {
    strategyData?: any;
    currentPrice: number;
    pcrAnalysis?: any;
    sentiment?: any;
    isRunning: boolean;
    intelligence?: IntelligenceContext;
}

interface MetricPill {
    label: string;
    value: string;
    valueColor: string;
}

const buildupShort: Record<string, { text: string; color: string }> = {
    LONG_BUILDUP:   { text: 'LB', color: 'var(--color-profit-text)' },
    SHORT_COVERING: { text: 'SC', color: 'var(--color-profit-text)' },
    SHORT_BUILDUP:  { text: 'SB', color: 'var(--color-loss-text)' },
    LONG_UNWINDING: { text: 'LU', color: 'var(--color-loss-text)' },
    NEUTRAL:        { text: '--', color: 'var(--text-muted)' },
};

const MarketOverviewBar: React.FC<MarketOverviewBarProps> = React.memo(({
    strategyData,
    currentPrice,
    pcrAnalysis,
    sentiment,
    isRunning,
    intelligence,
}) => {
    const pills = useMemo<MetricPill[]>(() => {
        const result: MetricPill[] = [];

        // RSI
        const rsi = strategyData?.rsi;
        if (rsi != null) {
            result.push({
                label: 'RSI',
                value: Number(rsi).toFixed(1),
                valueColor: rsi > 70
                    ? 'var(--color-loss-text)'
                    : rsi < 30
                        ? 'var(--color-profit-text)'
                        : 'var(--color-warning)',
            });
        }

        // Supertrend
        const supertrend = strategyData?.supertrend;
        if (supertrend) {
            result.push({
                label: 'TREND',
                value: supertrend === 'BULLISH' ? '▲ BULL' : '▼ BEAR',
                valueColor: supertrend === 'BULLISH' ? 'var(--color-profit-text)' : 'var(--color-loss-text)',
            });
        }

        // EMA alignment
        const ema5 = strategyData?.ema_5;
        const ema20 = strategyData?.ema_20;
        if (ema5 != null && ema20 != null) {
            const isBull = ema5 > ema20;
            result.push({
                label: 'EMA',
                value: isBull ? '5>20' : '5<20',
                valueColor: isBull ? 'var(--color-profit-text)' : 'var(--color-loss-text)',
            });
        }

        // PCR
        const pcr = pcrAnalysis?.pcr;
        if (pcr != null) {
            result.push({
                label: 'PCR',
                value: Number(pcr).toFixed(2),
                valueColor: pcr > 1.2
                    ? 'var(--color-loss-text)'
                    : pcr < 0.8
                        ? 'var(--color-profit-text)'
                        : 'var(--color-warning)',
            });
        }

        // VIX
        const vix = sentiment?.vix ?? pcrAnalysis?.vix;
        if (vix != null) {
            result.push({
                label: 'VIX',
                value: Number(vix).toFixed(1),
                valueColor: vix > 20
                    ? 'var(--color-loss-text)'
                    : vix < 15
                        ? 'var(--color-profit-text)'
                        : 'var(--color-warning)',
            });
        }

        // IV Rank
        const ivRankData = intelligence?.iv_rank;
        if (ivRankData?.iv_rank != null) {
            const ivr = ivRankData.iv_rank;
            result.push({
                label: 'IVR',
                value: `${ivr.toFixed(0)}%`,
                valueColor: ivr >= 50
                    ? 'var(--color-profit-text)'
                    : ivr < 20
                        ? 'var(--color-loss-text)'
                        : 'var(--color-warning)',
            });
        }

        // OI Buildup
        const oiData = intelligence?.oi_analysis;
        if (oiData && oiData.snapshots_count >= 3) {
            const b = buildupShort[oiData.buildup_signal] || buildupShort.NEUTRAL;
            result.push({
                label: 'OI',
                value: b.text,
                valueColor: b.color,
            });
        }

        // Max Pain
        if (oiData?.max_pain_strike) {
            result.push({
                label: 'MPAIN',
                value: oiData.max_pain_strike.toFixed(0),
                valueColor: 'var(--accent-purple)',
            });
        }

        // Volume ratio
        const volRatio = strategyData?.volume_ratio;
        if (volRatio != null) {
            result.push({
                label: 'VOL',
                value: Number(volRatio).toFixed(1) + 'x',
                valueColor: volRatio >= 1.5 ? 'var(--accent-cyan)' : 'var(--text-secondary)',
            });
        }

        // Expiry Day
        const isExpiry = new Date().getDay() === 4; // Thursday
        if (isExpiry) {
            result.push({
                label: '0DTE',
                value: 'EXPIRY',
                valueColor: 'var(--color-warning)',
            });
        }

        // Bot status
        result.push({
            label: 'BOT',
            value: isRunning ? 'LIVE' : 'IDLE',
            valueColor: isRunning ? 'var(--color-profit-text)' : 'var(--text-muted)',
        });

        return result;
    }, [strategyData, currentPrice, pcrAnalysis, sentiment, isRunning, intelligence]);

    if (pills.length === 0) return null;

    return (
        <div
            className="border-t border-[var(--border-subtle)] bg-[var(--bg-primary)]/80"
            style={{ height: 'var(--market-bar-height)' }}
        >
            <div className="max-w-[var(--max-content)] mx-auto px-3 lg:px-4 h-full">
                <div className="flex items-center h-full overflow-x-auto"
                    style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' } as React.CSSProperties}
                >
                    {pills.map((pill, i) => (
                        <React.Fragment key={pill.label}>
                            {i > 0 && (
                                <div
                                    className="flex-shrink-0 mx-2.5"
                                    style={{
                                        width: '1px',
                                        height: '14px',
                                        background: 'var(--border-subtle)',
                                    }}
                                />
                            )}
                            <div className="flex items-center gap-1.5 flex-shrink-0">
                                <span style={{
                                    fontSize: '10px',
                                    fontWeight: 500,
                                    color: 'var(--text-tertiary)',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.06em',
                                }}>
                                    {pill.label}
                                </span>
                                <span
                                    className="mono"
                                    style={{
                                        fontSize: '11px',
                                        fontWeight: 700,
                                        color: pill.valueColor,
                                    }}
                                >
                                    {pill.value}
                                </span>
                            </div>
                        </React.Fragment>
                    ))}
                </div>
            </div>
        </div>
    );
});

MarketOverviewBar.displayName = 'MarketOverviewBar';
export default MarketOverviewBar;
