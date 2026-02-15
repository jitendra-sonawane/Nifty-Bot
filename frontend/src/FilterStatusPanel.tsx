import React from 'react';
import { CheckCircle, XCircle, Gauge } from 'lucide-react';

interface FilterStatusProps {
    filters?: Record<string, boolean>;
    rsi?: number;
    volumeRatio?: number;
    atrPct?: number;
    supertrend?: string;
    ema5?: number;
    ema20?: number;
}

const FilterStatusPanel: React.FC<FilterStatusProps> = ({
    filters,
    rsi = 0,
    volumeRatio = 0,
    atrPct = 0,
    supertrend = '',
    ema5 = 0,
    ema20 = 0
}) => {
    // Ensure filters is an object with default values
    const safeFilters = filters || {};

    // Ensure numeric values have defaults to prevent .toFixed() errors
    const safeRsi = typeof rsi === 'number' ? rsi : 0;
    const safeVolumeRatio = typeof volumeRatio === 'number' ? volumeRatio : 0;
    const safeAtrPct = typeof atrPct === 'number' ? atrPct : 0;
    const safeEma5 = typeof ema5 === 'number' ? ema5 : 0;
    const safeEma20 = typeof ema20 === 'number' ? ema20 : 0;

    const getStatusIcon = (passed: boolean) => {
        return passed ? (
            <CheckCircle size={16} className="text-green-400" />
        ) : (
            <XCircle size={16} className="text-red-400" />
        );
    };

    const getStatusColor = (passed: boolean) => {
        return passed
            ? 'bg-green-500/10 border-green-500/30 text-green-400'
            : 'bg-red-500/10 border-red-500/30 text-red-400';
    };

    return (
        <div className="space-y-2">
            <div className="flex items-center gap-2 mb-3">
                <Gauge size={16} className="text-cyan-400" />
                <h3 className="text-sm font-semibold text-white uppercase">Live Filter Metrics</h3>
            </div>

            {/* EMA Crossover Filter */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.ema_crossover || false)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.ema_crossover || false)}
                        <span className="text-xs font-medium text-white">EMA Crossover</span>
                    </div>
                    <div className="text-right">
                        <span className={`text-sm font-bold ${safeFilters.ema_crossover ? 'text-green-400' : 'text-gray-400'}`}>
                            {safeFilters.ema_crossover ? 'ALIGNED' : 'NEUTRAL'}
                        </span>
                        <div className="text-[10px] text-gray-400 font-mono">
                            {safeEma5.toFixed(0)} / {safeEma20.toFixed(0)}
                        </div>
                    </div>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    Target: EMA5 &gt; EMA20 (bullish) or &lt; (bearish)
                </div>
            </div>

            {/* RSI Filter */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.rsi || false)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.rsi || false)}
                        <span className="text-xs font-medium text-white">RSI Level</span>
                    </div>
                    <span className="text-lg font-bold font-mono">{safeRsi.toFixed(1)}</span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    Target: &gt;55 (bullish) or &lt;45 (bearish)
                </div>
            </div>

            {/* Volume Filter */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.volume || false)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.volume || false)}
                        <span className="text-xs font-medium text-white">Volume</span>
                    </div>
                    <span className="text-lg font-bold font-mono">
                        {safeVolumeRatio ? `${(safeVolumeRatio * 100).toFixed(0)}%` : 'N/A'}
                    </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    Target: &gt;50% of avg volume
                </div>
            </div>

            {/* Volatility (ATR) Filter */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.volatility || false)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.volatility || false)}
                        <span className="text-xs font-medium text-white">Volatility (ATR)</span>
                    </div>
                    <span className="text-lg font-bold font-mono">
                        {safeAtrPct ? `${(safeAtrPct).toFixed(3)}%` : '0.000%'}
                    </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    Target: 0.01% - 2.5%
                </div>
            </div>


            {/* Supertrend Filter */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.supertrend || false)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.supertrend || false)}
                        <span className="text-xs font-medium text-white">Supertrend</span>
                    </div>
                    <span className={`text-sm font-bold ${supertrend === 'BULLISH' ? 'text-green-400' : 'text-red-400'}`}>
                        {supertrend || 'N/A'}
                    </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    Trend direction indicator
                </div>
            </div>

            {/* Entry Confirmation */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.entry_confirmation || false)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.entry_confirmation || false)}
                        <span className="text-xs font-medium text-white">Entry Confirmation</span>
                    </div>
                    <span className={`text-sm font-bold ${safeFilters.entry_confirmation ? 'text-green-400' : 'text-gray-400'}`}>
                        {safeFilters.entry_confirmation ? 'CONFIRMED' : 'WAITING'}
                    </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    Last 2 candles must confirm direction
                </div>
            </div>

            {/* Greeks Filter */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.greeks || false)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.greeks || false)}
                        <span className="text-xs font-medium text-white">Greeks Quality</span>
                    </div>
                    <span className={`text-sm font-bold ${safeFilters.greeks ? 'text-green-400' : 'text-gray-400'}`}>
                        {safeFilters.greeks ? 'GOOD' : 'POOR'}
                    </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    Delta & Theta thresholds
                </div>
            </div>

            {/* PCR Filter */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.pcr || false)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.pcr || false)}
                        <span className="text-xs font-medium text-white">PCR Sentiment</span>
                    </div>
                    <span className={`text-sm font-bold ${safeFilters.pcr ? 'text-green-400' : 'text-gray-400'}`}>
                        {safeFilters.pcr ? 'ALIGNED' : 'NEUTRAL'}
                    </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    Put-Call Ratio directional bias
                </div>
            </div>

            {/* ── Intelligence Filters ─────────────────────────── */}
            <div className="border-t border-white/10 my-3 pt-3">
                <h4 className="text-[10px] text-purple-400 uppercase tracking-widest mb-2 font-semibold">Intelligence Filters</h4>
            </div>

            {/* Market Regime */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.market_regime ?? true)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.market_regime ?? true)}
                        <span className="text-xs font-medium text-white">Market Regime</span>
                    </div>
                    <span className={`text-sm font-bold ${safeFilters.market_regime !== false ? 'text-green-400' : 'text-red-400'}`}>
                        {safeFilters.market_regime !== false ? 'PASS' : 'BLOCKED'}
                    </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    Ranging / Trending / High-Vol regime gate
                </div>
            </div>

            {/* IV Rank */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.iv_rank ?? true)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.iv_rank ?? true)}
                        <span className="text-xs font-medium text-white">IV Rank</span>
                    </div>
                    <span className={`text-sm font-bold ${safeFilters.iv_rank !== false ? 'text-green-400' : 'text-red-400'}`}>
                        {safeFilters.iv_rank !== false ? 'PASS' : 'LOW'}
                    </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    IV Rank ≥ 20 for premium selling
                </div>
            </div>

            {/* Market Breadth */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.market_breadth ?? true)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.market_breadth ?? true)}
                        <span className="text-xs font-medium text-white">Market Breadth</span>
                    </div>
                    <span className={`text-sm font-bold ${safeFilters.market_breadth !== false ? 'text-green-400' : 'text-red-400'}`}>
                        {safeFilters.market_breadth !== false ? 'PASS' : 'DIVERGE'}
                    </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    Advance/Decline breadth confirmation
                </div>
            </div>

            {/* Order Book */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.order_book ?? true)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.order_book ?? true)}
                        <span className="text-xs font-medium text-white">Order Book</span>
                    </div>
                    <span className={`text-sm font-bold ${safeFilters.order_book !== false ? 'text-green-400' : 'text-red-400'}`}>
                        {safeFilters.order_book !== false ? 'LIQUID' : 'POOR'}
                    </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    Option liquidity &amp; spread check
                </div>
            </div>

            {/* VIX */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.vix ?? true)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.vix ?? true)}
                        <span className="text-xs font-medium text-white">VIX</span>
                    </div>
                    <span className={`text-sm font-bold ${safeFilters.vix !== false ? 'text-green-400' : 'text-red-400'}`}>
                        {safeFilters.vix !== false ? 'SAFE' : 'HIGH'}
                    </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    India VIX &lt; 20 for normal trading
                </div>
            </div>

            {/* PCR Trend */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.pcr_trend ?? true)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.pcr_trend ?? true)}
                        <span className="text-xs font-medium text-white">PCR Trend</span>
                    </div>
                    <span className={`text-sm font-bold ${safeFilters.pcr_trend !== false ? 'text-green-400' : 'text-red-400'}`}>
                        {safeFilters.pcr_trend !== false ? 'ALIGNED' : 'DIVERGE'}
                    </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    PCR direction vs signal confluence
                </div>
            </div>

            {/* Time of Day */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.time_of_day ?? true)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.time_of_day ?? true)}
                        <span className="text-xs font-medium text-white">Time of Day</span>
                    </div>
                    <span className={`text-sm font-bold ${safeFilters.time_of_day !== false ? 'text-green-400' : 'text-red-400'}`}>
                        {safeFilters.time_of_day !== false ? 'OPEN' : 'BLOCKED'}
                    </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    Avoids opening &amp; closing volatility
                </div>
            </div>

            {/* OI Buildup */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.oi_buildup ?? true)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.oi_buildup ?? true)}
                        <span className="text-xs font-medium text-white">OI Buildup</span>
                    </div>
                    <span className={`text-sm font-bold ${safeFilters.oi_buildup !== false ? 'text-green-400' : 'text-red-400'}`}>
                        {safeFilters.oi_buildup !== false ? 'PASS' : 'CONTRA'}
                    </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    Long/Short buildup vs unwinding
                </div>
            </div>

            {/* Expiry Day */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.expiry_day ?? true)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.expiry_day ?? true)}
                        <span className="text-xs font-medium text-white">Expiry Day</span>
                    </div>
                    <span className={`text-sm font-bold ${safeFilters.expiry_day !== false ? 'text-green-400' : 'text-red-400'}`}>
                        {safeFilters.expiry_day !== false ? 'OK' : '0DTE ⚠'}
                    </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    Gamma risk check on expiry day
                </div>
            </div>
        </div>
    );
};

export default FilterStatusPanel;
