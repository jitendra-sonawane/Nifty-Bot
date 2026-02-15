import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { NIFTY50_COMPANIES, type Nifty50Company } from '../../data/nifty50Data';
import './NiftyHeatmap.css';

/* ═══════════════════════════════════════════
   TYPES
   ═══════════════════════════════════════════ */

export interface HeatmapStock {
    symbol: string;
    price: number;
    change: number;
    changePercent: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

interface TileRect {
    x: number;
    y: number;
    w: number;
    h: number;
    company: Nifty50Company;
    stock?: HeatmapStock;
}

interface TooltipData {
    company: Nifty50Company;
    stock?: HeatmapStock;
    x: number;
    y: number;
}

interface NiftyHeatmapProps {
    data?: HeatmapStock[];
    isLoading?: boolean;
    height?: number;
}

/* ═══════════════════════════════════════════
   SECTOR CONFIGURATION
   ═══════════════════════════════════════════ */

// Maps sector field values from nifty50Data to display config
const SECTOR_DISPLAY_CONFIG: Record<string, { label: string; color: string }> = {
    'Financials':     { label: 'Fin',    color: 'var(--sector-financials)' },
    'IT':             { label: 'IT',     color: 'var(--sector-it)' },
    'Energy':         { label: 'Energy', color: 'var(--sector-energy)' },
    'FMCG':           { label: 'FMCG',   color: 'var(--sector-fmcg)' },
    'Automobile':     { label: 'Auto',   color: 'var(--sector-automobile)' },
    'Metals':         { label: 'Metals', color: 'var(--sector-metals)' },
    'Pharma':         { label: 'Pharma', color: 'var(--sector-pharma)' },
    'Healthcare':     { label: 'Health', color: 'var(--sector-healthcare)' },
    'Telecom':        { label: 'Telco',  color: 'var(--sector-telecom)' },
    'Cement':         { label: 'Cement', color: 'var(--sector-cement)' },
    'Infrastructure': { label: 'Infra',  color: 'var(--sector-infrastructure)' },
    'Construction':   { label: 'Const',  color: 'var(--sector-construction)' },
    'Consumer':       { label: 'Consmr', color: 'var(--sector-consumer)' },
    'Defence':        { label: 'Def',    color: 'var(--sector-defence)' },
};

// Filter chip groups — each key maps to raw sector strings it includes
const NIFTY_SECTOR_FILTER_GROUPS: Record<string, string[]> = {
    'All':     [],
    'Banking': ['Financials'],
    'IT':      ['IT'],
    'Energy':  ['Energy'],
    'Auto':    ['Automobile'],
    'FMCG':    ['FMCG'],
    'Pharma':  ['Pharma', 'Healthcare'],
    'Metals':  ['Metals'],
    'Infra':   ['Infrastructure', 'Construction', 'Cement'],
    'Others':  ['Telecom', 'Consumer', 'Defence'],
};

/* ═══════════════════════════════════════════
   SQUARIFIED TREEMAP ALGORITHM
   ═══════════════════════════════════════════ */

interface TreeNode {
    value: number;
    index: number;
}

function squarify(
    nodes: TreeNode[],
    x: number,
    y: number,
    width: number,
    height: number
): { x: number; y: number; w: number; h: number; index: number }[] {
    const totalValue = nodes.reduce((sum, n) => sum + n.value, 0);
    if (totalValue <= 0 || nodes.length === 0) return [];

    const rects: { x: number; y: number; w: number; h: number; index: number }[] = [];
    let remaining = [...nodes];
    let cx = x, cy = y, cw = width, ch = height;

    while (remaining.length > 0) {
        const isHorizontal = cw >= ch;
        const side = isHorizontal ? ch : cw;
        const remainingTotal = remaining.reduce((s, n) => s + n.value, 0);

        // Find the best row
        let row: TreeNode[] = [];
        let rowTotal = 0;
        let bestAspect = Infinity;

        for (let i = 0; i < remaining.length; i++) {
            const candidate = [...row, remaining[i]];
            const candidateTotal = rowTotal + remaining[i].value;
            const rowSize = (candidateTotal / remainingTotal) * (isHorizontal ? cw : ch);

            // Calculate worst aspect ratio in this row
            let worstAspect = 0;
            for (const node of candidate) {
                const nodeSize = (node.value / candidateTotal) * side;
                const aspect = Math.max(rowSize / nodeSize, nodeSize / rowSize);
                worstAspect = Math.max(worstAspect, aspect);
            }

            if (worstAspect <= bestAspect) {
                row = candidate;
                rowTotal = candidateTotal;
                bestAspect = worstAspect;
            } else {
                break;
            }
        }

        // Layout this row
        const rowFraction = rowTotal / remainingTotal;
        const rowSize = isHorizontal
            ? cw * rowFraction
            : ch * rowFraction;

        let offset = 0;
        for (const node of row) {
            const nodeFraction = node.value / rowTotal;
            const nodeSize = side * nodeFraction;

            if (isHorizontal) {
                rects.push({
                    x: cx,
                    y: cy + offset,
                    w: rowSize,
                    h: nodeSize,
                    index: node.index,
                });
            } else {
                rects.push({
                    x: cx + offset,
                    y: cy,
                    w: nodeSize,
                    h: rowSize,
                    index: node.index,
                });
            }
            offset += nodeSize;
        }

        // Update remaining area
        if (isHorizontal) {
            cx += rowSize;
            cw -= rowSize;
        } else {
            cy += rowSize;
            ch -= rowSize;
        }

        remaining = remaining.slice(row.length);
    }

    return rects;
}

/* ═══════════════════════════════════════════
   COLOR MAPPING
   ═══════════════════════════════════════════ */

function getChangeColor(pct: number | undefined): string {
    if (pct === undefined || pct === null) return 'hsl(220, 10%, 25%)'; // neutral gray

    // Clamp between -4 and +4 for color mapping
    const clamped = Math.max(-4, Math.min(4, pct));

    if (clamped >= 0) {
        // Green scale: 0% → dark green, 4% → bright green
        const intensity = Math.min(clamped / 3, 1);
        const lightness = 18 + intensity * 14;
        const saturation = 40 + intensity * 35;
        return `hsl(145, ${saturation}%, ${lightness}%)`;
    } else {
        // Red scale: 0% → dark red, -4% → bright red
        const intensity = Math.min(Math.abs(clamped) / 3, 1);
        const lightness = 18 + intensity * 14;
        const saturation = 40 + intensity * 40;
        return `hsl(0, ${saturation}%, ${lightness}%)`;
    }
}

/* ═══════════════════════════════════════════
   FONT SIZE CALCULATION
   ═══════════════════════════════════════════ */

function getTileFontSizes(w: number, h: number): { symbol: number; change: number; show: 'both' | 'symbol' | 'none' } {
    const minDim = Math.min(w, h);
    const area = w * h;

    if (minDim < 24 || area < 800) return { symbol: 0, change: 0, show: 'none' };
    if (minDim < 36 || area < 1500) return { symbol: Math.min(9, minDim * 0.35), change: 0, show: 'symbol' };

    const symbolSize = Math.min(14, Math.max(9, minDim * 0.22));
    const changeSize = Math.min(11, Math.max(8, minDim * 0.18));
    return { symbol: symbolSize, change: changeSize, show: 'both' };
}

/* ═══════════════════════════════════════════
   MARKET BREADTH COMPUTATION
   ═══════════════════════════════════════════ */

interface BreadthStats {
    advancing: number;
    declining: number;
    unchanged: number;
    avgChange: number;
    weightedAvg: number;
    trendLabel: string;
    trendColor: string;
}

function computeBreadth(stocks: HeatmapStock[] | undefined): BreadthStats | null {
    if (!stocks || stocks.length === 0) return null;

    let advancing = 0, declining = 0, unchanged = 0;
    let totalChange = 0;
    let weightedSum = 0, totalWeight = 0;

    const symbolToCompany = new Map(NIFTY50_COMPANIES.map(c => [c.symbol, c]));

    for (const s of stocks) {
        if (s.changePercent > 0.01) advancing++;
        else if (s.changePercent < -0.01) declining++;
        else unchanged++;

        totalChange += s.changePercent;

        const company = symbolToCompany.get(s.symbol);
        const w = company?.weightage ?? 1;
        weightedSum += s.changePercent * w;
        totalWeight += w;
    }

    const avgChange = totalChange / stocks.length;
    const weightedAvg = totalWeight > 0 ? weightedSum / totalWeight : 0;

    let trendLabel: string;
    let trendColor: string;
    if (weightedAvg > 1.0) { trendLabel = 'Strong Bullish'; trendColor = '#22c55e'; }
    else if (weightedAvg > 0.3) { trendLabel = 'Bullish'; trendColor = '#4ade80'; }
    else if (weightedAvg > 0.05) { trendLabel = 'Mildly Bullish'; trendColor = '#86efac'; }
    else if (weightedAvg > -0.05) { trendLabel = 'Neutral'; trendColor = '#94a3b8'; }
    else if (weightedAvg > -0.3) { trendLabel = 'Mildly Bearish'; trendColor = '#fca5a5'; }
    else if (weightedAvg > -1.0) { trendLabel = 'Bearish'; trendColor = '#f87171'; }
    else { trendLabel = 'Strong Bearish'; trendColor = '#ef4444'; }

    return { advancing, declining, unchanged, avgChange, weightedAvg, trendLabel, trendColor };
}

/* ═══════════════════════════════════════════
   COMPONENT
   ═══════════════════════════════════════════ */

const NiftyHeatmap: React.FC<NiftyHeatmapProps> = ({ data, isLoading, height = 340 }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [containerWidth, setContainerWidth] = useState(0);
    const [tooltip, setTooltip] = useState<TooltipData | null>(null);
    const [activeSector, setActiveSector] = useState<string>('All');

    // Observe container width
    useEffect(() => {
        const el = containerRef.current;
        if (!el) return;

        const rect = el.getBoundingClientRect();
        if (rect.width > 0) {
            setContainerWidth(rect.width);
        }

        const ro = new ResizeObserver((entries) => {
            for (const entry of entries) {
                setContainerWidth(entry.contentRect.width);
            }
        });
        ro.observe(el);
        return () => ro.disconnect();
    }, [isLoading, !!data]);

    // Match stock data to company data
    const stockMap = useMemo(() => {
        const map = new Map<string, HeatmapStock>();
        if (data) {
            for (const s of data) {
                map.set(s.symbol, s);
            }
        }
        return map;
    }, [data]);

    // Sector-to-color lookup
    const sectorColorMap = useMemo(() => {
        const map = new Map<string, string>();
        for (const [sector, config] of Object.entries(SECTOR_DISPLAY_CONFIG)) {
            map.set(sector, config.color);
        }
        return map;
    }, []);

    // Filter companies by active sector
    const filteredCompanies = useMemo(() => {
        if (activeSector === 'All') return NIFTY50_COMPANIES;
        const targetSectors = NIFTY_SECTOR_FILTER_GROUPS[activeSector] ?? [];
        return NIFTY50_COMPANIES.filter(c => targetSectors.includes(c.sector));
    }, [activeSector]);

    // Compute treemap layout
    const tiles = useMemo<TileRect[]>(() => {
        if (containerWidth <= 0) return [];

        const sorted = [...filteredCompanies].sort((a, b) => b.weightage - a.weightage);

        const nodes: TreeNode[] = sorted.map((c, i) => ({
            value: c.weightage,
            index: i,
        }));

        const rects = squarify(nodes, 0, 0, containerWidth, height);

        return rects.map((r) => ({
            x: r.x,
            y: r.y,
            w: r.w,
            h: r.h,
            company: sorted[r.index],
            stock: stockMap.get(sorted[r.index].symbol),
        }));
    }, [containerWidth, height, stockMap, filteredCompanies]);

    // Tooltip handlers
    const handleMouseEnter = useCallback((e: React.MouseEvent, tile: TileRect) => {
        setTooltip({
            company: tile.company,
            stock: tile.stock,
            x: e.clientX,
            y: e.clientY,
        });
    }, []);

    const handleMouseMove = useCallback((e: React.MouseEvent) => {
        setTooltip((prev) => prev ? { ...prev, x: e.clientX, y: e.clientY } : null);
    }, []);

    const handleMouseLeave = useCallback(() => {
        setTooltip(null);
    }, []);

    const breadth = computeBreadth(data);

    // Loading state
    if (isLoading && !data) {
        return (
            <div className="heatmap-container" style={{ height }}>
                <div className="heatmap-loading" style={{ height }}>
                    <div className="heatmap-loading-spinner" />
                    <span>Loading Nifty 50 data…</span>
                </div>
            </div>
        );
    }

    return (
        <div className="heatmap-container">
            {/* Market Breadth Summary */}
            {breadth && (
                <div className="heatmap-breadth">
                    <div className="heatmap-breadth-left">
                        <span className="heatmap-breadth-dot" style={{ background: breadth.trendColor }} />
                        <span className="heatmap-breadth-trend" style={{ color: breadth.trendColor }}>
                            {breadth.trendLabel}
                        </span>
                        <span className="heatmap-breadth-avg" style={{ color: breadth.weightedAvg >= 0 ? 'var(--color-profit-text)' : 'var(--color-loss-text)' }}>
                            {breadth.weightedAvg >= 0 ? '+' : ''}{breadth.weightedAvg.toFixed(2)}%
                        </span>
                    </div>
                    <div className="heatmap-breadth-right">
                        <span className="heatmap-breadth-stat advancing">
                            ▲ {breadth.advancing}
                        </span>
                        <span className="heatmap-breadth-divider">·</span>
                        <span className="heatmap-breadth-stat declining">
                            ▼ {breadth.declining}
                        </span>
                        {breadth.unchanged > 0 && (
                            <>
                                <span className="heatmap-breadth-divider">·</span>
                                <span className="heatmap-breadth-stat unchanged">
                                    — {breadth.unchanged}
                                </span>
                            </>
                        )}
                    </div>
                </div>
            )}

            {/* Sector Filter Strip */}
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '6px 12px',
                    borderBottom: '1px solid var(--border-subtle)',
                    overflowX: 'auto',
                    scrollbarWidth: 'none',
                }}
            >
                {Object.keys(NIFTY_SECTOR_FILTER_GROUPS).map((sectorKey) => {
                    const isActive = activeSector === sectorKey;
                    // Pick color: for non-All chips, use first mapped sector's color
                    const rawSectors = NIFTY_SECTOR_FILTER_GROUPS[sectorKey];
                    const chipColor = rawSectors.length > 0
                        ? (SECTOR_DISPLAY_CONFIG[rawSectors[0]]?.color ?? 'var(--text-tertiary)')
                        : 'var(--accent-indigo)';

                    return (
                        <button
                            key={sectorKey}
                            onClick={() => setActiveSector(sectorKey)}
                            style={{
                                flexShrink: 0,
                                padding: '2px 8px',
                                borderRadius: '9999px',
                                fontSize: '10px',
                                fontWeight: 600,
                                cursor: 'pointer',
                                transition: 'all 0.15s',
                                border: `1px solid ${isActive ? chipColor : 'transparent'}`,
                                background: isActive ? `${chipColor}26` : 'transparent',
                                color: isActive ? chipColor : 'var(--text-muted)',
                            }}
                        >
                            {sectorKey}
                        </button>
                    );
                })}
            </div>

