import React from 'react';
import Card from '../../shared/Card';
import type {
    StrategyData,
    IntelligenceContext,
    Position,
    RiskStats,
} from '../../types/api';

interface MarketSnapshotDashboardProps {
    strategyData?: StrategyData;
    currentPrice: number;
    intelligence?: IntelligenceContext;
    positions?: Position[];
    pnl?: { daily: number; unrealized: number };
    riskStats?: RiskStats;
    signal?: string;
    pcrAnalysis?: any;
}

/* ── Tiny helpers ── */
const fmt = (n: number | null | undefined, decimals = 0) =>
    n != null ? n.toFixed(decimals) : '--';

const pnlColor = (v: number) =>
    v > 0 ? 'var(--color-profit-text)' : v < 0 ? 'var(--color-loss-text)' : 'var(--text-secondary)';

const pnlSign = (v: number) => (v > 0 ? '+' : '');

const MarketSnapshotDashboard: React.FC<MarketSnapshotDashboardProps> = React.memo(({
    strategyData,
    currentPrice,
    intelligence,
    positions = [],
    pnl,
    riskStats,
    signal,
    pcrAnalysis,
}) => {
    // ── Key Levels ──
    const sr = strategyData?.support_resistance;
    const oi = intelligence?.oi_analysis;
    const maxPain = oi?.max_pain_strike;
    const nearestSupport = sr?.nearest_support;
    const nearestResistance = sr?.nearest_resistance;

    // ── Risk Assessment ──
    const regime = intelligence?.market_regime;
    const ivRank = intelligence?.iv_rank;
    const portfolioGreeks = intelligence?.portfolio_greeks;
    const portfolioRisk = portfolioGreeks?.portfolio_risk ?? 'LOW';
    const riskScore = portfolioRisk === 'HIGH' ? 85 : portfolioRisk === 'MEDIUM' ? 55 : 25;
    const riskColor = portfolioRisk === 'HIGH' ? 'var(--color-loss-text)' : portfolioRisk === 'MEDIUM' ? 'var(--color-warning)' : 'var(--color-profit-text)';

    // ── P&L ──
    const dailyPnl = pnl?.daily ?? riskStats?.daily_pnl ?? 0;
    const unrealizedPnl = pnl?.unrealized ?? 0;
    const totalPnl = dailyPnl + unrealizedPnl;

    // ── Order Flow / OI ──
    const oiSignal = oi?.buildup_signal ?? 'NEUTRAL';
    const oiColor =
        oiSignal === 'LONG_BUILDUP' || oiSignal === 'SHORT_COVERING'
            ? 'var(--color-profit-text)'
            : oiSignal === 'SHORT_BUILDUP' || oiSignal === 'LONG_UNWINDING'
                ? 'var(--color-loss-text)'
                : 'var(--text-secondary)';

    const orderBook = intelligence?.order_book;

    return (
        <div className="grid grid-cols-2 gap-2 p-3" style={{ minHeight: 320 }}>
            {/* ── 1. Key Levels ── */}
            <Card compact className="!p-3">
                <div className="label mb-2 flex items-center gap-1.5">
                    <span style={{ fontSize: 13 }}>&#x1F4CD;</span>
                    Key Levels
                </div>

                <div className="space-y-1.5">
                    <LevelRow
                        label="Resistance"
                        value={nearestResistance}
                        current={currentPrice}
                        color="var(--color-loss-text)"
                    />
                    <LevelRow
                        label="Support"
                        value={nearestSupport}
                        current={currentPrice}
                        color="var(--color-profit-text)"
                    />
                    <LevelRow
                        label="Max Pain"
                        value={maxPain}
                        current={currentPrice}
                        color="var(--accent-purple)"
                    />
                    {oi?.max_oi_ce_strike && (
                        <LevelRow
                            label="Max OI CE"
                            value={oi.max_oi_ce_strike}
                            current={currentPrice}
                            color="var(--color-loss-text)"
                            subtle
                        />
                    )}
                    {oi?.max_oi_pe_strike && (
                        <LevelRow
                            label="Max OI PE"
                            value={oi.max_oi_pe_strike}
                            current={currentPrice}
                            color="var(--color-profit-text)"
                            subtle
                        />
                    )}
                </div>
            </Card>

            {/* ── 2. Risk Meter ── */}
            <Card compact className="!p-3">
                <div className="label mb-2 flex items-center gap-1.5">
                    <span style={{ fontSize: 13 }}>&#x1F6E1;</span>
                    Risk Meter
                </div>

                {/* Gauge */}
                <div className="flex items-center gap-2 mb-2">
                    <div className="flex-1 h-2 rounded-full bg-[var(--bg-overlay)] overflow-hidden">
                        <div
                            className="h-full rounded-full transition-all duration-700"
                            style={{
                                width: `${riskScore}%`,
                                background: `${riskColor}`,
                            }}
                        />
                    </div>
                    <span className="mono text-xs font-bold" style={{ color: riskColor }}>
                        {portfolioRisk}
                    </span>
                </div>

                <div className="space-y-1">
                    <MiniRow
                        label="Regime"
                        value={regime?.regime ?? '--'}
                        color={
                            regime?.regime === 'TRENDING'
                                ? 'var(--accent-blue)'
                                : regime?.regime === 'HIGH_VOLATILITY'
                                    ? 'var(--color-warning)'
                                    : 'var(--text-secondary)'
                        }
                    />
                    <MiniRow
                        label="IV Rank"
                        value={ivRank?.iv_rank != null ? `${ivRank.iv_rank.toFixed(0)}%` : '--'}
                        color={
                            (ivRank?.iv_rank ?? 0) > 70
                                ? 'var(--color-loss-text)'
                                : (ivRank?.iv_rank ?? 0) > 40
                                    ? 'var(--color-warning)'
                                    : 'var(--color-profit-text)'
                        }
                    />
                    <MiniRow
                        label="Net Delta"
                        value={portfolioGreeks?.net_delta != null ? portfolioGreeks.net_delta.toFixed(2) : '--'}
                        color={
                            (portfolioGreeks?.net_delta ?? 0) > 0
                                ? 'var(--color-profit-text)'
                                : (portfolioGreeks?.net_delta ?? 0) < 0
                                    ? 'var(--color-loss-text)'
                                    : 'var(--text-secondary)'
                        }
                    />
                    {portfolioGreeks?.hedge_needed && (
                        <div className="text-[10px] mt-1 px-1.5 py-0.5 rounded bg-[var(--color-warning)]/10 text-[var(--color-warning)] border border-[var(--color-warning)]/20">
                            Hedge: {portfolioGreeks.hedge_action ?? 'Needed'}
                        </div>
                    )}
                </div>
            </Card>

            {/* ── 3. Today's P&L ── */}
            <Card compact className="!p-3">
                <div className="label mb-2 flex items-center gap-1.5">
                    <span style={{ fontSize: 13 }}>&#x1F4B0;</span>
                    Today's P&L
                </div>

                <div
                    className="mono text-xl font-bold mb-1"
                    style={{ color: pnlColor(totalPnl) }}
                >
                    {pnlSign(totalPnl)}₹{fmt(Math.abs(totalPnl), 0)}
                </div>

                <div className="space-y-1">
                    <MiniRow
                        label="Realized"
                        value={`${pnlSign(dailyPnl)}₹${fmt(Math.abs(dailyPnl), 0)}`}
                        color={pnlColor(dailyPnl)}
                    />
                    <MiniRow
                        label="Unrealized"
                        value={`${pnlSign(unrealizedPnl)}₹${fmt(Math.abs(unrealizedPnl), 0)}`}
                        color={pnlColor(unrealizedPnl)}
                    />
                    <MiniRow
                        label="Trades Today"
                        value={String(positions.length)}
                        color="var(--text-secondary)"
                    />
                    {riskStats && (
                        <MiniRow
                            label="Loss Limit"
                            value={`₹${fmt(Math.abs(riskStats.daily_pnl), 0)} / ₹${fmt(riskStats.daily_loss_limit, 0)}`}
                            color={
                                !riskStats.is_trading_allowed
                                    ? 'var(--color-loss-text)'
                                    : 'var(--text-secondary)'
                            }
                        />
                    )}
                </div>
            </Card>

            {/* ── 4. Order Flow / OI ── */}
            <Card compact className="!p-3">
                <div className="label mb-2 flex items-center gap-1.5">
                    <span style={{ fontSize: 13 }}>&#x1F4CA;</span>
                    Order Flow
                </div>

                <div className="mb-2">
                    <span
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border"
                        style={{
                            color: oiColor,
                            borderColor: oiColor,
                            backgroundColor: `color-mix(in srgb, ${oiColor} 10%, transparent)`,
                        }}
                    >
                        <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: oiColor }} />
                        {oiSignal.replace(/_/g, ' ')}
                    </span>
                </div>

                <div className="space-y-1">
                    <MiniRow
                        label="OI Change"
                        value={oi?.oi_change_pct != null ? `${oi.oi_change_pct.toFixed(1)}%` : '--'}
                        color="var(--text-secondary)"
                    />
                    {orderBook && (
                        <>
                            <MiniRow
                                label="CE Bid Flow"
                                value={orderBook.ce_imbalance != null ? orderBook.ce_imbalance.toFixed(2) : '--'}
                                color={
                                    (orderBook.ce_imbalance ?? 0) > 1
                                        ? 'var(--color-profit-text)'
                                        : 'var(--text-secondary)'
                                }
                            />
                            <MiniRow
                                label="Entry Quality"
                                value={`${orderBook.entry_quality}/10`}
                                color={
                                    orderBook.entry_quality >= 7
                                        ? 'var(--color-profit-text)'
                                        : orderBook.entry_quality >= 4
                                            ? 'var(--color-warning)'
                                            : 'var(--color-loss-text)'
                                }
                            />
                        </>
                    )}
                    {pcrAnalysis?.pcr != null && (
                        <MiniRow
                            label="PCR"
                            value={pcrAnalysis.pcr.toFixed(2)}
                            color={
                                pcrAnalysis.pcr > 1.3
                                    ? 'var(--color-profit-text)'
                                    : pcrAnalysis.pcr < 0.7
                                        ? 'var(--color-loss-text)'
                                        : 'var(--color-warning)'
                            }
                        />
                    )}
                </div>
            </Card>

            {/* ── 5. Active Positions (spans full width) ── */}
            <Card compact className="!p-3 col-span-2">
                <div className="label mb-2 flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                        <span style={{ fontSize: 13 }}>&#x1F4BC;</span>
                        Active Positions
                    </span>
                    <span className="mono text-xs text-[var(--text-secondary)]">
                        {positions.length} open
                    </span>
                </div>

                {positions.length === 0 ? (
                    <div className="text-[11px] text-[var(--text-muted)] py-2 text-center">
                        No open positions
                    </div>
                ) : (
                    <div className="space-y-1.5">
                        {positions.slice(0, 4).map((pos) => {
                            // Use backend-computed P&L (handles BUY/SELL correctly)
                            // Fallback to simple BUY calculation for legacy positions
                            const unrealized = (pos as any).unrealized_pnl
                                ?? (((pos as any).current_price - pos.entry_price) * pos.quantity);
                            const unrealizedPct = (pos as any).unrealized_pnl_pct
                                ?? (pos.entry_price > 0
                                    ? (((pos as any).current_price - pos.entry_price) / pos.entry_price) * 100
                                    : 0);
                            return (
                                <div
                                    key={pos.id}
                                    className="flex items-center justify-between px-2 py-1.5 rounded-md bg-[var(--bg-overlay)]"
                                >
                                    <div className="flex items-center gap-2">
                                        <span
                                            className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                                            style={{
                                                color:
                                                    pos.position_type === 'CE'
                                                        ? 'var(--color-profit-text)'
                                                        : 'var(--color-loss-text)',
                                                background:
                                                    pos.position_type === 'CE'
                                                        ? 'rgba(34,197,94,0.12)'
                                                        : 'rgba(239,68,68,0.12)',
                                            }}
                                        >
                                            {pos.position_type}
                                        </span>
                                        <span className="mono text-xs text-[var(--text-secondary)]">
                                            {fmt(pos.entry_price, 1)}
                                        </span>
                                        <span className="text-[10px] text-[var(--text-muted)]">
                                            x{pos.quantity}
                                        </span>
                                    </div>
                                    <div className="text-right">
                                        <span className="mono text-xs font-bold" style={{ color: pnlColor(unrealized) }}>
                                            {pnlSign(unrealized)}{fmt(unrealized, 0)}
                                        </span>
                                        <span className="mono text-[10px] ml-1" style={{ color: pnlColor(unrealizedPct) }}>
                                            ({pnlSign(unrealizedPct)}{fmt(unrealizedPct, 1)}%)
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                        {positions.length > 4 && (
                            <div className="text-[10px] text-[var(--text-muted)] text-center">
                                +{positions.length - 4} more
                            </div>
                        )}
                    </div>
                )}
            </Card>
        </div>
    );
});

MarketSnapshotDashboard.displayName = 'MarketSnapshotDashboard';

/* ── Sub-components ── */

const LevelRow: React.FC<{
    label: string;
    value: number | null | undefined;
    current: number;
    color: string;
    subtle?: boolean;
}> = ({ label, value, current, color, subtle }) => {
    const distance =
        value != null && current > 0
            ? (((value - current) / current) * 100).toFixed(1)
            : null;

    return (
        <div className="flex items-center justify-between">
            <span className={`text-[10px] ${subtle ? 'text-[var(--text-muted)]' : 'text-[var(--text-tertiary)]'}`}>
                {label}
            </span>
            <div className="flex items-center gap-2">
                <span className="mono text-xs font-semibold" style={{ color }}>
                    {value != null ? value.toFixed(0) : '--'}
                </span>
                {distance && (
                    <span className="mono text-[10px] text-[var(--text-muted)]">
                        {Number(distance) > 0 ? '+' : ''}{distance}%
                    </span>
                )}
            </div>
        </div>
    );
};

const MiniRow: React.FC<{
    label: string;
    value: string;
    color: string;
}> = ({ label, value, color }) => (
    <div className="flex items-center justify-between">
        <span className="text-[10px] text-[var(--text-tertiary)]">{label}</span>
        <span className="mono text-[11px] font-semibold" style={{ color }}>{value}</span>
    </div>
);

export default MarketSnapshotDashboard;
