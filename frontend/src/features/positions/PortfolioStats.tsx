import React from 'react';
import Card from '../../shared/Card';
import type { PortfolioStats as PortfolioStatsType } from '../../apiSlice';

interface Props {
    stats?: PortfolioStatsType;
}

const fmt = (v: number, decimals = 0) =>
    v?.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) ?? '—';

const pnlClass = (v: number) => (v >= 0 ? 'profit' : 'loss');

const PortfolioStats: React.FC<Props> = React.memo(({ stats }) => {
    if (!stats) return null;

    const returnPct = stats.total_return_pct ?? 0;
    const equity = stats.total_equity ?? stats.current_balance;

    return (
        <Card compact>
            <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-[var(--text-primary)]">Portfolio</span>
                <span className={`text-[11px] mono font-bold px-1.5 py-0.5 rounded ${pnlClass(returnPct)}`}>
                    {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(2)}%
                </span>
            </div>

            {/* Capital row */}
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 mb-3">
                <Metric label="Capital" value={`₹${fmt(stats.initial_capital)}`} />
                <Metric label="Balance" value={`₹${fmt(stats.current_balance)}`} />
                <Metric label="Equity" value={`₹${fmt(equity)}`} />
                <Metric label="Unrealised" value={`₹${fmt(stats.unrealized_pnl)}`} pnl={stats.unrealized_pnl} />
            </div>

            <div className="border-t border-[var(--border-subtle)] pt-2 mb-2" />

            {/* P&L breakdown */}
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 mb-3">
                <Metric label="Realised P&L" value={`₹${fmt(stats.realized_pnl)}`} pnl={stats.realized_pnl} />
                <Metric label="Session P&L" value={`₹${fmt(stats.session_pnl)}`} pnl={stats.session_pnl} />
            </div>

            <div className="border-t border-[var(--border-subtle)] pt-2 mb-2" />

            {/* Stats */}
            <div className="grid grid-cols-3 gap-x-2 gap-y-2 text-center">
                <StatBox label="Trades" value={String(stats.total_trades)} />
                <StatBox label="Win Rate" value={`${stats.win_rate ?? 0}%`} highlight={stats.win_rate >= 50} />
                <StatBox label="P.Factor" value={
                    stats.profit_factor === Infinity || stats.profit_factor > 999
                        ? '∞'
                        : (stats.profit_factor ?? 0).toFixed(2)
                } highlight={stats.profit_factor > 1} />
                <StatBox label="Avg Win" value={`₹${fmt(stats.avg_win)}`} highlight />
                <StatBox label="Avg Loss" value={`₹${fmt(stats.avg_loss)}`} highlight={false} isLoss />
                <StatBox label="Open" value={String(stats.open_positions)} />
            </div>

            {/* Strategy breakdown */}
            {stats.strategy_analytics && Object.keys(stats.strategy_analytics).length > 0 && (
                <>
                    <div className="border-t border-[var(--border-subtle)] pt-2 mt-3" />
                    <div className="text-[10px] text-[var(--text-muted)] mb-1.5 font-medium uppercase tracking-wide">
                        By Strategy
                    </div>
                    <div className="space-y-1">
                        {Object.entries(stats.strategy_analytics).map(([name, s]) => (
                            <div key={name} className="flex items-center justify-between text-[11px]">
                                <span className="text-[var(--text-secondary)] truncate max-w-[100px]">{name}</span>
                                <div className="flex items-center gap-3 mono">
                                    <span className="text-[var(--text-muted)]">{s.total_trades}T</span>
                                    <span className="text-[var(--text-muted)]">{s.win_rate}%W</span>
                                    <span className={pnlClass(s.total_pnl)}>₹{fmt(s.total_pnl)}</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </>
            )}
        </Card>
    );
});

const Metric: React.FC<{ label: string; value: string; pnl?: number }> = ({ label, value, pnl }) => (
    <div>
        <div className="text-[10px] text-[var(--text-muted)]">{label}</div>
        <div className={`text-xs font-semibold mono ${pnl !== undefined ? pnlClass(pnl) : 'text-[var(--text-primary)]'}`}>
            {value}
        </div>
    </div>
);

const StatBox: React.FC<{ label: string; value: string; highlight?: boolean; isLoss?: boolean }> = ({
    label, value, highlight, isLoss,
}) => (
    <div className="bg-[var(--bg-surface)] rounded p-1.5">
        <div className="text-[9px] text-[var(--text-muted)] mb-0.5">{label}</div>
        <div className={`text-xs font-bold mono ${isLoss ? 'loss' : highlight ? 'profit' : 'text-[var(--text-primary)]'}`}>
            {value}
        </div>
    </div>
);

PortfolioStats.displayName = 'PortfolioStats';
export default PortfolioStats;
