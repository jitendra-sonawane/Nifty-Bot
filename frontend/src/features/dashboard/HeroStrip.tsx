import React from 'react';
import Badge, { getSignalVariant } from '../../shared/Badge';
import ProgressBar from '../../shared/ProgressBar';
import Sparkline from '../../shared/Sparkline';
import type {
    IntelligenceContext,
    Position,
    PricePoint,
    ReasoningData,
} from '../../types/api';

/* ── Props ── */
interface HeroStripProps {
    signal: string;
    reasoning?: ReasoningData;
    positions?: Position[];
    pnl?: { daily: number; unrealized: number };
    priceHistory: PricePoint[];
    strategyData?: any;
    intelligence?: IntelligenceContext;
    pcrAnalysis?: any;
    sentiment?: any;
}

/* ── Helpers ── */
const fmt = (n: number | null | undefined, d = 0) =>
    n != null ? n.toFixed(d) : '--';

const pnlColor = (v: number) =>
    v > 0 ? 'var(--color-profit-text)' : v < 0 ? 'var(--color-loss-text)' : 'var(--text-secondary)';

const pnlSign = (v: number) => (v > 0 ? '+' : '');

/* ── Pipeline Dot helpers ── */
type DotStatus = 'passed' | 'partial' | 'failed';

const dotColors: Record<DotStatus, string> = {
    passed: 'bg-[var(--color-profit)]',
    partial: 'bg-[var(--color-warning)]',
    failed: 'bg-[var(--bg-overlay)]',
};

function derivePipelineDots(data: any): DotStatus[] {
    if (!data || Object.keys(data).length === 0) {
        return ['failed', 'failed', 'failed', 'failed', 'failed'];
    }

    const filters = data.filters || {};
    const supertrend = data.supertrend || '';
    const rsi = data.rsi ?? 0;
    const ema5 = data.ema_5 ?? 0;
    const ema20 = data.ema_20 ?? 0;
    const pcr = data.pcr;

    const isBullish = supertrend === 'BULLISH';
    const isBearish = supertrend === 'BEARISH';

    // TREND
    const trend: DotStatus = (isBullish || isBearish) ? 'passed' : 'failed';

    // MOMENTUM
    const emaBullish = ema5 > ema20;
    const emaBearish = ema5 < ema20;
    const rsiBullish = rsi >= 50;
    const rsiBearish = rsi <= 50;
    const momentumAligned = (isBullish && emaBullish && rsiBullish) ||
        (isBearish && emaBearish && rsiBearish);
    const momentumPartial = (emaBullish || emaBearish) && !momentumAligned;
    const momentum: DotStatus = momentumAligned ? 'passed' : momentumPartial ? 'partial' : 'failed';

    // VOLATILITY
    const volatility: DotStatus = filters.volatility ? 'passed' : 'failed';

    // CONFIRMED
    const confirmed: DotStatus = filters.entry_confirmation ? 'passed' : 'failed';

    // SENTIMENT
    const isPcrAligned = (isBullish && pcr >= 1.0) || (isBearish && pcr < 1.0);
    const pcrPassed = pcr != null ? isPcrAligned : false;
    const greeksPassed = filters.greeks ?? false;
    const sentiment: DotStatus = (pcrPassed && greeksPassed) ? 'passed' : (pcrPassed || greeksPassed) ? 'partial' : 'failed';

    return [trend, momentum, volatility, confirmed, sentiment];
}

const dotLabels = ['T', 'M', 'V', 'C', 'S'];

/* ── Buildup display ── */
const buildupDisplay: Record<string, { text: string; color: string }> = {
    LONG_BUILDUP: { text: 'LB', color: 'var(--color-profit-text)' },
    SHORT_COVERING: { text: 'SC', color: 'var(--color-profit-text)' },
    SHORT_BUILDUP: { text: 'SB', color: 'var(--color-loss-text)' },
    LONG_UNWINDING: { text: 'LU', color: 'var(--color-loss-text)' },
    NEUTRAL: { text: '--', color: 'var(--text-muted)' },
};

/* ════════════════════════════════════
   HERO STRIP COMPONENT
   ════════════════════════════════════ */
