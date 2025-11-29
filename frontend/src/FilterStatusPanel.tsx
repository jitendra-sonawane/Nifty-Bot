import React from 'react';
import { CheckCircle, XCircle, Gauge } from 'lucide-react';

interface FilterStatusProps {
    filters?: Record<string, boolean>;
    rsi?: number;
    volumeRatio?: number;
    atrPct?: number;
    vwap?: number;
    currentPrice?: number;
    supertrend?: string;
}

const FilterStatusPanel: React.FC<FilterStatusProps> = ({
    filters,
    rsi = 0,
    volumeRatio = 0,
    atrPct = 0,
    vwap = 0,
    currentPrice = 0,
    supertrend = ''
}) => {
    // Ensure filters is an object with default values
    const safeFilters = filters || {};
    
    // Ensure numeric values have defaults to prevent .toFixed() errors
    const safeRsi = typeof rsi === 'number' ? rsi : 0;
    const safeVolumeRatio = typeof volumeRatio === 'number' ? volumeRatio : 0;
    const safeAtrPct = typeof atrPct === 'number' ? atrPct : 0;
    const safeVwap = typeof vwap === 'number' ? vwap : 0;
    const safeCurrentPrice = typeof currentPrice === 'number' ? currentPrice : 0;
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

    const priceVwapDistance = safeVwap && safeCurrentPrice
        ? Math.abs((safeCurrentPrice - safeVwap) / safeVwap * 100).toFixed(3)
        : '0.000';

    return (
        <div className="space-y-2">
            <div className="flex items-center gap-2 mb-3">
                <Gauge size={16} className="text-cyan-400" />
                <h3 className="text-sm font-semibold text-white uppercase">Live Filter Metrics</h3>
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

            {/* Price vs VWAP Filter */}
            <div className={`rounded-lg p-3 border ${getStatusColor(safeFilters.price_vwap || false)}`}>
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        {getStatusIcon(safeFilters.price_vwap || false)}
                        <span className="text-xs font-medium text-white">Price vs VWAP</span>
                    </div>
                    <span className="text-lg font-bold font-mono">{priceVwapDistance}%</span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                    Target: &gt;0.05% distance
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
        </div>
    );
};

export default FilterStatusPanel;
