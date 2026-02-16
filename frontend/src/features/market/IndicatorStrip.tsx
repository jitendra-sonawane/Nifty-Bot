import React from 'react';
import Card from '../../shared/Card';

interface IndicatorStripProps {
    strategyData: any;
    currentPrice: number;
}

const IndicatorStrip: React.FC<IndicatorStripProps> = ({ strategyData, currentPrice }: IndicatorStripProps) => {
    const rsi = strategyData?.rsi ?? 0;
    const supertrend = strategyData?.supertrend ?? 'N/A';
    const ema5 = strategyData?.ema_5 ?? 0;
    const ema20 = strategyData?.ema_20 ?? 0;
    const greeks = strategyData?.greeks;
    const isBullEma = ema5 > ema20;

    // PDH/PDL/PDC
    const pdh = strategyData?.pdh_pdl_pdc?.pdh;
    const pdl = strategyData?.pdh_pdl_pdc?.pdl;
    const pdc = strategyData?.pdh_pdl_pdc?.pdc;
    const hasPDH = pdh != null && pdl != null;

    // Determine price position relative to previous day levels
    let pdhPdlSub = '';
    let pdhPdlColor = 'var(--text-secondary)';
    if (hasPDH && currentPrice > 0) {
        if (currentPrice > pdh) {
            pdhPdlSub = '> PDH (Breakout)';
            pdhPdlColor = 'var(--color-profit-text)';
        } else if (currentPrice < pdl) {
            pdhPdlSub = '< PDL (Breakdown)';
            pdhPdlColor = 'var(--color-loss-text)';
        } else {
            pdhPdlSub = 'Inside Range';
            pdhPdlColor = 'var(--color-warning)';
        }
    }

    const items = [
        {
            label: 'RSI',
            value: rsi > 0 ? rsi.toFixed(1) : '--',
            sub: rsi > 70 ? 'Overbought' : rsi < 30 ? 'Oversold' : 'Neutral',
            color: rsi > 70 ? 'var(--color-loss-text)' : rsi < 30 ? 'var(--color-profit-text)' : 'var(--color-warning)',
        },
        {
            label: 'Supertrend',
            value: supertrend,
            sub: 'Direction',
            color: supertrend === 'BULLISH' ? 'var(--color-profit-text)' : supertrend === 'BEARISH' ? 'var(--color-loss-text)' : 'var(--text-muted)',
        },
        {
            label: 'EMA 5/20',
            value: ema5 > 0 ? `${ema5.toFixed(0)}/${ema20.toFixed(0)}` : '--',
            sub: isBullEma ? '↑ Bullish' : '↓ Bearish',
            color: isBullEma ? 'var(--color-profit-text)' : 'var(--color-loss-text)',
        },
        {
            label: 'IV (CE)',
            value: greeks?.ce?.iv ? `${(greeks.ce.iv * 100).toFixed(1)}%` : '--',
            sub: greeks?.ce?.delta ? `Δ ${greeks.ce.delta.toFixed(3)}` : '',
            color: 'var(--accent-purple)',
        },
        {
            label: 'PDH/PDL',
            value: hasPDH ? `${pdh.toFixed(0)}/${pdl.toFixed(0)}` : '--',
            sub: hasPDH ? pdhPdlSub : (pdc != null ? `PDC: ${pdc.toFixed(0)}` : ''),
            color: pdhPdlColor,
        },
    ];

    return (
        <div className="grid grid-cols-5 gap-2">
            {items.map((item) => (
                <Card key={item.label} compact className="!p-2.5 text-center">
                    <div className="label mb-1">{item.label}</div>
                    <div
                        className="mono font-bold text-sm leading-tight"
                        style={{ color: item.color }}
                    >
                        {item.value}
                    </div>
                    {item.sub && (
                        <div className="text-[10px] text-[var(--text-muted)] mt-0.5">{item.sub}</div>
                    )}
                </Card>
            ))}
        </div>
    );
};

export default IndicatorStrip;
