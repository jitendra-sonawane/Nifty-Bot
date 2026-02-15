import React, { useState } from 'react';
import { useRunBacktestMutation } from '../../apiSlice';
import Card from '../../shared/Card';
import { ChevronDown, ChevronUp, BarChart3 } from 'lucide-react';

const BacktestPanel: React.FC = () => {
    const [runBacktest, { isLoading, data: results, error }] = useRunBacktestMutation();
    const [open, setOpen] = useState(false);

    const today = new Date();
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(today.getDate() - 30);

    const [fromDate, setFromDate] = useState(thirtyDaysAgo.toISOString().split('T')[0]);
    const [toDate, setToDate] = useState(today.toISOString().split('T')[0]);
    const [initialCapital, setInitialCapital] = useState(100000);

    const handleRun = () => {
        runBacktest({ from_date: fromDate, to_date: toDate, initial_capital: initialCapital });
    };

    return (
        <Card compact>
            <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <BarChart3 size={14} className="text-[var(--accent-purple)]" />
                    <span className="text-sm font-medium">Backtest</span>
                </div>
                {open ? (
                    <ChevronUp size={16} className="text-[var(--text-muted)]" />
                ) : (
                    <ChevronDown size={16} className="text-[var(--text-muted)]" />
                )}
            </button>

            {open && (
                <div className="mt-3 space-y-2 animate-fade-in">
                    {/* Inputs */}
                    <div className="grid grid-cols-2 gap-2">
                        <div>
                            <label className="label block mb-1">From</label>
                            <input
                                type="date"
                                value={fromDate}
                                max={today.toISOString().split('T')[0]}
                                onChange={(e) => setFromDate(e.target.value)}
                                className="w-full"
                            />
                        </div>
                        <div>
                            <label className="label block mb-1">To</label>
                            <input
                                type="date"
                                value={toDate}
                                max={today.toISOString().split('T')[0]}
                                onChange={(e) => setToDate(e.target.value)}
                                className="w-full"
                            />
                        </div>
                    </div>
                    <div>
                        <label className="label block mb-1">Capital</label>
                        <input
                            type="number"
                            value={initialCapital}
                            onChange={(e) => setInitialCapital(Number(e.target.value))}
                            className="w-full"
                        />
                    </div>
                    <button
                        onClick={handleRun}
                        disabled={isLoading}
                        className="w-full py-2 rounded-lg font-bold text-sm text-white
              bg-gradient-to-r from-[var(--accent-purple)] to-pink-500
              hover:opacity-90 disabled:opacity-50 transition-opacity"
                    >
                        {isLoading ? '⏳ Running…' : '▶ Run Backtest'}
                    </button>

                    {/* Results */}
                    {results && !results.error && (
                        <div className="space-y-2 pt-2 border-t border-[var(--border-subtle)]">
                            <div className="grid grid-cols-3 gap-1.5">
                                {[
                                    {
                                        label: 'Return',
                                        val: `${results.metrics?.total_return_pct?.toFixed(1)}%`,
                                        color: (results.metrics?.total_return_pct ?? 0) >= 0 ? 'profit' : 'loss',
                                    },
                                    { label: 'Win Rate', val: `${results.metrics?.win_rate?.toFixed(0)}%`, color: '' },
                                    { label: 'Trades', val: results.total_trades || 0, color: '' },
                                    { label: 'PF', val: results.metrics?.profit_factor?.toFixed(2), color: '' },
                                    { label: 'Drawdown', val: `${results.metrics?.max_drawdown_pct?.toFixed(1)}%`, color: 'loss' },
                                    { label: 'Final', val: `₹${(results.final_capital || 0).toFixed(0)}`, color: '' },
                                ].map((m) => (
                                    <div key={m.label} className="text-center surface !rounded-md p-1.5">
                                        <div className="label text-[9px]">{m.label}</div>
                                        <div className={`mono text-xs font-bold ${m.color}`}>{m.val}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Error */}
                    {(results?.error || error) && (
                        <div className="text-xs text-[var(--color-loss-text)] bg-[var(--color-loss-muted)] rounded-md p-2">
                            {results?.error || (error as any)?.data?.detail || 'Unknown error'}
                        </div>
                    )}
                </div>
            )}
        </Card>
    );
};

export default BacktestPanel;
