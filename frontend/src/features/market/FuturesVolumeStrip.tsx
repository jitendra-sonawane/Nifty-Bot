import React, { useMemo } from 'react';
import type { FuturesVolumeData } from '../../types/api';

interface FuturesVolumeStripProps {
    data: FuturesVolumeData | null | undefined;
    height?: number;
}

/** Format large numbers: 1234567 -> "12.3L", 45000 -> "45.0K" */
function formatVolume(v: number): string {
    if (v >= 100000) return (v / 100000).toFixed(1) + 'L';
    if (v >= 1000) return (v / 1000).toFixed(1) + 'K';
    return v.toFixed(0);
}

const FuturesVolumeStrip: React.FC<FuturesVolumeStripProps> = ({ data, height = 160 }) => {
    const chartHeight = height - 52;
    const svgWidth = 100;

    const { bars, cvdPath, timeLabels } = useMemo(() => {
        if (!data || !data.candles || data.candles.length === 0) {
            return { bars: [], cvdPath: '', timeLabels: [] };
        }

        const candles = data.candles;
        const n = candles.length;

        const maxVol = Math.max(...candles.map((c) => c.total_volume), 1);

        const cvdValues = candles.map((c) => c.cvd);
        const cvdMin = Math.min(...cvdValues);
        const cvdMax = Math.max(...cvdValues);
        const cvdRange = cvdMax - cvdMin || 1;

        const pad = 4;
        const barGap = 0.4;
        const barW = Math.max((svgWidth - pad * 2) / n - barGap, 0.5);

        const bars = candles.map((c, i) => {
            const x = pad + i * ((svgWidth - pad * 2) / n);
            const barH = (c.total_volume / maxVol) * (chartHeight - pad * 2);
            const y = chartHeight - pad - barH;
            const isBuy = c.delta >= 0;
            return { x, y, w: barW, h: barH, isBuy, time: c.time };
        });

        const cvdPts = candles.map((c, i) => {
            const x = pad + i * ((svgWidth - pad * 2) / n) + barW / 2;
            const y = pad + (1 - (c.cvd - cvdMin) / cvdRange) * (chartHeight - pad * 2);
            return `${x.toFixed(2)},${y.toFixed(2)}`;
        });
        const cvdPath = 'M' + cvdPts.join(' L');

        const labelInterval = Math.max(Math.floor(n / 6), 1);
        const timeLabels = candles
            .filter((_, i) => i % labelInterval === 0)
            .map((c) => {
                const idx = candles.indexOf(c);
                const x = pad + idx * ((svgWidth - pad * 2) / n) + barW / 2;
                return { x, label: c.time };
            });

        return { bars, cvdPath, timeLabels };
    }, [data, chartHeight]);

    if (!data || !data.candles || data.candles.length === 0) {
        return (
            <div
                className="surface-elevated rounded-xl flex items-center justify-center text-[var(--text-muted)] text-sm"
                style={{ height }}
            >
                Waiting for futures volume data...
            </div>
        );
    }

    const cvdColor = data.current_cvd >= 0 ? 'var(--color-profit-text)' : 'var(--color-loss-text)';
    const deltaColor = data.current_delta >= 0 ? 'var(--color-profit-text)' : 'var(--color-loss-text)';

    return (
        <div className="surface-elevated rounded-xl overflow-hidden" style={{ height }}>
            {/* Header */}
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '6px 12px',
                    borderBottom: '1px solid var(--border-subtle)',
                }}
            >
                <span
                    style={{
                        fontSize: 'var(--text-sm)',
                        fontWeight: 600,
                        color: 'var(--text-secondary)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                    }}
                >
                    Futures Volume
                </span>
                <div style={{ display: 'flex', gap: '12px', fontSize: '11px' }}>
                    <span style={{ color: 'var(--text-tertiary)' }}>
                        LTP{' '}
                        <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                            {data.futures_ltp.toFixed(1)}
                        </span>
                    </span>
                    <span style={{ color: 'var(--text-tertiary)' }}>
                        CVD{' '}
                        <span style={{ color: cvdColor, fontWeight: 600 }}>
                            {data.current_cvd >= 0 ? '+' : ''}
                            {formatVolume(data.current_cvd)}
                        </span>
                    </span>
                    <span style={{ color: 'var(--text-tertiary)' }}>
                        Delta{' '}
                        <span style={{ color: deltaColor, fontWeight: 600 }}>
                            {data.current_delta >= 0 ? '+' : ''}
                            {formatVolume(data.current_delta)}
                        </span>
                    </span>
                    <span style={{ color: 'var(--text-tertiary)' }}>
                        Vol{' '}
                        <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                            {formatVolume(data.total_volume)}
                        </span>
                    </span>
                </div>
            </div>

            {/* Chart */}
            <svg
                viewBox={`0 0 ${svgWidth} ${chartHeight}`}
                className="w-full"
                style={{ height: chartHeight }}
                preserveAspectRatio="none"
            >
                {/* Volume bars */}
                {bars.map((bar, i) => (
                    <rect
                        key={i}
                        x={bar.x}
                        y={bar.y}
                        width={bar.w}
                        height={Math.max(bar.h, 0.3)}
                        fill={bar.isBuy ? 'rgba(34,197,94,0.5)' : 'rgba(239,68,68,0.5)'}
                        rx={0.2}
                    />
                ))}

                {/* CVD line */}
                {cvdPath && (
                    <polyline
                        points={cvdPath.replace('M', '').replace(/L/g, ' ')}
                        fill="none"
                        stroke="var(--accent-blue)"
                        strokeWidth="0.6"
                        strokeLinejoin="round"
                    />
                )}
            </svg>

            {/* X-axis time labels */}
            <div
                style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '0 12px 4px',
                    fontSize: '9px',
                    color: 'var(--text-muted)',
                }}
            >
                {timeLabels.map((tl, i) => (
                    <span key={i}>{tl.label}</span>
                ))}
            </div>
        </div>
    );
};

export default FuturesVolumeStrip;
