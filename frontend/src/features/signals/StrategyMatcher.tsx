import React, { useState } from 'react';
import Card from '../../shared/Card';

interface StrategyMatcherProps {
    strategyData?: any;
    signal?: string;
}

interface StrategyFit {
    id: string;
    name: string;
    type: 'debit' | 'credit';
    fitScore: number;
    reason: string;
    direction: 'bullish' | 'bearish' | 'neutral';
}

function calculateFitScores(data: any, signal: string): StrategyFit[] {
    if (!data || Object.keys(data).length === 0) {
        return getDefaultStrategies();
    }

    const supertrend = data.supertrend || '';
    const rsi = data.rsi ?? 50;
    const ema5 = data.ema_5 ?? 0;
    const ema20 = data.ema_20 ?? 0;
    const atrPct = data.atr_pct ?? 0;
    const filters = data.filters || {};
    const breakout = data.breakout || {};
    const volatilityOk = filters.volatility ?? false;

    const isBullish = supertrend === 'BULLISH';
    const isBearish = supertrend === 'BEARISH';
    const emaBullish = ema5 > ema20;
    const emaBearish = ema5 < ema20;
    const isRangebound = rsi >= 40 && rsi <= 60;
    const hasBreakout = breakout.is_breakout ?? false;

    // Bull Call Spread
    let bullCallScore = 0;
    let bullCallReason = '';
    if (isBullish) bullCallScore += 30;
    if (rsi > 55) bullCallScore += 25;
    if (emaBullish) bullCallScore += 25;
    if (volatilityOk) bullCallScore += 20;
    if (bullCallScore >= 70) bullCallReason = 'Strong bullish momentum';
    else if (bullCallScore >= 40) bullCallReason = 'Partial bullish signals';
    else bullCallReason = 'Not enough bullish alignment';

    // Bear Put Spread
    let bearPutScore = 0;
    let bearPutReason = '';
    if (isBearish) bearPutScore += 30;
    if (rsi < 45) bearPutScore += 25;
    if (emaBearish) bearPutScore += 25;
    if (volatilityOk) bearPutScore += 20;
    if (bearPutScore >= 70) bearPutReason = 'Strong bearish momentum';
    else if (bearPutScore >= 40) bearPutReason = 'Partial bearish signals';
    else bearPutReason = 'Not enough bearish alignment';

    // Iron Condor
    let ironCondorScore = 0;
    let ironCondorReason = '';
    if (isRangebound) ironCondorScore += 35;
    if (!hasBreakout) ironCondorScore += 25;
    if (volatilityOk) ironCondorScore += 20;
    if (atrPct > 0 && atrPct < 1.0) ironCondorScore += 20;
    if (ironCondorScore >= 70) ironCondorReason = 'Range-bound, ideal for selling';
    else if (ironCondorScore >= 40) ironCondorReason = 'Moderate range, some risk';
    else ironCondorReason = 'Too directional for range strategy';

    // Short Straddle
    let straddleScore = 0;
    let straddleReason = '';
    if (isRangebound) straddleScore += 30;
    if (!hasBreakout) straddleScore += 20;
    if (atrPct > 0 && atrPct < 0.8) straddleScore += 25;
    if (volatilityOk) straddleScore += 25;
    if (straddleScore >= 70) straddleReason = 'Low movement expected, theta play';
    else if (straddleScore >= 40) straddleReason = 'Some range but risky';
    else straddleReason = 'Too volatile for straddle selling';

    // Breakout
    let breakoutScore = 0;
    let breakoutReason = '';
    if (hasBreakout) {
        breakoutScore += 40;
        breakoutReason = `${breakout.breakout_type} breakout detected`;
    }
    if (volatilityOk) breakoutScore += 20;
    if (atrPct > 0.3) breakoutScore += 20;
    if ((isBullish && breakout.breakout_type === 'UPSIDE') ||
        (isBearish && breakout.breakout_type === 'DOWNSIDE')) {
        breakoutScore += 20;
    }
    if (!hasBreakout) breakoutReason = 'No breakout detected';
    else if (breakoutScore >= 70) breakoutReason = `Strong ${breakout.breakout_type} breakout`;

    const strategies: StrategyFit[] = [
        { id: 'bull_call', name: 'Bull Call Spread', type: 'debit', fitScore: bullCallScore, reason: bullCallReason, direction: 'bullish' },
        { id: 'bear_put', name: 'Bear Put Spread', type: 'debit', fitScore: bearPutScore, reason: bearPutReason, direction: 'bearish' },
        { id: 'iron_condor', name: 'Iron Condor', type: 'credit', fitScore: ironCondorScore, reason: ironCondorReason, direction: 'neutral' },
        { id: 'short_straddle', name: 'Short Straddle', type: 'credit', fitScore: straddleScore, reason: straddleReason, direction: 'neutral' },
        { id: 'breakout', name: 'Breakout', type: 'debit', fitScore: breakoutScore, reason: breakoutReason, direction: hasBreakout ? (breakout.breakout_type === 'UPSIDE' ? 'bullish' : 'bearish') : 'neutral' },
    ];

    // Sort by fit score descending
    return strategies.sort((a, b) => b.fitScore - a.fitScore);
}

