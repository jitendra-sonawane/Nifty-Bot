import React, { useState } from 'react';
import Card from '../../shared/Card';
import type { TradeRecord } from '../../apiSlice';

interface Props {
    trades?: TradeRecord[];
}

const fmt = (v: number, d = 2) =>
    v?.toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d }) ?? '0';

const pnlClass = (v: number) => (v >= 0 ? 'profit' : 'loss');

const formatTime = (iso: string) => {
    try {
        const d = new Date(iso);
        return d.toLocaleString('en-IN', {
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit', hour12: false,
        });
    } catch {
        return iso;
    }
};

const formatDuration = (mins: number) => {
    if (!mins) return '—';
    if (mins < 60) return `${Math.round(mins)}m`;
    return `${Math.floor(mins / 60)}h ${Math.round(mins % 60)}m`;
};

const TradeJournal: React.FC<Props> = React.memo(({ trades }) => {
    const [filter, setFilter] = useState<'all' | 'win' | 'loss'>('all');

    const filteredTrades = (trades ?? []).filter(t => {
        if (filter === 'win') return t.pnl > 0;
        if (filter === 'loss') return t.pnl <= 0;
        return true;
    });

    const totalPnl = filteredTrades.reduce((s, t) => s + t.pnl, 0);

    return (
        <Card compact>
            <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-[var(--text-primary)]">Trade Journal</span>
                <div className="flex items-center gap-2">
                    <span className={`text-[11px] mono font-bold ${pnlClass(totalPnl)}`}>
                        {totalPnl >= 0 ? '+' : ''}₹{fmt(totalPnl)}
                    </span>
                    <span className="text-[10px] text-[var(--text-muted)] mono">
                        {filteredTrades.length} trades
                    </span>
                </div>
            </div>

            {/* Filter chips */}
            <div className="flex gap-1.5 mb-3">
                {(['all', 'win', 'loss'] as const).map(f => (
                    <button
                        key={f}
                        onClick={() => setFilter(f)}
                        className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${
                            filter === f
                                ? f === 'win'
                                    ? 'bg-[var(--color-profit-muted)] border-[rgba(34,197,94,0.3)] text-[var(--color-profit-text)]'
                                    : f === 'loss'
                                    ? 'bg-[var(--color-loss-muted)] border-[rgba(239,68,68,0.3)] text-[var(--color-loss-text)]'
                                    : 'bg-[var(--bg-surface)] border-[var(--border-default)] text-[var(--text-primary)]'
                                : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
                        }`}
                    >
                        {f === 'all' ? `All (${(trades ?? []).length})` : f === 'win' ? `Win (${(trades ?? []).filter(t => t.pnl > 0).length})` : `Loss (${(trades ?? []).filter(t => t.pnl <= 0).length})`}
                    </button>
                ))}
            </div>

            {filteredTrades.length === 0 ? (
                <div className="text-center py-6 text-[var(--text-muted)] text-xs">
                    No trades yet
                </div>
            ) : (
                <div className="space-y-1.5 max-h-96 overflow-y-auto pr-0.5">
                    {filteredTrades.map((trade) => {
                        const duration = trade.duration_minutes ?? trade.market_conditions?.duration_minutes ?? 0;
                        const stratLabel = trade.strategy_name ?? 'unknown';
                        const exitReason = trade.exit_reason ?? trade.reason ?? '—';
                        const legs = trade.legs ?? [];

                        return (
                            <div
                                key={trade.trade_id ?? trade.position_id}
                                className={`p-2 rounded-md border text-[11px] ${
                                    trade.pnl >= 0
                                        ? 'bg-[var(--color-profit-muted)] border-[rgba(34,197,94,0.12)]'
                                        : 'bg-[var(--color-loss-muted)] border-[rgba(239,68,68,0.12)]'
                                }`}
                            >
                                <div className="flex items-center justify-between mb-1">
                                    <div className="flex items-center gap-2">
                                        <span className="font-semibold text-[var(--text-primary)] capitalize">
                                            {stratLabel.replace(/_/g, ' ')}
                                        </span>
                                        {legs.length > 1 && (
                                            <span className="text-[9px] bg-[var(--bg-surface)] border border-[var(--border-subtle)] px-1 rounded text-[var(--text-muted)]">
                                                {legs.length}L
                                            </span>
                                        )}
                                        {(trade as any).trade_type && (
                                            <span className={`text-[9px] px-1 rounded font-medium ${
                                                (trade as any).trade_type === 'CREDIT'
                                                    ? 'bg-[rgba(34,197,94,0.1)] text-[var(--color-profit-text)]'
                                                    : 'bg-[rgba(239,68,68,0.1)] text-[var(--color-loss-text)]'
                                            }`}>
                                                {(trade as any).trade_type}
                                            </span>
                                        )}
                                    </div>
                                    <span className={`mono font-bold ${pnlClass(trade.pnl)}`}>
                                        {trade.pnl >= 0 ? '+' : ''}₹{fmt(trade.pnl)} ({trade.pnl_pct >= 0 ? '+' : ''}{fmt(trade.pnl_pct)}%)
                                    </span>
                                </div>

                                <div className="flex items-center justify-between text-[10px] text-[var(--text-muted)] mono">
                                    <span>{formatTime(trade.entry_time)}</span>
                                    <span>{formatDuration(duration)}</span>
                                    <span className="capitalize">{exitReason.toLowerCase().replace(/_/g, ' ')}</span>
                                </div>

                                {/* Premiums */}
                                <div className="flex items-center gap-3 mt-1 text-[10px] mono text-[var(--text-tertiary)]">
                                    <span>
                                        Entry {(trade as any).trade_type === 'CREDIT' ? '+' : '-'}₹{fmt(trade.entry_premium)}
                                    </span>
                                    <span>→</span>
                                    <span>
                                        Exit {(trade as any).trade_type === 'CREDIT' ? '-' : '+'}₹{fmt(trade.exit_premium)}
                                    </span>
                                </div>

                                {/* Legs summary */}
                                {legs.length > 0 && (
                                    <div className="mt-1 flex flex-wrap gap-1">
                                        {legs.map((leg, i) => (
                                            <span
                                                key={i}
                                                className={`text-[9px] px-1 rounded ${
                                                    leg.transaction_type === 'SELL'
                                                        ? 'bg-[rgba(239,68,68,0.1)] text-[var(--color-loss-text)]'
                                                        : 'bg-[rgba(34,197,94,0.1)] text-[var(--color-profit-text)]'
                                                }`}
                                            >
                                                {leg.transaction_type} {leg.strike ?? ''} {leg.option_type}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </Card>
    );
});

TradeJournal.displayName = 'TradeJournal';
export default TradeJournal;
