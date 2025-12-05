import React from 'react';

interface PCRSentimentCardProps {
    pcrAnalysis: any;
    sentiment: any;
}

const PCRSentimentCard: React.FC<PCRSentimentCardProps> = ({ pcrAnalysis, sentiment }) => {
    if (!pcrAnalysis && !sentiment?.pcr) {
        return (
            <div className="card p-4 rounded-xl bg-[#151925] border border-white/5 shadow-lg">
                <h3 className="text-sm font-medium mb-3 text-white">PCR Sentiment</h3>
                <div className="text-center text-gray-500 text-xs py-4">Waiting for PCR data...</div>
            </div>
        );
    }

    const pcr = pcrAnalysis?.pcr || sentiment?.pcr;
    const pcrSentiment = pcrAnalysis?.sentiment || sentiment?.pcr_sentiment;
    const emoji = pcrAnalysis?.emoji || sentiment?.pcr_emoji;
    const interpretation = pcrAnalysis?.interpretation;
    const trend = pcrAnalysis?.trend || sentiment?.pcr_trend;

    const getSentimentColor = (sentiment: string) => {
        switch (sentiment) {
            case 'EXTREME_BEARISH': return 'text-red-500';
            case 'BEARISH': return 'text-red-400';
            case 'NEUTRAL': return 'text-yellow-400';
            case 'BULLISH': return 'text-green-400';
            case 'EXTREME_BULLISH': return 'text-green-500';
            default: return 'text-gray-400';
        }
    };

    const getTrendColor = (trend: string) => {
        switch (trend) {
            case 'INCREASING': return 'text-red-400';
            case 'DECREASING': return 'text-green-400';
            default: return 'text-gray-400';
        }
    };

    const getTrendIcon = (trend: string) => {
        switch (trend) {
            case 'INCREASING': return '📈';
            case 'DECREASING': return '📉';
            default: return '➡️';
        }
    };

    const getTrendLabel = (trend: string) => {
        switch (trend) {
            case 'INCREASING': return 'Bearish Trend';
            case 'DECREASING': return 'Bullish Trend';
            default: return 'Stable';
        }
    };

    return (
        <div className="card p-4 rounded-xl bg-[#151925] border border-white/5 shadow-lg">
            <h3 className="text-sm font-medium mb-3 text-white flex items-center gap-2">
                <span>PCR Sentiment</span>
                {emoji && <span className="text-lg">{emoji}</span>}
            </h3>
            
            {/* PCR Value and Sentiment */}
            <div className="flex items-center justify-between mb-3">
                <div className="text-2xl font-mono font-bold text-white">
                    {pcr?.toFixed(3) || 'N/A'}
                </div>
                <div className={`text-sm font-bold ${getSentimentColor(pcrSentiment)}`}>
                    {pcrSentiment?.replace('_', ' ') || 'Unknown'}
                </div>
            </div>

            {/* PCR Bar Visualization */}
            <div className="mb-3">
                <div className="h-2 bg-[#2A2F45] rounded-full overflow-hidden relative">
                    {/* Neutral zone marker */}
                    <div className="absolute left-1/2 top-0 w-0.5 h-full bg-yellow-400 opacity-50"></div>
                    {/* PCR indicator */}
                    <div 
                        className={`h-full rounded-full transition-all duration-1000 ${
                            pcr > 1.5 ? 'bg-red-500' :
                            pcr > 1.0 ? 'bg-red-400' :
                            pcr > 0.5 ? 'bg-green-400' :
                            'bg-green-500'
                        }`}
                        style={{ 
                            width: `${Math.min(Math.max((pcr / 2) * 100, 5), 95)}%` 
                        }}
                    ></div>
                </div>
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>Bullish (&lt;1.0)</span>
                    <span>Bearish (&gt;1.0)</span>
                </div>
            </div>

            {/* Interpretation */}
            {interpretation && (
                <div className="mb-3 p-2 bg-white/5 rounded text-xs text-gray-300 leading-relaxed">
                    {interpretation}
                </div>
            )}

            {/* Trend */}
            {trend && (
                <div className="flex items-center justify-between text-xs">
                    <span className="text-gray-500">Trend:</span>
                    <span className={`font-medium flex items-center gap-1 ${getTrendColor(trend)}`}>
                        <span>{getTrendIcon(trend)}</span>
                        <span>{getTrendLabel(trend)}</span>
                    </span>
                </div>
            )}

            {/* PCR Levels Reference */}
            <div className="mt-3 pt-3 border-t border-white/10">
                <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="text-center">
                        <div className="text-gray-500">Extreme Bearish</div>
                        <div className="font-mono text-red-500">&gt; 1.5</div>
                    </div>
                    <div className="text-center">
                        <div className="text-gray-500">Extreme Bullish</div>
                        <div className="font-mono text-green-500">&lt; 0.5</div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PCRSentimentCard;