function getDefaultStrategies(): StrategyFit[] {
    return [
        { id: 'bull_call', name: 'Bull Call Spread', type: 'debit', fitScore: 0, reason: 'Waiting for data...', direction: 'neutral' },
        { id: 'bear_put', name: 'Bear Put Spread', type: 'debit', fitScore: 0, reason: 'Waiting for data...', direction: 'neutral' },
        { id: 'iron_condor', name: 'Iron Condor', type: 'credit', fitScore: 0, reason: 'Waiting for data...', direction: 'neutral' },
        { id: 'short_straddle', name: 'Short Straddle', type: 'credit', fitScore: 0, reason: 'Waiting for data...', direction: 'neutral' },
        { id: 'breakout', name: 'Breakout', type: 'debit', fitScore: 0, reason: 'Waiting for data...', direction: 'neutral' },
    ];
}

const directionDotColor = {
    bullish: 'bg-[var(--color-profit)]',
    bearish: 'bg-[var(--color-loss)]',
    neutral: 'bg-[var(--text-muted)]',
};

const fitBarColor = (score: number) => {
    if (score >= 70) return 'bg-[var(--color-profit)]';
    if (score >= 40) return 'bg-[var(--color-warning)]';
    return 'bg-[var(--text-muted)]';
};

const fitTextColor = (score: number) => {
    if (score >= 70) return 'text-[var(--color-profit-text)]';
    if (score >= 40) return 'text-[var(--color-warning)]';
    return 'text-[var(--text-muted)]';
};

const StrategyMatcher: React.FC<StrategyMatcherProps> = ({ strategyData, signal }) => {
    const strategies = calculateFitScores(strategyData, signal || '');
    const [expanded, setExpanded] = useState(false);

    // Show top 3 by default, all 5 when expanded
    const visible = expanded ? strategies : strategies.slice(0, 3);
    const best = strategies[0];

    return (
        <Card compact>
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold">Strategy Matcher</span>
                {best && best.fitScore >= 70 && (
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[rgba(34,197,94,0.12)] text-[var(--color-profit-text)] border border-[rgba(34,197,94,0.25)]">
                        BEST FIT
                    </span>
                )}
            </div>

            {/* Strategy Rows */}
            <div className="space-y-1.5">
                {visible.map((strategy, i) => (
                    <div
                        key={strategy.id}
                        className={`rounded-md px-2.5 py-2 border transition-all duration-300 animate-fade-in ${i === 0 && strategy.fitScore >= 70
                                ? 'bg-[rgba(34,197,94,0.06)] border-[rgba(34,197,94,0.2)]'
                                : 'bg-[var(--bg-hover)] border-[var(--border-subtle)]'
                            }`}
                        style={{ animationDelay: `${i * 40}ms` }}
                    >
                        {/* Row 1: Name + Score */}
                        <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-2">
                                <span className={`w-2 h-2 rounded-full ${directionDotColor[strategy.direction]}`} />
                                <span className="text-[11px] font-semibold text-[var(--text-primary)]">
                                    {strategy.name}
                                </span>
                                <span className="text-[9px] px-1.5 py-0.5 rounded bg-[var(--bg-overlay)] text-[var(--text-muted)] font-medium uppercase">
                                    {strategy.type}
                                </span>
                            </div>
                            <span className={`mono text-xs font-bold ${fitTextColor(strategy.fitScore)}`}>
                                {strategy.fitScore}%
                            </span>
                        </div>

                        {/* Fit Bar */}
                        <div className="h-1 rounded-full bg-[var(--bg-overlay)] overflow-hidden mb-1">
                            <div
                                className={`h-1 rounded-full transition-all duration-700 ease-out ${fitBarColor(strategy.fitScore)}`}
                                style={{ width: `${strategy.fitScore}%` }}
                            />
                        </div>

                        {/* Reason */}
                        <div className="text-[10px] text-[var(--text-muted)]">
                            {strategy.reason}
                        </div>
                    </div>
                ))}
            </div>

            {/* Expand/Collapse */}
            {strategies.length > 3 && (
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="w-full mt-2 pt-1.5 text-[10px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors text-center"
                >
                    {expanded ? '▲ Show less' : `▼ Show ${strategies.length - 3} more`}
                </button>
            )}
        </Card>
    );
};

export default StrategyMatcher;
