import React from 'react';
import Card from '../../shared/Card';

interface SetupPipelineProps {
    strategyData?: any;
    signal?: string;
}

interface PipelineStage {
    id: string;
    label: string;
    icon: string;
    status: 'passed' | 'partial' | 'failed';
    detail: string;
    value?: string;
}

function deriveStages(data: any): PipelineStage[] {
    if (!data || Object.keys(data).length === 0) {
        return getDefaultStages();
    }

    const filters = data.filters || {};
    const supertrend = data.supertrend || '';
    const rsi = data.rsi ?? 0;
    const ema5 = data.ema_5 ?? 0;
    const ema20 = data.ema_20 ?? 0;
    const atrPct = data.atr_pct ?? 0;
    const pcr = data.pcr;
    const greeks = data.greeks;

    // 1. TREND — Supertrend direction
    const isBullish = supertrend === 'BULLISH';
    const isBearish = supertrend === 'BEARISH';
    const trendPassed = isBullish || isBearish;

    // 2. MOMENTUM — EMA crossover + RSI alignment
    const emaBullish = ema5 > ema20;
    const emaBearish = ema5 < ema20;
    const rsiBullish = rsi >= 50;
    const rsiBearish = rsi <= 50;
    const momentumAligned = (isBullish && emaBullish && rsiBullish) ||
        (isBearish && emaBearish && rsiBearish);
    const momentumPartial = (emaBullish || emaBearish) && !momentumAligned;

    // 3. VOLATILITY — ATR range
    const volatilityPassed = filters.volatility ?? false;

    // 4. CONFIRMATION — 2 candles confirmed
    const confirmPassed = filters.entry_confirmation ?? false;

    // 5. SENTIMENT — PCR + Greeks
    const pcrPassed = filters.pcr ?? false;
    const greeksPassed = filters.greeks ?? false;
    const sentimentPassed = pcrPassed && greeksPassed;
    const sentimentPartial = pcrPassed || greeksPassed;

    return [
        {
            id: 'trend',
            label: 'TREND',
            icon: trendPassed ? (isBullish ? '↑' : '↓') : '—',
            status: trendPassed ? 'passed' : 'failed',
            detail: supertrend || 'Waiting...',
            value: `Supertrend ${supertrend || '—'}`,
        },
        {
            id: 'momentum',
            label: 'MOMENTUM',
            icon: momentumAligned ? '⚡' : momentumPartial ? '~' : '—',
            status: momentumAligned ? 'passed' : momentumPartial ? 'partial' : 'failed',
            detail: `EMA ${ema5 > ema20 ? '↑' : '↓'}  RSI ${rsi?.toFixed?.(0) || '—'}`,
            value: `${ema5?.toFixed?.(0) || '—'} / ${ema20?.toFixed?.(0) || '—'}`,
        },
        {
            id: 'volatility',
            label: 'VOLATILITY',
            icon: volatilityPassed ? '✓' : '✗',
            status: volatilityPassed ? 'passed' : atrPct > 0 ? 'partial' : 'failed',
            detail: volatilityPassed ? `ATR ${atrPct?.toFixed?.(3) || '—'}% OK` : `ATR ${atrPct?.toFixed?.(3) || '—'}%`,
            value: atrPct > 2.5 ? 'Extreme' : atrPct < 0.01 ? 'Too Low' : 'In Range',
        },
        {
            id: 'confirmed',
            label: 'CONFIRMED',
            icon: confirmPassed ? '✓' : '—',
            status: confirmPassed ? 'passed' : 'failed',
            detail: confirmPassed ? '2 candles aligned' : 'Not yet confirmed',
            value: confirmPassed ? 'Yes' : 'No',
        },
        {
            id: 'sentiment',
            label: 'SENTIMENT',
            icon: sentimentPassed ? '✓' : sentimentPartial ? '~' : '—',
            status: sentimentPassed ? 'passed' : sentimentPartial ? 'partial' : 'failed',
            detail: `PCR ${pcr?.toFixed?.(2) || '—'}`,
            value: sentimentPassed ? 'Aligned' : getMissingSentiment(pcrPassed, greeksPassed),
        },
    ];
}