            {/* Treemap */}
            <div
                ref={containerRef}
                className="heatmap-grid"
                style={{ height }}
            >
                {tiles.map((tile) => {
                    const pct = tile.stock?.changePercent;
                    const bg = getChangeColor(pct);
                    const fonts = getTileFontSizes(tile.w, tile.h);
                    const sectorColor = sectorColorMap.get(tile.company.sector);

                    return (
                        <div
                            key={tile.company.symbol}
                            className="heatmap-tile"
                            style={{
                                left: tile.x,
                                top: tile.y,
                                width: tile.w,
                                height: tile.h,
                                backgroundColor: bg,
                                borderTop: sectorColor ? `2px solid ${sectorColor}` : undefined,
                            }}
                            onMouseEnter={(e) => handleMouseEnter(e, tile)}
                            onMouseMove={handleMouseMove}
                            onMouseLeave={handleMouseLeave}
                        >
                            {fonts.show !== 'none' && (
                                <span
                                    className="heatmap-tile-symbol"
                                    style={{ fontSize: fonts.symbol }}
                                >
                                    {tile.company.symbol}
                                </span>
                            )}
                            {fonts.show === 'both' && pct !== undefined && (
                                <span
                                    className="heatmap-tile-change"
                                    style={{ fontSize: fonts.change }}
                                >
                                    {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
                                </span>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Tooltip */}
            {tooltip && (
                <div
                    className="heatmap-tooltip"
                    style={{
                        left: Math.min(tooltip.x + 12, window.innerWidth - 220),
                        top: Math.min(tooltip.y + 12, window.innerHeight - 200),
                    }}
                >
                    <div className="heatmap-tooltip-symbol">{tooltip.company.symbol}</div>
                    <div className="heatmap-tooltip-name">
                        {tooltip.company.name} · <span style={{ color: sectorColorMap.get(tooltip.company.sector) ?? 'var(--text-tertiary)' }}>{tooltip.company.sector}</span>
                    </div>
                    {tooltip.stock ? (
                        <>
                            <div className="heatmap-tooltip-row">
                                <span className="label">Price</span>
                                <span className="value">₹{tooltip.stock.price.toLocaleString('en-IN')}</span>
                            </div>
                            <div className="heatmap-tooltip-row">
                                <span className="label">Change</span>
                                <span className={`value ${tooltip.stock.change >= 0 ? 'profit' : 'loss'}`}>
                                    {tooltip.stock.change >= 0 ? '+' : ''}
                                    {tooltip.stock.change.toFixed(2)} ({tooltip.stock.changePercent >= 0 ? '+' : ''}
                                    {tooltip.stock.changePercent.toFixed(2)}%)
                                </span>
                            </div>
                            <div className="heatmap-tooltip-row">
                                <span className="label">Day Range</span>
                                <span className="value">
                                    ₹{tooltip.stock.low.toLocaleString('en-IN')} — ₹{tooltip.stock.high.toLocaleString('en-IN')}
                                </span>
                            </div>
                            <div className="heatmap-tooltip-row">
                                <span className="label">Volume</span>
                                <span className="value">
                                    {tooltip.stock.volume >= 1e7
                                        ? (tooltip.stock.volume / 1e7).toFixed(2) + ' Cr'
                                        : tooltip.stock.volume >= 1e5
                                            ? (tooltip.stock.volume / 1e5).toFixed(2) + ' L'
                                            : tooltip.stock.volume.toLocaleString('en-IN')}
                                </span>
                            </div>
                            <div className="heatmap-tooltip-row">
                                <span className="label">Weight</span>
                                <span className="value">{tooltip.company.weightage}%</span>
                            </div>
                        </>
                    ) : (
                        <div className="heatmap-tooltip-row">
                            <span className="label">Weight</span>
                            <span className="value">{tooltip.company.weightage}%</span>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default NiftyHeatmap;
