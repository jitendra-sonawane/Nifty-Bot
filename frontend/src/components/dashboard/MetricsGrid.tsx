import React from 'react';
import { Database } from 'lucide-react';
import PriceChart from '../../PriceChart';

interface MetricsGridProps {
    currentPrice: number;
    priceHistory: { time: string, price: number }[];
    signal: string;
    status: any;
}

const MetricsGrid: React.FC<MetricsGridProps> = ({ currentPrice, priceHistory, signal, status }) => {
    return (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            {/* Price Card */}
            <div className="card p-4 rounded-xl bg-gradient-to-b from-white/5 to-white/0 border border-white/5 shadow-lg">
                <div className="flex justify-between items-start mb-2">
                    <h3 className="text-xs text-gray-400 uppercase tracking-wider">Nifty 50</h3>
                    <span className="text-[10px] text-gray-500 font-mono">LTP</span>
                </div>
                <div className="text-3xl font-mono font-bold text-white mb-1">{currentPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
                <div className="h-10 w-full opacity-50">
                    <PriceChart data={priceHistory} height={40} />
                </div>
            </div>

            {/* Signal Card */}
            <div className="card p-4 rounded-xl bg-gradient-to-b from-white/5 to-white/0 border border-white/5 shadow-lg">
                <h3 className="text-xs text-gray-400 uppercase tracking-wider mb-2">Signal</h3>
                <div className={`text-2xl font-bold mb-2 ${signal.includes('BUY') ? 'text-green-400' : signal.includes('SELL') ? 'text-red-400' : 'text-cyan-400'}`}>
                    {signal}
                </div>
                <div className="text-[10px] text-gray-400 truncate">{status?.decision_reason || "Analyzing..."}</div>
            </div>

            {/* P&L Card */}
            <div className="card p-4 rounded-xl bg-gradient-to-b from-white/5 to-white/0 border border-white/5 shadow-lg">
                <h3 className="text-xs text-gray-400 uppercase tracking-wider mb-2">Daily P&L</h3>
                <div className={`text-3xl font-mono font-bold mb-1 ${(status?.trading_mode === 'PAPER' ? (status.paper_daily_pnl ?? status.paper_pnl) : 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {status?.trading_mode === 'PAPER' ? `₹${(status.paper_daily_pnl ?? status.paper_pnl)?.toFixed(2)}` : '--'}
                </div>
                <div className="text-[10px] text-gray-500">
                    {status?.trading_mode === 'PAPER' && status.paper_daily_pnl !== undefined ? (
                        <>
                            Realized: ₹{status.paper_daily_pnl?.toFixed(2)} | Unrealized: ₹{status.paper_pnl?.toFixed(2)}
                        </>
                    ) : (
                        `Risk Limit: ₹${status?.risk_stats?.daily_loss_limit?.toFixed(0) || '0'}`
                    )}
                </div>
            </div>

            {/* AI Status Card */}
            <div className="card p-4 rounded-xl bg-gradient-to-b from-purple-500/10 to-purple-500/0 border border-purple-500/20 shadow-lg">
                <div className="flex items-center gap-2 mb-2">
                    <Database size={14} className="text-purple-400" />
                    <h3 className="text-xs text-purple-300 uppercase tracking-wider">AI Data Collection</h3>
                </div>
                <div className="flex items-center gap-2 mb-2">
                    <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                    <span className="text-sm font-bold text-white">Active</span>
                </div>
                <div className="text-[10px] text-gray-400">
                    Logging features & outcomes for future training.
                </div>
            </div>
        </div>
    );
};

export default MetricsGrid;
