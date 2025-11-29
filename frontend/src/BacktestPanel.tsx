import React, { useState } from 'react';
import { useRunBacktestMutation } from './apiSlice';

const BacktestPanel: React.FC = () => {
    const [runBacktest, { isLoading, data: results, error }] = useRunBacktestMutation();

    // Default to last 30 days
    const today = new Date();
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(today.getDate() - 30);

    const [fromDate, setFromDate] = useState(thirtyDaysAgo.toISOString().split('T')[0]);
    const [toDate, setToDate] = useState(today.toISOString().split('T')[0]);
    const [initialCapital, setInitialCapital] = useState(100000);

    const handleRunBacktest = () => {
        console.log('Running backtest with:', { fromDate, toDate, initialCapital });
        runBacktest({
            from_date: fromDate,
            to_date: toDate,
            initial_capital: initialCapital
        });
    };

    return (
        <div className="card p-3 rounded-lg border border-[rgba(255,255,255,0.03)] bg-[linear-gradient(180deg,rgba(10,10,18,0.6),rgba(30,8,48,0.6))] shadow-[0_10px_40px_rgba(20,8,40,0.6)]">
            <h2 className="text-sm font-medium mb-2 text-white">📈 Backtest</h2>

            {/* Input Form */}
            <div className="space-y-2 mb-2">
                <div className="grid grid-cols-2 gap-2">
                    <div>
                        <label className="text-xs text-gray-400 block mb-1">From</label>
                        <input
                            type="date"
                            value={fromDate}
                            max={new Date().toISOString().split('T')[0]}
                            onChange={(e) => setFromDate(e.target.value)}
                            className="w-full px-2 py-1 bg-white/5 border border-white/10 rounded text-white text-xs focus:outline-none focus:border-blue-500"
                        />
                    </div>
                    <div>
                        <label className="text-xs text-gray-400 block mb-1">To</label>
                        <input
                            type="date"
                            value={toDate}
                            max={new Date().toISOString().split('T')[0]}
                            onChange={(e) => setToDate(e.target.value)}
                            className="w-full px-2 py-1 bg-white/5 border border-white/10 rounded text-white text-xs focus:outline-none focus:border-blue-500"
                        />
                    </div>
                </div>
                <div>
                    <label className="text-xs text-gray-400 block mb-1">Capital</label>
                    <input
                        type="number"
                        value={initialCapital}
                        onChange={(e) => setInitialCapital(Number(e.target.value))}
                        className="w-full px-2 py-1 bg-white/5 border border-white/10 rounded text-white text-xs focus:outline-none focus:border-blue-500"
                    />
                </div>
                <button
                    onClick={handleRunBacktest}
                    disabled={isLoading}
                    className="w-full py-1 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-bold rounded text-xs hover:shadow-lg transition-all disabled:opacity-50"
                >
                    {isLoading ? 'Running...' : '▶ Run'}
                </button>
            </div>

            {/* Results */}
            {isLoading && (
                <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded text-blue-400 text-xs text-center">
                    ⏳ Running backtest... This may take a moment
                </div>
            )}

            {results && !results.error && (
                <div className="space-y-2">
                    {/* Metrics */}
                    <div className="p-2 bg-white/5 rounded border border-white/10">
                        <h3 className="text-xs font-bold mb-2 text-white">Metrics</h3>
                        <div className="grid grid-cols-2 gap-2 text-[10px]">
                            <div>
                                <div className="text-gray-400">Return</div>
                                <div className={`font-mono font-bold ${(results.metrics?.total_return_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    {results.metrics?.total_return_pct?.toFixed(2) || '0'}%
                                </div>
                            </div>
                            <div>
                                <div className="text-gray-400">Win Rate</div>
                                <div className="font-mono font-bold text-white">
                                    {results.metrics?.win_rate?.toFixed(1) || '0'}%
                                </div>
                            </div>
                            <div>
                                <div className="text-gray-400">Trades</div>
                                <div className="font-mono font-bold text-white">
                                    {results.total_trades || 0}
                                </div>
                            </div>
                            <div>
                                <div className="text-gray-400">Profit Factor</div>
                                <div className="font-mono font-bold text-white">
                                    {results.metrics?.profit_factor?.toFixed(2) || '0'}
                                </div>
                            </div>
                            <div>
                                <div className="text-gray-400">Drawdown</div>
                                <div className="font-mono font-bold text-red-400">
                                    {results.metrics?.max_drawdown_pct?.toFixed(2) || '0'}%
                                </div>
                            </div>
                            <div>
                                <div className="text-gray-400">Final $</div>
                                <div className="font-mono font-bold text-white">
                                    ₹{(results.final_capital || 0)?.toFixed(0)}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Trades Summary */}
                    {results.trades && results.trades.length > 0 && (
                        <div className="p-2 bg-white/5 rounded border border-white/10">
                            <h3 className="text-xs font-bold mb-1 text-white">Trades ({results.trades.length})</h3>
                            <div className="space-y-1 max-h-32 overflow-y-auto">
                                {results.trades.slice(-5).reverse().map((trade: any, idx: number) => (
                                    <div key={idx} className="text-[10px] p-1 bg-white/5 rounded">
                                        <div className="flex justify-between items-center">
                                            <span className="font-bold">{trade.position_type}</span>
                                            <span className={`font-mono text-[9px] ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                ₹{trade.pnl?.toFixed(2)} ({trade.pnl_pct?.toFixed(1)}%)
                                            </span>
                                        </div>
                                        <div className="text-gray-500 text-[9px] mt-0.5">{trade.reason}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Error */}
            {(results?.error || error) && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded text-red-400 text-xs">
                    Error: {results?.error || (error as any)?.data?.detail || 'Unknown error'}
                </div>
            )}
        </div>
    );
};

export default BacktestPanel;
