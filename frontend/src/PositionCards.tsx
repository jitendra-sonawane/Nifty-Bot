import React from 'react';
import { X } from 'lucide-react';
import type { StatusResponse } from './apiSlice';

interface PositionCardsProps {
    status?: StatusResponse;
    closePosition: (params: { position_id: string; exit_price: number }) => void;
}

const PositionCards: React.FC<PositionCardsProps> = ({ status, closePosition }) => {
    return (
        <>
            {/* Open Positions Card */}
            {status?.positions && status.positions.length > 0 && (
                <div className="card p-3 rounded-lg border border-[rgba(255,255,255,0.03)] bg-[linear-gradient(180deg,rgba(10,10,18,0.6),rgba(30,8,48,0.6))] shadow-[0_10px_40px_rgba(20,8,40,0.6)]">
                    <h2 className="text-sm font-medium mb-2 text-white">📈 Open Positions</h2>
                    <div className="space-y-1">
                        {status.positions.map((position) => {
                            const currentPrice = position.current_price ?? position.entry_price;
                            const pnl = (position.unrealized_pnl != null ? position.unrealized_pnl : (currentPrice - position.entry_price) * position.quantity);
                            const pnlPct = (position.unrealized_pnl_pct != null ? position.unrealized_pnl_pct : ((currentPrice - position.entry_price) / position.entry_price) * 100);

                            return (
                                <div key={position.id} className="p-2 bg-white/5 rounded border border-white/10">
                                    <div className="flex justify-between items-start mb-1">
                                        <div>
                                            <div className="font-bold text-xs">{position.position_type}</div>
                                            <div className="text-[10px] text-gray-400">Qty: {position.quantity}</div>
                                        </div>
                                        <button
                                            onClick={() => closePosition({ position_id: position.id, exit_price: currentPrice as number })}
                                            className="p-1 hover:bg-red-500/20 rounded transition-colors"
                                            title="Close Position"
                                        >
                                            <X size={14} className="text-red-400" />
                                        </button>
                                    </div>
                                    <div className="grid grid-cols-2 gap-1 text-[10px]">
                                        <div>
                                            <div className="text-gray-400">Entry</div>
                                            <div className="font-mono">₹{position.entry_price.toFixed(2)}</div>
                                        </div>
                                        <div>
                                            <div className="text-gray-400">P&L</div>
                                            <div className={`font-mono font-bold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                ₹{pnl.toFixed(2)} ({pnlPct.toFixed(1)}%)
                                            </div>
                                        </div>
                                        <div>
                                            <div className="text-gray-400">SL</div>
                                            <div className="font-mono text-red-400">₹{position.stop_loss.toFixed(2)}</div>
                                        </div>
                                        <div>
                                            <div className="font-mono text-green-400">₹{position.target.toFixed(2)}</div>
                                        </div>
                                        <div>
                                            <div className="text-gray-400">Trailing SL</div>
                                            <div className={`font-mono ${position.trailing_sl_activated ? 'text-blue-400' : 'text-gray-600'}`}>
                                                {position.trailing_sl ? `₹${position.trailing_sl.toFixed(2)}` : '-'}
                                                {position.trailing_sl_activated && <span className="text-[8px] ml-1">ON</span>}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Risk Management Stats Card */}
            {status?.risk_stats && (
                <div className="card p-5 rounded-2xl border border-[rgba(255,255,255,0.03)] bg-[linear-gradient(180deg,rgba(10,10,18,0.6),rgba(30,8,48,0.6))] shadow-[0_10px_40px_rgba(20,8,40,0.6)]">
                    <h2 className="text-lg font-medium mb-4 text-white">💼 Risk Management</h2>
                    <div className="space-y-3 text-sm">
                        <div className="flex justify-between">
                            <span className="text-gray-300">Daily P&L</span>
                            <span className={`font-mono font-bold ${status.risk_stats.daily_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                ₹{status.risk_stats.daily_pnl.toFixed(2)}
                            </span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-gray-300">Loss Limit</span>
                            <span className="font-mono text-white">₹{status.risk_stats.daily_loss_limit.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-gray-300">Risk per Trade</span>
                            <span className="font-mono text-white">{status.risk_stats.risk_per_trade_pct}%</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-gray-300">Max Positions</span>
                            <span className="font-mono text-white">{status.risk_stats.max_concurrent_positions}</span>
                        </div>
                        <div className="flex justify-between items-center pt-2 border-t border-white/10">
                            <span className="text-gray-300">Trading Status</span>
                            <span className={`font-bold ${status.risk_stats.is_trading_allowed ? 'text-green-400' : 'text-red-400'}`}>
                                {status.risk_stats.is_trading_allowed ? '✅ Allowed' : '🚫 Blocked'}
                            </span>
                        </div>
                    </div>
                </div>
            )}

            {/* Trade History Card */}
            {status?.trade_history && status.trade_history.length > 0 && (
                <div className="card p-5 rounded-2xl border border-[rgba(255,255,255,0.03)] bg-[linear-gradient(180deg,rgba(10,10,18,0.6),rgba(30,8,48,0.6))] shadow-[0_10px_40px_rgba(20,8,40,0.6)]">
                    <h2 className="text-lg font-medium mb-4 text-white">📊 Recent Trades</h2>
                    <div className="space-y-2 text-xs">
                        {status.trade_history.slice(0, 5).map((trade, idx) => (
                            <div key={idx} className="p-3 bg-white/5 rounded-lg border border-white/10">
                                <div className="flex justify-between items-center mb-2">
                                    <span className="font-bold">{trade.type}</span>
                                    <span className={`font-mono font-bold ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        ₹{trade.pnl.toFixed(2)} ({trade.pnl_pct.toFixed(1)}%)
                                    </span>
                                </div>
                                <div className="grid grid-cols-2 gap-1 text-gray-400">
                                    <div>Entry: ₹{trade.entry_price.toFixed(2)}</div>
                                    <div>Exit: ₹{trade.exit_price.toFixed(2)}</div>
                                </div>
                                <div className="text-gray-500 mt-1">{trade.reason}</div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </>
    );
};

export default PositionCards;