function getMissingSentiment(pcr: boolean, greeks: boolean): string {
    if (!pcr && !greeks) return 'Need PCR + Greeks';
    if (!pcr) return 'Need PCR';
    return 'Need Greeks';
}

function getDefaultStages(): PipelineStage[] {
    return [
        { id: 'trend', label: 'TREND', icon: '—', status: 'failed', detail: 'Waiting...', value: '—' },
        { id: 'momentum', label: 'MOMENTUM', icon: '—', status: 'failed', detail: 'Waiting...', value: '—' },
        { id: 'volatility', label: 'VOLATILITY', icon: '—', status: 'failed', detail: 'Waiting...', value: '—' },
        { id: 'confirmed', label: 'CONFIRMED', icon: '—', status: 'failed', detail: 'Waiting...', value: '—' },
        { id: 'sentiment', label: 'SENTIMENT', icon: '—', status: 'failed', detail: 'Waiting...', value: '—' },
    ];
}

function getDirection(data: any): { label: string; variant: 'bullish' | 'bearish' | 'neutral' } {
    const supertrend = data?.supertrend || '';
    const ema5 = data?.ema_5 ?? 0;
    const ema20 = data?.ema_20 ?? 0;

    if (supertrend === 'BULLISH' && ema5 > ema20) return { label: 'BULLISH BUILDING', variant: 'bullish' };
    if (supertrend === 'BEARISH' && ema5 < ema20) return { label: 'BEARISH BUILDING', variant: 'bearish' };
    if (supertrend === 'BULLISH' || supertrend === 'BEARISH') return { label: 'MIXED SIGNALS', variant: 'neutral' };
    return { label: 'SCANNING...', variant: 'neutral' };
}

const statusColors = {
    passed: {
        bg: 'bg-[rgba(34,197,94,0.1)]',
        border: 'border-[rgba(34,197,94,0.3)]',
        text: 'text-[var(--color-profit-text)]',
        dot: 'bg-[var(--color-profit)]',
        line: 'bg-[var(--color-profit)]',
    },
    partial: {
        bg: 'bg-[rgba(245,158,11,0.08)]',
        border: 'border-[rgba(245,158,11,0.25)]',
        text: 'text-[var(--color-warning)]',
        dot: 'bg-[var(--color-warning)]',
        line: 'bg-[var(--color-warning)]',
    },
    failed: {
        bg: 'bg-[var(--bg-hover)]',
        border: 'border-[var(--border-subtle)]',
        text: 'text-[var(--text-muted)]',
        dot: 'bg-[var(--text-muted)]',
        line: 'bg-[var(--border-subtle)]',
    },
};

const directionColors = {
    bullish: { badge: 'bg-[rgba(34,197,94,0.12)] text-[var(--color-profit-text)] border-[rgba(34,197,94,0.25)]', bar: 'bg-[var(--color-profit)]' },
    bearish: { badge: 'bg-[rgba(239,68,68,0.12)] text-[var(--color-loss-text)] border-[rgba(239,68,68,0.25)]', bar: 'bg-[var(--color-loss)]' },
    neutral: { badge: 'bg-[var(--bg-overlay)] text-[var(--text-secondary)] border-[var(--border-default)]', bar: 'bg-[var(--text-muted)]' },
};

