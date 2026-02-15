import React from 'react';
import Card from '../../shared/Card';
import { Zap } from 'lucide-react';
import type { GreeksInfo } from '../../types/api';

interface GreeksTableProps {
    greeks?: GreeksInfo;
}

const GreeksTable: React.FC<GreeksTableProps> = React.memo(({ greeks }) => {
    if (!greeks || !greeks.ce || !greeks.pe) {
        return (
            <Card
                compact
                header={
                    <div className="flex items-center gap-2">
                        <Zap size={14} className="text-[var(--accent-purple)]" />
                        <span className="text-sm font-medium">Option Greeks</span>
                    </div>
                }
            >
                <div className="text-center py-6 text-[var(--text-muted)] text-sm">
                    Waiting for Greeks data…
                </div>
            </Card>
        );
    }

    const { ce, pe, atm_strike, expiry_date } = greeks;

    const metrics = [
        { key: 'Delta', ce: ce.delta, pe: pe.delta, fmt: 3 },
        { key: 'Gamma', ce: ce.gamma, pe: pe.gamma, fmt: 4 },
        { key: 'Theta', ce: ce.theta, pe: pe.theta, fmt: 2, warn: true },
        { key: 'Vega', ce: ce.vega, pe: pe.vega, fmt: 4 },
        { key: 'IV', ce: ce.iv ? ce.iv * 100 : undefined, pe: pe.iv ? pe.iv * 100 : undefined, fmt: 1, suffix: '%' },
        { key: 'Price', ce: ce.price, pe: pe.price, fmt: 2, prefix: '₹' },
    ];

    return (
        <Card compact>
            {/* Header with ATM info */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <Zap size={14} className="text-[var(--accent-purple)]" />
                    <span className="text-sm font-medium">Option Greeks</span>
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5">
                        <span className="label">ATM</span>
                        <span className="mono text-sm font-bold">₹{atm_strike}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <span className="label">Exp</span>
                        <span className="mono text-[11px] text-[var(--text-secondary)]">{expiry_date}</span>
                    </div>
                </div>
            </div>

            {/* Greeks Table */}
            <div className="overflow-x-auto">
                <table className="w-full text-[11px]">
                    <thead>
                        <tr className="border-b border-[var(--border-subtle)]">
                            <th className="text-left py-1.5 text-[var(--text-muted)] font-medium">Greek</th>
                            <th className="text-right py-1.5 font-medium" style={{ color: 'var(--ce-color)' }}>CE</th>
                            <th className="text-right py-1.5 font-medium" style={{ color: 'var(--pe-color)' }}>PE</th>
                        </tr>
                    </thead>
                    <tbody>
                        {metrics.map((m) => (
                            <tr key={m.key} className="border-b border-[var(--border-subtle)] last:border-0">
                                <td className="py-1.5 text-[var(--text-secondary)] font-medium">{m.key}</td>
                                <td className="py-1.5 text-right mono font-semibold" style={{ color: 'var(--ce-color)' }}>
                                    {m.prefix || ''}{m.ce != null ? m.ce.toFixed(m.fmt) : '--'}{m.suffix || ''}
                                </td>
                                <td className="py-1.5 text-right mono font-semibold" style={{ color: 'var(--pe-color)' }}>
                                    {m.prefix || ''}{m.pe != null ? m.pe.toFixed(m.fmt) : '--'}{m.suffix || ''}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </Card>
    );
});

GreeksTable.displayName = 'GreeksTable';
export default GreeksTable;
