import React from 'react';

interface SentimentPanelProps {
    status: any;
}

const SentimentPanel: React.FC<SentimentPanelProps> = ({ status }) => {
    const pcrAnalysis = status?.market_state?.pcr_analysis;
    const sentiment = status?.sentiment;
    
    return (
        <div className="card p-4 rounded-xl bg-[#151925] border border-white/5 shadow-lg">
            <h2 className="text-sm font-medium mb-3 text-white">Market Sentiment</h2>
            {sentiment ? (
                <>
                    {/* Overall Sentiment Score */}
                    <div className="flex justify-between items-center mb-2">
                        <div className={`font-bold text-lg ${sentiment.score >= 60 ? 'text-green-400' : sentiment.score <= 40 ? 'text-red-400' : 'text-yellow-400'}`}>
                            {sentiment.label}
                        </div>
                        <div className="text-xs font-mono bg-white/5 px-2 py-1 rounded">{sentiment.score}/100</div>
                    </div>
                    <div className="h-2 bg-[#2A2F45] rounded-full overflow-hidden mb-4">
                        <div className={`h-full rounded-full transition-all duration-1000 ${sentiment.score >= 60 ? 'bg-green-500' : sentiment.score <= 40 ? 'bg-red-500' : 'bg-yellow-500'}`} style={{ width: `${sentiment.score}%` }}></div>
                    </div>
                    

                    
                    {/* VIX and PCR Grid */}
                    <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="bg-white/5 p-2 rounded text-center">
                            <div className="text-gray-500 mb-1">VIX</div>
                            <div className="font-mono font-bold">{sentiment.vix?.toFixed(2) || 'N/A'}</div>
                        </div>
                        <div className="bg-white/5 p-2 rounded text-center">
                            <div className="text-gray-500 mb-1">PCR</div>
                            <div className="font-mono font-bold">{sentiment.pcr?.toFixed(2) || 'N/A'}</div>
                        </div>
                    </div>
                </>
            ) : (
                <div className="text-center text-gray-500 text-xs py-4">Waiting for data...</div>
            )}
        </div>
    );
};

export default SentimentPanel;
