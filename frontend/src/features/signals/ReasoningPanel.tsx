import React, { useState } from 'react';
import Card from '../../shared/Card';
import { ChevronDown, ChevronUp, Shield, Target } from 'lucide-react';

interface ReasoningPanelProps {
    reasoning?: any;
    currentPrice: number;
}

const ReasoningPanel: React.FC<ReasoningPanelProps> = ({ reasoning = {}, currentPrice = 0 }) => {
    const [open, setOpen] = useState(false);

    const {
        key_factors = [],
        risk_factors = [],
        target_levels = {},
        stop_loss_levels = {},
        why_now = '',
        filter_summary = {},
    } = reasoning;

    const hasContent =
        key_factors.length > 0 ||
        risk_factors.length > 0 ||
        why_now ||
        Object.keys(filter_summary).length > 0;

    if (!hasContent) return null;

    return (
        <Card compact>
            <button
                onClick={() => setOpen(!open)}
                className="w-full flex items-center justify-between"
            >
                <span className="text-sm font-medium">AI Reasoning</span>
                {open ? (
                    <ChevronUp size={16} className="text-[var(--text-muted)]" />
                ) : (
                    <ChevronDown size={16} className="text-[var(--text-muted)]" />
                )}
            </button>

            {open && (
                <div className="mt-3 space-y-3 animate-fade-in">
                    {/* Why Now */}
                    {why_now && (
                        <div className="text-[11px] text-[var(--text-secondary)] leading-relaxed bg-[var(--bg-hover)] rounded-md p-2.5">
                            <span className="text-[var(--accent-purple)] font-semibold">Why now: </span>
                            {why_now}
                        </div>
                    )}

                    {/* Key Factors */}
                    {key_factors.length > 0 && (
                        <div>
                            <div className="label mb-1.5">Key Factors</div>
                            <div className="space-y-1">
                                {key_factors.map((f: string, i: number) => (
                                    <div key={i} className="text-[11px] text-[var(--text-secondary)] bg-[var(--bg-hover)] rounded-md px-2.5 py-1.5">
                                        {f}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Risk Factors */}
                    {risk_factors.length > 0 && (
                        <div>
                            <div className="label mb-1.5 text-[var(--color-loss-text)]">Risk Factors</div>
                            <div className="space-y-1">
                                {risk_factors.map((r: string, i: number) => (
                                    <div key={i} className="text-[11px] text-[var(--color-loss-text)] bg-[var(--color-loss-muted)] rounded-md px-2.5 py-1.5">
                                        ⚠ {r}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Target & SL */}
                    {(target_levels.primary || stop_loss_levels.primary) && (
                        <div className="grid grid-cols-2 gap-2">
                            {target_levels.primary && (
                                <div className="surface !rounded-md p-2 border-l-2 border-l-[var(--color-profit)]">
                                    <div className="flex items-center gap-1 mb-1">
                                        <Target size={11} className="text-[var(--color-profit-text)]" />
                                        <span className="label">Target</span>
                                    </div>
                                    <div className="mono text-sm font-bold text-[var(--color-profit-text)]">
                                        ₹{Number(target_levels.primary).toFixed(1)}
                                    </div>
                                </div>
                            )}
                            {stop_loss_levels.primary && (
                                <div className="surface !rounded-md p-2 border-l-2 border-l-[var(--color-loss)]">
                                    <div className="flex items-center gap-1 mb-1">
                                        <Shield size={11} className="text-[var(--color-loss-text)]" />
                                        <span className="label">Stop Loss</span>
                                    </div>
                                    <div className="mono text-sm font-bold text-[var(--color-loss-text)]">
                                        ₹{Number(stop_loss_levels.primary).toFixed(1)}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Filter Summary */}
                    {Object.keys(filter_summary).length > 0 && (
                        <div>
                            <div className="label mb-1.5">Filter Summary</div>
                            <div className="grid grid-cols-2 gap-1">
                                {Object.entries(filter_summary).map(([name, status]) => (
                                    <div key={name} className="flex items-center justify-between bg-[var(--bg-hover)] rounded-md px-2 py-1">
                                        <span className="text-[10px] text-[var(--text-tertiary)]">{name}</span>
                                        <span className={`text-[11px] font-bold ${status === '✅' ? 'text-[var(--color-profit-text)]' : 'text-[var(--color-loss-text)]'}`}>
                                            {status as string}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </Card>
    );
};

export default ReasoningPanel;