const SetupPipeline: React.FC<SetupPipelineProps> = ({ strategyData, signal }) => {
    const stages = deriveStages(strategyData);
    const direction = getDirection(strategyData);
    const passedCount = stages.filter((s) => s.status === 'passed').length;
    const strength = Math.round((passedCount / stages.length) * 100);
    const allPassed = passedCount === stages.length;
    const missing = stages.filter((s) => s.status !== 'passed').map((s) => s.label);

    const isSignalActive = signal === 'BUY_CE' || signal === 'BUY_PE';

    return (
        <Card
            compact
            className={allPassed || isSignalActive ? 'animate-glow' : ''}
        >
            {/* Header */}
            <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold">Setup Formation</span>
                <span
                    className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-semibold rounded-full border ${directionColors[direction.variant].badge}`}
                >
                    <span className={`w-1.5 h-1.5 rounded-full ${direction.variant === 'bullish' ? 'bg-[var(--color-profit)]' : direction.variant === 'bearish' ? 'bg-[var(--color-loss)]' : 'bg-[var(--text-tertiary)]'}`} />
                    {direction.label}
                </span>
            </div>

            {/* Strength Bar */}
            <div className="flex items-center gap-2 mb-3">
                <div className="flex-1 h-1.5 rounded-full bg-[var(--bg-overlay)] overflow-hidden">
                    <div
                        className={`h-1.5 rounded-full transition-all duration-700 ease-out ${strength >= 80 ? 'bg-[var(--color-profit)]' : strength >= 50 ? 'bg-[var(--color-warning)]' : 'bg-[var(--color-loss)]'
                            }`}
                        style={{ width: `${strength}%` }}
                    />
                </div>
                <span className={`mono text-xs font-bold min-w-[2.5rem] text-right ${strength >= 80 ? 'text-[var(--color-profit-text)]' : strength >= 50 ? 'text-[var(--color-warning)]' : 'text-[var(--color-loss-text)]'
                    }`}>
                    {strength}%
                </span>
            </div>

            {/* Pipeline Stages */}
            <div className="relative">
                {stages.map((stage, i) => {
                    const colors = statusColors[stage.status];
                    const isLast = i === stages.length - 1;

                    return (
                        <div key={stage.id} className="relative flex items-start gap-2.5 animate-fade-in"
                            style={{ animationDelay: `${i * 60}ms` }}>
                            {/* Vertical Line + Dot */}
                            <div className="flex flex-col items-center flex-shrink-0" style={{ width: '16px' }}>
                                {/* Dot */}
                                <div className={`relative w-3 h-3 rounded-full ${colors.dot} flex-shrink-0 mt-0.5`}>
                                    {stage.status === 'passed' && (
                                        <span className="absolute inset-0 rounded-full animate-ping opacity-30 bg-[var(--color-profit)]" style={{ animationDuration: '3s' }} />
                                    )}
                                </div>
                                {/* Connecting line */}
                                {!isLast && (
                                    <div className={`w-px flex-1 min-h-[12px] ${colors.line} opacity-40 my-0.5`} />
                                )}
                            </div>

                            {/* Stage Card */}
                            <div className={`flex-1 rounded-md px-2.5 py-1.5 mb-1.5 border transition-all duration-300 ${colors.bg} ${colors.border}`}>
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-1.5">
                                        <span className={`text-[10px] font-bold tracking-wider ${colors.text}`}>
                                            {stage.label}
                                        </span>
                                    </div>
                                    <span className={`mono text-[10px] ${colors.text}`}>
                                        {stage.value}
                                    </span>
                                </div>
                                <div className={`text-[10px] mt-0.5 ${stage.status === 'passed' ? 'text-[var(--text-secondary)]' : 'text-[var(--text-muted)]'}`}>
                                    {stage.detail}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Footer Summary */}
            <div className="mt-1 pt-2 border-t border-[var(--border-subtle)]">
                {allPassed || isSignalActive ? (
                    <div className="flex items-center gap-2">
                        <span className="text-[11px] font-bold text-[var(--color-profit-text)]">
                            🚀 SETUP READY
                        </span>
                        <span className="mono text-[10px] text-[var(--color-profit-text)]">
                            — {signal || 'Signal Active'}
                        </span>
                    </div>
                ) : (
                    <div className="text-[10px] text-[var(--text-muted)]">
                        <span className="mono font-medium">{passedCount}/{stages.length}</span>
                        {' conditions met'}
                        {missing.length > 0 && (
                            <span> • Need: <span className="text-[var(--text-tertiary)]">{missing.join(', ')}</span></span>
                        )}
                    </div>
                )}
            </div>
        </Card>
    );
};

export default SetupPipeline;
