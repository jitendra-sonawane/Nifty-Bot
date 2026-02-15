import React from 'react';

interface IndicatorPanelProps {
    strategyData: any;
    currentPrice: number;
}

const IndicatorPanel: React.FC<IndicatorPanelProps> = ({ strategyData, currentPrice }) => {
    const rsi = strategyData?.rsi || 0;
    const supertrend = strategyData?.supertrend || "WAITING";
    const ema5 = strategyData?.ema_5 || 0;
    const ema20 = strategyData?.ema_20 || 0;
    const greeks = strategyData?.greeks;

    return (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {/* RSI */}
            <div className="bg-white/5 p-3 rounded-lg border border-white/10">
                <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">RSI (14)</div>
                <div className={`text-lg font-mono font-bold ${rsi > 70 ? 'text-red-400' : rsi < 30 ? 'text-green-400' : 'text-yellow-400'}`}>
                    {rsi.toFixed(1)}
                </div>
                <div className="text-[10px] text-gray-500">
                    {rsi > 70 ? 'Overbought' : rsi < 30 ? 'Oversold' : 'Neutral'}
                </div>
            </div>

            {/* Supertrend */}
            <div className="bg-white/5 p-3 rounded-lg border border-white/10">
                <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Supertrend</div>
                <div className={`text-lg font-bold ${supertrend === 'BULLISH' ? 'text-green-400' : supertrend === 'BEARISH' ? 'text-red-400' : 'text-gray-400'}`}>
                    {supertrend}
                </div>
                <div className="text-[10px] text-gray-500">Trend Direction</div>
            </div>

            {/* EMA Crossover */}
            <div className="bg-white/5 p-3 rounded-lg border border-white/10">
                <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">EMA (5/20)</div>
                <div className={`text-lg font-mono font-bold ${ema5 > ema20 ? 'text-green-400' : 'text-red-400'}`}>
                    {ema5.toFixed(0)} / {ema20.toFixed(0)}
                </div>
                <div className="text-[10px] text-gray-500">
                    {ema5 > ema20 ? '↑ Bullish' : '↓ Bearish'}
                </div>
            </div>

            {/* Greeks / IV */}
            <div className="bg-white/5 p-3 rounded-lg border border-white/10">
                <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">IV (CE/PE)</div>
                <div className="text-lg font-mono font-bold text-purple-400">
                    {greeks?.ce?.iv ? `${(greeks.ce.iv * 100).toFixed(1)}%` : '--'}
                </div>
                <div className="text-[10px] text-gray-500">
                    {greeks?.ce?.delta ? `Delta: ${greeks.ce.delta.toFixed(3)}` : 'No Data'}
                </div>
            </div>
        </div>
    );
};

export default IndicatorPanel;
