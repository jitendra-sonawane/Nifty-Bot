import React from 'react';
import Card from '../../shared/Card';
import { TrendingUp, TrendingDown, AlertCircle } from 'lucide-react';

interface SRProps {
    supportResistance?: any;
    breakout?: any;
    currentPrice: number;
}

const SupportResistance: React.FC<SRProps> = React.memo(({ supportResistance, breakout, currentPrice }) => {
    const sr = supportResistance || {};
    const nearS = sr.nearest_support;
    const nearR = sr.nearest_resistance;
    const displayPrice = currentPrice || sr.current_price || 0;

    const sDist = nearS && displayPrice > 0 ? ((displayPrice - nearS) / displayPrice * 100).toFixed(2) : null;
    const rDist = nearR && displayPrice > 0 ? ((nearR - displayPrice) / displayPrice * 100).toFixed(2) : null;

    const isBreakout = breakout?.is_breakout;
    const bType = breakout?.breakout_type;

    return (
        <Card compact>
            <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium">Support / Resistance</span>
                {isBreakout && (
                    <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${bType === 'UPSIDE'
                                ? 'bg-[var(--color-profit-muted)] text-[var(--color-profit-text)]'
                                : 'bg-[var(--color-loss-muted)] text-[var(--color-loss-text)]'
                            }`}
                    >
                        🔥 {bType} BREAKOUT
                    </span>
                )}
            </div>

            <div className="grid grid-cols-2 gap-2">
                {/* Support */}
                <div className="surface !rounded-md p-2.5 border-l-2 border-l-[var(--ce-color)]">
                    <div className="flex items-center gap-1.5 mb-1">
                        <TrendingUp size={12} className="text-[var(--color-profit-text)]" />
                        <span className="label">Support</span>
                    </div>
                    <div className="mono text-sm font-bold text-[var(--color-profit-text)]">
                        {nearS ? `₹${nearS.toFixed(1)}` : '--'}
                    </div>
                    {sDist && (
                        <div className="text-[10px] text-[var(--text-muted)] mono mt-0.5">
                            -{sDist}%
                        </div>
                    )}
                </div>

                {/* Resistance */}
                <div className="surface !rounded-md p-2.5 border-l-2 border-l-[var(--pe-color)]">
                    <div className="flex items-center gap-1.5 mb-1">
                        <TrendingDown size={12} className="text-[var(--color-loss-text)]" />
                        <span className="label">Resistance</span>
                    </div>
                    <div className="mono text-sm font-bold text-[var(--color-loss-text)]">
                        {nearR ? `₹${nearR.toFixed(1)}` : '--'}
                    </div>
                    {rDist && (
                        <div className="text-[10px] text-[var(--text-muted)] mono mt-0.5">
                            +{rDist}%
                        </div>
                    )}
                </div>
            </div>

            {/* Range */}
            {nearS && nearR && (
                <div className="mt-2 text-[10px] text-[var(--text-muted)] text-center mono">
                    Range: ₹{(nearR - nearS).toFixed(1)}
                </div>
            )}
        </Card>
    );
});

SupportResistance.displayName = 'SupportResistance';
export default SupportResistance;
