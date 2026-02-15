import React from 'react';
import Card from '../../shared/Card';
import { CheckCircle, XCircle } from 'lucide-react';
import type { FilterData } from '../../types/api';

interface FilterMatrixProps {
    filters?: FilterData;
}

const filterLabels: Record<string, string> = {
    ema_crossover: 'EMA',
    rsi: 'RSI',
    volatility: 'ATR',
    entry_confirmation: 'Confirm',
    greeks: 'Greeks',
    pcr: 'PCR',
    // Intelligence
    market_regime: 'Regime',
    iv_rank: 'IV Rank',
    market_breadth: 'Breadth',
    order_book: 'Book',
    vix: 'VIX',
    pcr_trend: 'PCR Tr',
    time_of_day: 'Time',
    oi_buildup: 'OI',
    expiry_day: 'Expiry',
};

const FilterMatrix: React.FC<FilterMatrixProps> = React.memo(({ filters }) => {
    const safeFilters = filters || ({} as Record<string, boolean>);
    const entries = Object.entries(filterLabels);
    const passedCount = entries.filter(([key]) => (safeFilters as any)[key]).length;

    return (
        <Card compact>
            <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium">Filters</span>
                <span className="mono text-xs text-[var(--text-tertiary)]">
                    <span
                        className={
                            passedCount >= 10
                                ? 'text-[var(--color-profit-text)]'
                                : passedCount >= 7
                                    ? 'text-[var(--color-warning)]'
                                    : 'text-[var(--color-loss-text)]'
                        }
                    >
                        {passedCount}
                    </span>
                    /{entries.length}
                </span>
            </div>

            <div className="grid grid-cols-3 gap-1.5">
                {entries.map(([key, label]) => {
                    const passed = (safeFilters as any)[key] ?? false;
                    return (
                        <div
                            key={key}
                            className={`
                flex items-center gap-1.5 px-2 py-1.5 rounded-md text-[11px] font-medium transition-colors
                ${passed
                                    ? 'bg-[var(--color-profit-muted)] text-[var(--color-profit-text)]'
                                    : 'bg-[var(--bg-hover)] text-[var(--text-muted)]'
                                }
              `}
                        >
                            {passed ? (
                                <CheckCircle size={12} className="flex-shrink-0" />
                            ) : (
                                <XCircle size={12} className="flex-shrink-0 opacity-50" />
                            )}
                            {label}
                        </div>
                    );
                })}
            </div>
        </Card>
    );
});

FilterMatrix.displayName = 'FilterMatrix';
export default FilterMatrix;
