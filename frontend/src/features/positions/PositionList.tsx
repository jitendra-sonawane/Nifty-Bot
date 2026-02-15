import React from 'react';
import Card from '../../shared/Card';
import { X } from 'lucide-react';
import type { StatusResponse } from '../../apiSlice';

interface PositionListProps {
    status?: StatusResponse;
    closePosition: (params: { position_id: string; exit_price: number }) => void;
}

const PositionList: React.FC<PositionListProps> = React.memo(({ status, closePosition }) => {
    const positions = status?.positions;
    const riskStats = status?.risk_stats;

    return (
        <Card compact>
            <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Positions</span>
                {positions && positions.length > 0 && (
                    <span className="text-[10px] mono text-[var(--text-muted)]">
                        {positions.length} open
                    </span>
                )}
            </div>

            {/* Open Positions */}
            {positions && positions.length > 0 ? (
                <div className="space-y-1.5">
                    {positions.map((pos) => {
                        const optionPrice = pos.current_price ?? pos.entry_price;
                        const pnl = pos.unrealized_pnl ?? (optionPrice - pos.entry_price) * pos.quantity;
                        const pnlPct = pos.unrealized_pnl_pct ?? ((optionPrice - pos.entry_price) / pos.entry_price) * 100;
                        const isProfit = pnl >= 0;

                        return (
                            <div
                                key={pos.id}
                                className={`flex items-center justify-between p-2 rounded-md border ${isProfit
                                    ? 'bg-[var(--color-profit-muted)] border-[rgba(34,197,94,0.15)]'
                                    : 'bg-[var(--color-loss-muted)] border-[rgba(239,68,68,0.15)]'
                                    }`}
                            >
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-0.5">
                                        <span className="text-xs font-bold text-[var(--text-primary)]">
                                            {pos.strike ? `${pos.strike} ${pos.position_type}` : pos.position_type}
                                        </span>
                                        <span className="text-[10px] text-[var(--text-muted)]">
                                            Qty: {pos.quantity}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-3 text-[10px] mono">
                                        <span className="text-[var(--text-tertiary)]">Entry: ₹{pos.entry_price.toFixed(1)}</span>
                                        <span className="text-[var(--text-primary)] font-medium">LTP: ₹{optionPrice.toFixed(1)}</span>
                                        <span className="text-[var(--color-loss-text)]">SL ₹{pos.stop_loss.toFixed(1)}</span>
                                        <span className="text-[var(--color-profit-text)]">TP ₹{pos.target.toFixed(1)}</span>
                                    </div>
                                </div>

                                <div className="flex items-center gap-2 flex-shrink-0">
                                    <div className="text-right">
                                        <div className={`mono text-xs font-bold ${isProfit ? 'profit' : 'loss'}`}>
                                            {isProfit ? '+' : ''}₹{pnl.toFixed(1)}
                                        </div>
                                        <div className={`mono text-[10px] ${isProfit ? 'profit' : 'loss'}`}>
                                            {pnlPct.toFixed(1)}%
                                        </div>
                                    </div>
                                    <button
                                        onClick={() =>
                                            closePosition({ position_id: pos.id, exit_price: pos.current_price ?? pos.entry_price })
                                        }
                                        className="p-1 rounded hover:bg-[var(--color-loss-muted)] transition-colors"
                                    >
                                        <X size={14} className="text-[var(--color-loss-text)]" />
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            ) : (
                <div className="text-center py-4 text-[var(--text-muted)] text-xs">
                    No open positions
                </div>
            )}

            {/* Risk Stats */}
            {riskStats && (
                <div className="mt-3 pt-2 border-t border-[var(--border-subtle)] space-y-1">
                    <div className="flex justify-between text-[11px]">
                        <span className="text-[var(--text-tertiary)]">Daily P&L</span>
                        <span className={`mono font-semibold ${riskStats.daily_pnl >= 0 ? 'profit' : 'loss'}`}>
                            ₹{riskStats.daily_pnl.toFixed(1)}
                        </span>
                    </div>
                    <div className="flex justify-between text-[11px]">
                        <span className="text-[var(--text-tertiary)]">Loss Limit</span>
                        <span className="mono text-[var(--text-secondary)]">₹{riskStats.daily_loss_limit.toFixed(0)}</span>
                    </div>
                    <div className="flex justify-between text-[11px]">
                        <span className="text-[var(--text-tertiary)]">Status</span>
                        <span className={`font-semibold ${riskStats.is_trading_allowed ? 'profit' : 'loss'}`}>
                            {riskStats.is_trading_allowed ? '● Active' : '● Blocked'}
                        </span>
                    </div>
                </div>
            )}
        </Card>
    );
});

PositionList.displayName = 'PositionList';
export default PositionList;