const HeroStrip: React.FC<HeroStripProps> = React.memo(({
    signal,
    reasoning,
    positions = [],
    pnl,
    priceHistory,
    strategyData,
    intelligence,
    pcrAnalysis,
    sentiment,
}) => {
    const confidence = reasoning?.confidence ?? 0;
    const rationale = reasoning?.trade_rationale || '';

    // P&L
    const dailyPnl = pnl?.daily ?? 0;
    const unrealizedPnl = pnl?.unrealized ?? 0;
    const totalPnl = dailyPnl + unrealizedPnl;
    const activePosition = positions.length > 0 ? positions[0] : null;

    // SL distance
    const slDistance = activePosition && activePosition.current_price && activePosition.stop_loss
        ? (((activePosition.current_price - activePosition.stop_loss) / activePosition.current_price) * 100)
        : null;

    // Pipeline dots
    const dots = derivePipelineDots(strategyData);

    // Market Pulse
    const regime = intelligence?.market_regime;
    const ivRank = intelligence?.iv_rank;
    const oiData = intelligence?.oi_analysis;
    const buildup = buildupDisplay[oiData?.buildup_signal ?? 'NEUTRAL'] ?? buildupDisplay.NEUTRAL;

    const rsi = strategyData?.rsi;
    const pcr = pcrAnalysis?.pcr;
    const vix = sentiment?.vix ?? pcrAnalysis?.vix;

    // Sparkline data
    const sparkData = priceHistory.map((p: PricePoint) => p.price);

    // Signal accent border color
    const signalBorderColor = signal === 'BUY_CE' ? 'var(--color-profit)'
        : signal === 'BUY_PE' ? 'var(--color-loss)'
            : signal === 'HOLD' ? 'var(--text-muted)'
                : 'var(--accent-cyan)';

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            {/* ── Card 1: Signal State ── */}
            <div
                className="surface-elevated p-3 rounded-xl"
                style={{ borderLeft: `3px solid ${signalBorderColor}` }}
            >
                <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider">Signal</span>
                    <Badge variant={getSignalVariant(signal)} size="sm" dot>
                        {signal}
                    </Badge>
                </div>

                {/* Confidence */}
                <div className="flex items-center gap-2 mb-2">
                    <span
                        className={`mono text-lg font-bold ${confidence >= 70
                            ? 'text-[var(--color-profit-text)]'
                            : confidence >= 40
                                ? 'text-[var(--color-warning)]'
                                : 'text-[var(--color-loss-text)]'
                            }`}
                    >
                        {confidence.toFixed(0)}%
                    </span>
                    <div className="flex-1">
                        <ProgressBar value={confidence} color="auto" height="sm" />
                    </div>
                </div>

                {/* Pipeline mini dots */}
                <div className="flex items-center gap-1 mb-1.5">
                    {dots.map((status, i) => (
                        <div key={i} className="flex items-center gap-0.5">
                            <div
                                className={`w-2 h-2 rounded-full ${dotColors[status]}`}
                                title={`${dotLabels[i]}: ${status}`}
                            />
                            {i < dots.length - 1 && (
                                <div className="w-1.5 h-px bg-[var(--border-subtle)]" />
                            )}
                        </div>
                    ))}
                    <span className="text-[9px] text-[var(--text-muted)] ml-1">
                        {dots.filter(d => d === 'passed').length}/{dots.length}
                    </span>
                </div>

                {/* Rationale */}
                {rationale && (
                    <p className="text-[10px] text-[var(--text-tertiary)] line-clamp-1 leading-relaxed">
                        {rationale}
                    </p>
                )}
            </div>

            {/* ── Card 2: Position & P&L ── */}
            <div
                className="surface-elevated p-3 rounded-xl"
                style={{ borderLeft: `3px solid ${pnlColor(totalPnl)}` }}
            >
                <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider">Position</span>
                    {sparkData.length >= 2 && (
                        <Sparkline data={sparkData} width={64} height={20} />
                    )}
                </div>

                {/* Total P&L */}
                <div
                    className="mono text-xl font-bold mb-1"
                    style={{ color: pnlColor(totalPnl) }}
                >
                    {pnlSign(totalPnl)}₹{fmt(Math.abs(totalPnl), 0)}
                </div>

                {/* Active position row */}
                {activePosition ? (
                    <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-1.5">
                            <span
                                className="text-[9px] font-bold px-1 py-0.5 rounded"
                                style={{
                                    color: activePosition.position_type === 'CE' ? 'var(--color-profit-text)' : 'var(--color-loss-text)',
                                    background: activePosition.position_type === 'CE' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
                                }}
                            >
                                {activePosition.position_type}
                            </span>
                            <span className="mono text-[10px] text-[var(--text-secondary)]">
                                ₹{fmt(activePosition.entry_price, 1)}
                            </span>
                            <span className="text-[9px] text-[var(--text-muted)]">x{activePosition.quantity}</span>
                        </div>
                        {slDistance != null && (
                            <span className="mono text-[10px] text-[var(--color-loss-text)]">
                                SL: {slDistance.toFixed(1)}%
                            </span>
                        )}
                    </div>
                ) : (
                    <div className="text-[10px] text-[var(--text-muted)] mb-1">No open positions</div>
                )}

                {/* Daily stats */}
                <div className="flex items-center gap-3 text-[10px]">
                    <span className="text-[var(--text-muted)]">
                        Real: <span className="mono" style={{ color: pnlColor(dailyPnl) }}>{pnlSign(dailyPnl)}₹{fmt(Math.abs(dailyPnl), 0)}</span>
                    </span>
                    <span className="text-[var(--text-muted)]">
                        Unreal: <span className="mono" style={{ color: pnlColor(unrealizedPnl) }}>{pnlSign(unrealizedPnl)}₹{fmt(Math.abs(unrealizedPnl), 0)}</span>
                    </span>
                </div>
            </div>

            {/* ── Card 3: Market Pulse ── */}
            <div
                className="surface-elevated p-3 rounded-xl"
                style={{
                    borderLeft: `3px solid ${regime?.regime === 'TRENDING' ? 'var(--accent-blue)'
                        : regime?.regime === 'HIGH_VOLATILITY' ? 'var(--color-warning)'
                            : 'var(--text-muted)'}`,
                }}
            >
                <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider">Market Pulse</span>
                    {regime?.regime && (
                        <span
                            className="text-[9px] font-bold px-1.5 py-0.5 rounded-full border"
                            style={{
                                color: regime.regime === 'TRENDING' ? 'var(--accent-blue)'
                                    : regime.regime === 'HIGH_VOLATILITY' ? 'var(--color-warning)'
                                        : 'var(--text-secondary)',
                                borderColor: regime.regime === 'TRENDING' ? 'rgba(59,130,246,0.3)'
                                    : regime.regime === 'HIGH_VOLATILITY' ? 'rgba(245,158,11,0.3)'
                                        : 'var(--border-default)',
                                background: regime.regime === 'TRENDING' ? 'rgba(59,130,246,0.1)'
                                    : regime.regime === 'HIGH_VOLATILITY' ? 'rgba(245,158,11,0.1)'
                                        : 'var(--bg-overlay)',
                            }}
                        >
                            {regime.regime}
                        </span>
                    )}
                </div>

                {/* RSI + OI row */}
                <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-1">
                        <span className="text-[9px] text-[var(--text-muted)]">RSI</span>
                        <span
                            className="mono text-xs font-bold"
                            style={{
                                color: rsi != null
                                    ? rsi > 70 ? 'var(--color-loss-text)' : rsi < 30 ? 'var(--color-profit-text)' : 'var(--color-warning)'
                                    : 'var(--text-muted)',
                            }}
                        >
                            {rsi != null ? rsi.toFixed(0) : '--'}
                        </span>
                    </div>
                    <div className="flex items-center gap-1">
                        <span className="text-[9px] text-[var(--text-muted)]">OI</span>
                        <span className="mono text-[10px] font-bold" style={{ color: buildup.color }}>
                            {buildup.text}
                        </span>
                    </div>
                </div>

                {/* PCR + VIX row */}
                <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-1">
                        <span className="text-[9px] text-[var(--text-muted)]">PCR</span>
                        <span
                            className="mono text-xs font-bold"
                            style={{
                                color: pcr != null
                                    ? pcr > 1.2 ? 'var(--color-profit-text)' : pcr < 0.8 ? 'var(--color-loss-text)' : 'var(--color-warning)'
                                    : 'var(--text-muted)',
                            }}
                        >
                            {pcr != null ? Number(pcr).toFixed(2) : '--'}
                        </span>
                    </div>
                    <div className="flex items-center gap-1">
                        <span className="text-[9px] text-[var(--text-muted)]">VIX</span>
                        <span
                            className="mono text-xs font-bold"
                            style={{
                                color: vix != null
                                    ? vix > 20 ? 'var(--color-loss-text)' : vix < 15 ? 'var(--color-profit-text)' : 'var(--color-warning)'
                                    : 'var(--text-muted)',
                            }}
                        >
                            {vix != null ? Number(vix).toFixed(1) : '--'}
                        </span>
                    </div>
                </div>

                {/* IV Rank bar */}
                <div className="flex items-center gap-2">
                    <span className="text-[9px] text-[var(--text-muted)]">IVR</span>
                    <div className="flex-1 h-1 rounded-full bg-[var(--bg-overlay)] overflow-hidden">
                        <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{
                                width: `${Math.min(Math.max(ivRank?.iv_rank ?? 0, 0), 100)}%`,
                                background: (ivRank?.iv_rank ?? 0) >= 50 ? 'var(--color-profit)' : (ivRank?.iv_rank ?? 0) < 20 ? 'var(--color-loss)' : 'var(--color-warning)',
                            }}
                        />
                    </div>
                    <span
                        className="mono text-[10px] font-bold min-w-[2rem] text-right"
                        style={{
                            color: (ivRank?.iv_rank ?? 0) >= 50 ? 'var(--color-profit-text)' : (ivRank?.iv_rank ?? 0) < 20 ? 'var(--color-loss-text)' : 'var(--color-warning)',
                        }}
                    >
                        {ivRank?.iv_rank != null ? `${ivRank.iv_rank.toFixed(0)}%` : '--'}
                    </span>
                </div>
            </div>
        </div>
    );
});

HeroStrip.displayName = 'HeroStrip';
export default HeroStrip;
