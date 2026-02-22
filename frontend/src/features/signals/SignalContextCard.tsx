import React, { useState } from 'react';
import Card from '../../shared/Card';
import Badge, { getSignalVariant } from '../../shared/Badge';
import ProgressBar from '../../shared/ProgressBar';
import SetupPipeline from './SetupPipeline';
import { ChevronDown, ChevronUp, Shield, Target } from 'lucide-react';

interface SignalContextCardProps {
    signal: string;
    reasoning?: any;
    strategyData?: any;
}

const SignalContextCard: React.FC<SignalContextCardProps> = React.memo(({ signal, reasoning, strategyData }) => {
    const [expanded, setExpanded] = useState(false);

    const confidence = reasoning?.confidence ?? 0;
    const action = reasoning?.action ?? '\u23F8\uFE0F WAIT';
    const whyNow = reasoning?.why_now || '';
    const decisionReason = reasoning?.trade_rationale || '';
    const atmStrike = strategyData?.greeks?.atm_strike;

    const keyFactors: string[] = reasoning?.key_factors ?? [];
    const riskFactors: string[] = reasoning?.risk_factors ?? [];
    const targetLevels = reasoning?.target_levels ?? {};
    const stopLossLevels = reasoning?.stop_loss_levels ?? {};

    const hasExpandContent = keyFactors.length > 0 || riskFactors.length > 0 || whyNow ||
        targetLevels.primary || stopLossLevels.primary || strategyData;

    return (
        <Card compact>
            {/* ── Header: Signal badge ── */}
            <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Signal</span>
                <Badge variant={getSignalVariant(signal)} size="md" dot>
                    {signal}
                </Badge>
            </div>

            {/* ── Action + Confidence ── */}
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

            {/* ── ATM Strike (buy signals only) ── */}
            {(signal === 'BUY_CE' || signal === 'BUY_PE') && atmStrike && (
                <div className="mt-2 flex items-center gap-2 px-2 py-1.5 rounded-md bg-[var(--accent-purple)]/10 border border-[var(--accent-purple)]/20">
                    <span className="text-[10px] text-[var(--text-tertiary)]">Strike:</span>
                    <span className="mono text-sm font-bold text-[var(--accent-purple)]">₹{atmStrike}</span>
                    <span className="text-[10px] text-[var(--text-muted)]">{signal === 'BUY_CE' ? 'CE' : 'PE'}</span>
                </div>
            )}

            {/* ── Why Now (brief, always visible) ── */}
            {(whyNow || decisionReason) && (
                <div className="mt-2 text-[11px] text-[var(--text-secondary)] leading-relaxed bg-[var(--bg-hover)] rounded-md px-2.5 py-1.5">
                    <span className="text-[var(--accent-purple)] font-semibold">Why: </span>
                    <span className="line-clamp-2">{whyNow || decisionReason}</span>
                </div>
            )}

            {/* ── Setup Progress ── */}
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

            {/* ── Expand/Collapse Toggle ── */}
            {hasExpandContent && (
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="w-full mt-3 pt-2 border-t border-[var(--border-subtle)] flex items-center justify-center gap-1 text-[11px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
                >
                    {expanded ? 'Hide Analysis' : 'Show Analysis'}
                    {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
            )}

            {/* ═══ EXPANDED CONTENT ═══ */}
            {expanded && (
                <div className="mt-3 space-y-3 animate-fade-in">
                    {/* Key Factors */}
                    {keyFactors.length > 0 && (
                        <div>
                            <div className="label mb-1.5">Key Factors</div>
                            <div className="space-y-1">
                                {keyFactors.map((f: string, i: number) => (
                                    <div key={i} className="text-[11px] text-[var(--text-secondary)] bg-[var(--bg-hover)] rounded-md px-2.5 py-1.5">
                                        {f}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Risk Factors */}
                    {riskFactors.length > 0 && (
                        <div>
                            <div className="label mb-1.5 text-[var(--color-loss-text)]">Risk Factors</div>
                            <div className="space-y-1">
                                {riskFactors.map((r: string, i: number) => (
                                    <div key={i} className="text-[11px] text-[var(--color-loss-text)] bg-[var(--color-loss-muted)] rounded-md px-2.5 py-1.5">
                                        ⚠ {r}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Target & Stop Loss */}
                    {(targetLevels.primary || stopLossLevels.primary) && (
                        <div className="grid grid-cols-2 gap-2">
                            {targetLevels.primary && (
                                <div className="surface !rounded-md p-2 border-l-2 border-l-[var(--color-profit)]">
                                    <div className="flex items-center gap-1 mb-1">
                                        <Target size={11} className="text-[var(--color-profit-text)]" />
                                        <span className="label">Target</span>
                                    </div>
                                    <div className="mono text-sm font-bold text-[var(--color-profit-text)]">
                                        ₹{Number(targetLevels.primary).toFixed(1)}
                                    </div>
                                </div>
                            )}
                            {stopLossLevels.primary && (
                                <div className="surface !rounded-md p-2 border-l-2 border-l-[var(--color-loss)]">
                                    <div className="flex items-center gap-1 mb-1">
                                        <Shield size={11} className="text-[var(--color-loss-text)]" />
                                        <span className="label">Stop Loss</span>
                                    </div>
                                    <div className="mono text-sm font-bold text-[var(--color-loss-text)]">
                                        ₹{Number(stopLossLevels.primary).toFixed(1)}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Full Setup Pipeline */}
                    <SetupPipeline strategyData={strategyData} signal={signal} />
                </div>
            )}
        </Card>
    );
});

SignalContextCard.displayName = 'SignalContextCard';
export default SignalContextCard;
