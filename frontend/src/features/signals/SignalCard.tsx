import React from 'react';
import Card from '../../shared/Card';
import Badge, { getSignalVariant } from '../../shared/Badge';
import ProgressBar from '../../shared/ProgressBar';

interface SignalCardProps {
    signal: string;
    reasoning?: any;
    strategyData?: any;
}

const SignalCard: React.FC<SignalCardProps> = React.memo(({ signal, reasoning, strategyData }) => {
    const confidence = reasoning?.confidence ?? 0;
    const action = reasoning?.action ?? '⏸️ WAIT';
    const decisionReason = reasoning?.trade_rationale || '';
    const atmStrike = strategyData?.greeks?.atm_strike;

    return (
        <Card compact>
            <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Signal</span>
                <Badge variant={getSignalVariant(signal)} size="md" dot>
                    {signal}
                </Badge>
            </div>

            {/* Action + Confidence */}
            <div className="flex items-center justify-between mb-2">
                <span className="text-lg font-bold text-[var(--text-primary)]">{action}</span>
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
            </div>

            <ProgressBar value={confidence} color="auto" height="md" />

            {/* ATM Strike for buy signals */}
            {(signal === 'BUY_CE' || signal === 'BUY_PE') && atmStrike && (
                <div className="mt-2 flex items-center gap-2 px-2 py-1.5 rounded-md bg-[var(--accent-purple)]/10 border border-[var(--accent-purple)]/20">
                    <span className="text-[10px] text-[var(--text-tertiary)]">Strike:</span>
                    <span className="mono text-sm font-bold text-[var(--accent-purple)]">₹{atmStrike}</span>
                    <span className="text-[10px] text-[var(--text-muted)]">{signal === 'BUY_CE' ? 'CE' : 'PE'}</span>
                </div>
            )}

            {/* Brief reason */}
            {decisionReason && (
                <p className="text-[11px] text-[var(--text-tertiary)] mt-2 line-clamp-2 leading-relaxed">
                    {decisionReason}
                </p>
            )}

            {/* Setup Progress */}
            {strategyData?.progress && (
                <div className="mt-3 pt-3 border-t border-[var(--border-subtle)]">
                    <div className="flex justify-between items-center mb-1">
                        <span className="text-[10px] font-medium text-[var(--text-tertiary)]">Setup Progress</span>
                        <span className={`text-[10px] font-bold ${strategyData.progress.direction === 'BULLISH' ? 'text-[var(--color-profit-text)]' : 'text-[var(--color-loss-text)]'}`}>
                            {strategyData.progress.score}% ({strategyData.progress.direction})
                        </span>
                    </div>
                    <div className="w-full bg-[var(--bg-card-hover)] rounded-full h-1.5 overflow-hidden">
                        <div
                            className={`h-full rounded-full transition-all duration-500 ease-out ${strategyData.progress.direction === 'BULLISH' ? 'bg-[var(--color-profit)]' : 'bg-[var(--color-loss)]'}`}
                            style={{ width: `${strategyData.progress.score}%` }}
                        />
                    </div>
                    <div className="mt-1 text-[9px] text-[var(--text-muted)] text-right">
                        {strategyData.progress.passed_checks}/{strategyData.progress.required_checks} conditions met
                    </div>
                </div>
            )}
        </Card>
    );
});

SignalCard.displayName = 'SignalCard';
export default SignalCard;
