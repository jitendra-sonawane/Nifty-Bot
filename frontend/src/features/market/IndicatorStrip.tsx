import React from 'react';
import Card from '../../shared/Card';

interface IndicatorStripProps {
    strategyData: any;
    currentPrice: number;
}

const IndicatorStrip: React.FC<IndicatorStripProps> = ({ strategyData, currentPrice }) => {
    const rsi = strategyData?.rsi ?? 0;
    const supertrend = strategyData?.supertrend ?? 'N/A';
    const ema5 = strategyData?.ema_5 ?? 0;
    const ema20 = strategyData?.ema_20 ?? 0;
    const greeks = strategyData?.greeks;
    const isBullEma = ema5 > ema20;

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
    ];

    return (
        <div className="grid grid-cols-4 gap-2">
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
