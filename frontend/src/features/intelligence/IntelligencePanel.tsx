import React, { useState } from 'react';
import {
    Brain,
    ChevronDown,
    ChevronUp,
    TrendingUp,
    BarChart2,
    BookOpen,
    Users,
    Activity,
    Layers,
} from 'lucide-react';
import type {
    IntelligenceContext,
    MarketRegimeContext,
    IVRankContext,
    MarketBreadthContext,
    OrderBookContext,
    PortfolioGreeksContext,
    OIAnalysisContext,
} from '../../types/api';

interface IntelligencePanelProps {
    intelligence?: IntelligenceContext;
    onToggleModule: (module: string, enabled: boolean) => void;
}

// ── Helpers ────────────────────────────────────────────────────────────────

const regimeColor: Record<string, string> = {
    TRENDING: 'var(--accent-blue)',
    RANGING: 'var(--color-warning)',
    HIGH_VOLATILITY: 'var(--color-loss-text)',
    UNKNOWN: 'var(--text-muted)',
};

const biasColor: Record<string, string> = {
    STRONG_BULLISH: 'var(--color-profit-text)',
    BULLISH: 'var(--color-profit-text)',
    NEUTRAL: 'var(--text-secondary)',
    BEARISH: 'var(--color-loss-text)',
    STRONG_BEARISH: 'var(--color-loss-text)',
};

const riskColor: Record<string, string> = {
    HIGH: 'var(--color-loss-text)',
    MEDIUM: 'var(--color-warning)',
    LOW: 'var(--color-profit-text)',
};

const recColor: Record<string, string> = {
    SELL_PREMIUM: 'var(--color-profit-text)',
    BUY_DEBIT: 'var(--accent-blue)',
    NEUTRAL: 'var(--text-muted)',
};

function ToggleSwitch({
    enabled,
    onChange,
}: {
    enabled: boolean;
    onChange: (v: boolean) => void;
}) {
    return (
        <button
            onClick={(e) => { e.stopPropagation(); onChange(!enabled); }}
            title={enabled ? 'Disable module' : 'Enable module'}
            style={{
                width: 32,
                height: 18,
                borderRadius: 9,
                border: 'none',
                cursor: 'pointer',
                background: enabled ? 'var(--color-profit-text)' : 'var(--bg-overlay)',
                position: 'relative',
                transition: 'background 0.2s',
                flexShrink: 0,
            }}
        >
            <span style={{
                position: 'absolute',
                top: 2,
                left: enabled ? 16 : 2,
                width: 14,
                height: 14,
                borderRadius: '50%',
                background: 'white',
                transition: 'left 0.2s',
                display: 'block',
            }} />
        </button>
    );
}

function ModuleHeader({
    icon,
    label,
    enabled,
    onToggle,
    expanded,
    onExpand,
    badge,
    badgeColor,
}: {
    icon: React.ReactNode;
    label: string;
    enabled: boolean;
    onToggle: (v: boolean) => void;
    expanded: boolean;
    onExpand: () => void;
    badge?: string;
    badgeColor?: string;
}) {
    return (
        <div
            onClick={onExpand}
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                cursor: 'pointer',
                padding: '8px 0',
                opacity: enabled ? 1 : 0.45,
            }}
        >
            <span style={{ color: 'var(--text-secondary)', display: 'flex' }}>{icon}</span>
            <span style={{ flex: 1, fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{label}</span>
            {badge && (
                <span style={{
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '2px 6px',
                    borderRadius: 4,
                    background: (badgeColor || 'var(--text-muted)') + '22',
                    color: badgeColor || 'var(--text-muted)',
                    letterSpacing: '0.04em',
                }}>
                    {badge}
                </span>
            )}
            <ToggleSwitch enabled={enabled} onChange={onToggle} />
            <span style={{ color: 'var(--text-muted)' }}>
                {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </span>
        </div>
    );
}

// ── Module Sub-components ──────────────────────────────────────────────────

function MarketRegimeCard({ data, enabled, onToggle }: { data?: MarketRegimeContext; enabled: boolean; onToggle: (v: boolean) => void }) {
    const [expanded, setExpanded] = useState(true);
    const regime = data?.regime || 'UNKNOWN';
    return (
        <div style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 4 }}>
            <ModuleHeader
                icon={<TrendingUp size={13} />}
                label="Market Regime"
                enabled={enabled}
                onToggle={onToggle}
                expanded={expanded}
                onExpand={() => setExpanded(e => !e)}
                badge={regime}
                badgeColor={regimeColor[regime]}
            />
            {expanded && enabled && (
                <div style={{ paddingBottom: 8 }}>
                    {!data ? (
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Warming up…</span>
                    ) : (
                        <>
                            <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
                                <Chip label="ADX" value={data.adx != null ? data.adx.toFixed(1) : '—'} />
                                <Chip label="BB Width" value={data.bb_width_pct != null ? data.bb_width_pct.toFixed(2) + '%' : '—'} />
                                <Chip label="ATR%" value={data.atr_pct != null ? data.atr_pct.toFixed(2) + '%' : '—'} />
                            </div>
                            {data.allowed_strategies.length > 0 && (
                                <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                                    Allowed: {data.allowed_strategies.map(s => s.replace(/_/g, ' ')).join(' · ')}
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}
        </div>
    );
}

function IVRankCard({ data, enabled, onToggle }: { data?: IVRankContext; enabled: boolean; onToggle: (v: boolean) => void }) {
    const [expanded, setExpanded] = useState(true);
    const rec = data?.recommendation || 'NEUTRAL';
    return (
        <div style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 4 }}>
            <ModuleHeader
                icon={<BarChart2 size={13} />}
                label="IV Rank"
                enabled={enabled}
                onToggle={onToggle}
                expanded={expanded}
                onExpand={() => setExpanded(e => !e)}
                badge={rec.replace('_', ' ')}
                badgeColor={recColor[rec]}
            />
            {expanded && enabled && (
                <div style={{ paddingBottom: 8 }}>
                    {data?.iv_rank == null ? (
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            {data?.history_size != null ? `Building history (${data.history_size} samples)…` : 'Waiting for IV data…'}
                        </span>
                    ) : (
                        <>
                            {/* IV Rank bar */}
                            <div style={{ marginBottom: 6 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 3 }}>
                                    <span>IV Rank</span>
                                    <span style={{ color: recColor[rec], fontWeight: 700 }}>{data.iv_rank.toFixed(1)}</span>
                                </div>
                                <div style={{ height: 5, background: 'var(--bg-overlay)', borderRadius: 3, overflow: 'hidden' }}>
                                    <div style={{
                                        height: '100%',
                                        width: `${data.iv_rank}%`,
                                        background: data.iv_rank >= 60 ? 'var(--color-profit-text)' : data.iv_rank <= 30 ? 'var(--accent-blue)' : 'var(--color-warning)',
                                        borderRadius: 3,
                                        transition: 'width 0.4s',
                                    }} />
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                <Chip label="IV" value={data.current_iv != null ? data.current_iv.toFixed(1) + '%' : '—'} />
                                <Chip label="30d Hi" value={data.iv_30d_high != null ? data.iv_30d_high.toFixed(1) + '%' : '—'} />
                                <Chip label="30d Lo" value={data.iv_30d_low != null ? data.iv_30d_low.toFixed(1) + '%' : '—'} />
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}

function MarketBreadthCard({ data, enabled, onToggle }: { data?: MarketBreadthContext; enabled: boolean; onToggle: (v: boolean) => void }) {
    const [expanded, setExpanded] = useState(true);
    const bias = data?.breadth_bias || 'NEUTRAL';
    return (
        <div style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 4 }}>
            <ModuleHeader
                icon={<Users size={13} />}
                label="Market Breadth"
                enabled={enabled}
                onToggle={onToggle}
                expanded={expanded}
                onExpand={() => setExpanded(e => !e)}
                badge={bias.replace('_', ' ')}
                badgeColor={biasColor[bias]}
            />
            {expanded && enabled && (
                <div style={{ paddingBottom: 8 }}>
                    {!data || data.coverage === 0 ? (
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Waiting for breadth data…</span>
                    ) : (
                        <>
                            {/* Advance-Decline bar */}
                            <div style={{ marginBottom: 6 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 3 }}>
                                    <span style={{ color: 'var(--color-profit-text)' }}>▲ {data.advancing}</span>
                                    <span>—{data.unchanged}</span>
                                    <span style={{ color: 'var(--color-loss-text)' }}>▼ {data.declining}</span>
                                </div>
                                <div style={{ height: 5, display: 'flex', borderRadius: 3, overflow: 'hidden' }}>
                                    <div style={{ flex: data.advancing, background: 'var(--color-profit-text)' }} />
                                    <div style={{ flex: data.unchanged, background: 'var(--bg-overlay)' }} />
                                    <div style={{ flex: data.declining, background: 'var(--color-loss-text)' }} />
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: 6 }}>
                                <Chip label="A/D" value={data.ad_ratio != null ? data.ad_ratio.toFixed(2) : '—'} />
                                <Chip label="Score" value={data.breadth_score.toString()} />
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}

function OrderBookCard({ data, enabled, onToggle }: { data?: OrderBookContext; enabled: boolean; onToggle: (v: boolean) => void }) {
    const [expanded, setExpanded] = useState(true);
    const signal = data?.imbalance_signal || 'NEUTRAL';
    const sigColor = signal === 'BULLISH' ? 'var(--color-profit-text)' : signal === 'BEARISH' ? 'var(--color-loss-text)' : 'var(--text-muted)';
    return (
        <div style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 4 }}>
            <ModuleHeader
                icon={<BookOpen size={13} />}
                label="Order Book"
                enabled={enabled}
                onToggle={onToggle}
                expanded={expanded}
                onExpand={() => setExpanded(e => !e)}
                badge={signal}
                badgeColor={sigColor}
            />
            {expanded && enabled && (
                <div style={{ paddingBottom: 8 }}>
                    {!data || (data.ce_imbalance == null && data.pe_imbalance == null) ? (
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Waiting for bid/ask data…</span>
                    ) : (
                        <>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, marginBottom: 6 }}>
                                <ImbalanceCell side="CE" imbalance={data.ce_imbalance} liquidity={data.ce_liquidity} spreadPct={data.ce_spread_pct} />
                                <ImbalanceCell side="PE" imbalance={data.pe_imbalance} liquidity={data.pe_liquidity} spreadPct={data.pe_spread_pct} />
                            </div>
                            <div style={{ display: 'flex', gap: 6 }}>
                                <Chip label="Quality" value={data.entry_quality + '/100'} />
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}

function ImbalanceCell({ side, imbalance, liquidity, spreadPct }: { side: string; imbalance: number | null; liquidity: string; spreadPct: number | null }) {
    const liqColor: Record<string, string> = { EXCELLENT: 'var(--color-profit-text)', GOOD: 'var(--color-warning)', POOR: 'var(--color-loss-text)', UNKNOWN: 'var(--text-muted)' };
    return (
        <div style={{ background: 'var(--bg-overlay)', borderRadius: 4, padding: '4px 6px' }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 2 }}>{side}</div>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)' }}>
                {imbalance != null ? imbalance.toFixed(2) + '×' : '—'}
            </div>
            <div style={{ fontSize: 10, color: liqColor[liquidity] || 'var(--text-muted)' }}>
                {liquidity} {spreadPct != null ? `(${spreadPct.toFixed(2)}%)` : ''}
            </div>
        </div>
    );
}

const buildupColor: Record<string, string> = {
    LONG_BUILDUP: 'var(--color-profit-text)',
    SHORT_COVERING: 'var(--color-profit-text)',
    SHORT_BUILDUP: 'var(--color-loss-text)',
    LONG_UNWINDING: 'var(--color-loss-text)',
    NEUTRAL: 'var(--text-muted)',
};

const buildupLabel: Record<string, string> = {
    LONG_BUILDUP: 'Long Buildup',
    SHORT_COVERING: 'Short Covering',
    SHORT_BUILDUP: 'Short Buildup',
    LONG_UNWINDING: 'Long Unwinding',
    NEUTRAL: 'Neutral',
};

function OIAnalysisCard({ data, enabled, onToggle }: { data?: OIAnalysisContext; enabled: boolean; onToggle: (v: boolean) => void }) {
    const [expanded, setExpanded] = useState(true);
    const signal = data?.buildup_signal || 'NEUTRAL';
    return (
        <div style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 4 }}>
            <ModuleHeader
                icon={<Layers size={13} />}
                label="OI Analysis"
                enabled={enabled}
                onToggle={onToggle}
                expanded={expanded}
                onExpand={() => setExpanded(e => !e)}
                badge={buildupLabel[signal] || signal}
                badgeColor={buildupColor[signal]}
            />
            {expanded && enabled && (
                <div style={{ paddingBottom: 8 }}>
                    {!data || data.snapshots_count < 3 ? (
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            {data ? `Building snapshots (${data.snapshots_count}/3)...` : 'Waiting for OI data...'}
                        </span>
                    ) : (
                        <>
                            {/* OI Change bars */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, marginBottom: 6 }}>
                                <div style={{ background: 'var(--bg-overlay)', borderRadius: 4, padding: '4px 6px' }}>
                                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 2 }}>CE OI</div>
                                    <div style={{
                                        fontSize: 11, fontWeight: 600,
                                        color: data.ce_oi_change_pct > 0 ? 'var(--color-loss-text)' : data.ce_oi_change_pct < 0 ? 'var(--color-profit-text)' : 'var(--text-muted)',
                                    }}>
                                        {data.ce_oi_change_pct > 0 ? '+' : ''}{data.ce_oi_change_pct.toFixed(2)}%
                                    </div>
                                    {data.max_oi_ce_strike && (
                                        <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                                            Max: {data.max_oi_ce_strike}
                                        </div>
                                    )}
                                </div>
                                <div style={{ background: 'var(--bg-overlay)', borderRadius: 4, padding: '4px 6px' }}>
                                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 2 }}>PE OI</div>
                                    <div style={{
                                        fontSize: 11, fontWeight: 600,
                                        color: data.pe_oi_change_pct > 0 ? 'var(--color-profit-text)' : data.pe_oi_change_pct < 0 ? 'var(--color-loss-text)' : 'var(--text-muted)',
                                    }}>
                                        {data.pe_oi_change_pct > 0 ? '+' : ''}{data.pe_oi_change_pct.toFixed(2)}%
                                    </div>
                                    {data.max_oi_pe_strike && (
                                        <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                                            Max: {data.max_oi_pe_strike}
                                        </div>
                                    )}
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                <Chip label="OI Chg" value={`${data.oi_change_pct > 0 ? '+' : ''}${data.oi_change_pct.toFixed(2)}%`} />
                                <Chip label="Price" value={data.price_direction} />
                                {data.max_pain_strike && (
                                    <Chip label="Max Pain" value={data.max_pain_strike.toFixed(0)} />
                                )}
                                {data.distance_from_max_pain_pct != null && (
                                    <Chip label="Dist" value={`${data.distance_from_max_pain_pct > 0 ? '+' : ''}${data.distance_from_max_pain_pct.toFixed(2)}%`} />
                                )}
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}

function PortfolioGreeksCard({ data, enabled, onToggle }: { data?: PortfolioGreeksContext; enabled: boolean; onToggle: (v: boolean) => void }) {
    const [expanded, setExpanded] = useState(true);
    const risk = data?.portfolio_risk || 'LOW';
    return (
        <div style={{ paddingBottom: 4 }}>
            <ModuleHeader
                icon={<Activity size={13} />}
                label="Portfolio Greeks"
                enabled={enabled}
                onToggle={onToggle}
                expanded={expanded}
                onExpand={() => setExpanded(e => !e)}
                badge={risk + ' RISK'}
                badgeColor={riskColor[risk]}
            />
            {expanded && enabled && (
                <div style={{ paddingBottom: 4 }}>
                    {!data || data.position_count === 0 ? (
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>No open positions.</span>
                    ) : (
                        <>
                            {/* Net delta bar */}
                            <div style={{ marginBottom: 6 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 3 }}>
                                    <span>Net Delta ({data.delta_bias.replace('_', ' ')})</span>
                                    <span style={{ fontWeight: 700, color: data.net_delta > 0 ? 'var(--color-profit-text)' : data.net_delta < 0 ? 'var(--color-loss-text)' : 'var(--text-muted)' }}>
                                        {data.net_delta > 0 ? '+' : ''}{data.net_delta.toFixed(3)}
                                    </span>
                                </div>
                                <div style={{ height: 5, background: 'var(--bg-overlay)', borderRadius: 3, overflow: 'hidden', position: 'relative' }}>
                                    <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, background: 'var(--border-subtle)' }} />
                                    <div style={{
                                        position: 'absolute',
                                        height: '100%',
                                        width: `${Math.min(Math.abs(data.net_delta) * 100, 50)}%`,
                                        left: data.net_delta >= 0 ? '50%' : undefined,
                                        right: data.net_delta < 0 ? '50%' : undefined,
                                        background: data.net_delta >= 0 ? 'var(--color-profit-text)' : 'var(--color-loss-text)',
                                        borderRadius: 3,
                                        transition: 'width 0.4s',
                                    }} />
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 4 }}>
                                <Chip label="Γ" value={data.net_gamma.toFixed(5)} />
                                <Chip label="Θ" value={data.net_theta.toFixed(2)} />
                                <Chip label="V" value={data.net_vega.toFixed(4)} />
                                <Chip label="Pos" value={String(data.position_count)} />
                            </div>
                            {data.hedge_needed && (
                                <div style={{
                                    fontSize: 10,
                                    fontWeight: 700,
                                    color: 'var(--color-warning)',
                                    background: 'var(--color-warning-muted, rgba(234,179,8,0.1))',
                                    padding: '3px 6px',
                                    borderRadius: 4,
                                }}>
                                    ⚠ Hedge: {data.hedge_action}
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}
        </div>
    );
}

function Chip({ label, value }: { label: string; value: string }) {
    return (
        <div style={{ background: 'var(--bg-overlay)', borderRadius: 4, padding: '2px 6px', fontSize: 10 }}>
            <span style={{ color: 'var(--text-muted)' }}>{label} </span>
            <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{value}</span>
        </div>
    );
}

// ── Main Panel ─────────────────────────────────────────────────────────────

const IntelligencePanel: React.FC<IntelligencePanelProps> = ({ intelligence, onToggleModule }) => {
    const [panelOpen, setPanelOpen] = useState(true);

    // Track module enabled state locally (backend is source of truth but we mirror for instant UI)
    // We infer "enabled" by whether we have data; backend returns null/empty for disabled modules.
    // Toggle switches send to backend and rely on status refetch for confirmation.

    return (
        <div className="surface-elevated p-3" style={{ borderRadius: 'var(--radius-lg)' }}>
            {/* Panel header */}
            <button
                onClick={() => setPanelOpen(o => !o)}
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 7,
                    width: '100%',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 0,
                    marginBottom: panelOpen ? 8 : 0,
                }}
            >
                <Brain size={14} style={{ color: 'var(--accent-blue)' }} />
                <span style={{ flex: 1, fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', textAlign: 'left', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Intelligence Engine
                </span>
                <span style={{ fontSize: 10, color: 'var(--text-muted)', marginRight: 4 }}>
                    {Object.keys(intelligence || {}).length} modules
                </span>
                {panelOpen ? <ChevronUp size={14} style={{ color: 'var(--text-muted)' }} /> : <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />}
            </button>

            {panelOpen && (
                <div>
                    <MarketRegimeCard
                        data={intelligence?.market_regime}
                        enabled={intelligence?.market_regime != null}
                        onToggle={(v) => onToggleModule('market_regime', v)}
                    />
                    <IVRankCard
                        data={intelligence?.iv_rank}
                        enabled={intelligence?.iv_rank != null}
                        onToggle={(v) => onToggleModule('iv_rank', v)}
                    />
                    <MarketBreadthCard
                        data={intelligence?.market_breadth}
                        enabled={intelligence?.market_breadth != null}
                        onToggle={(v) => onToggleModule('market_breadth', v)}
                    />
                    <OrderBookCard
                        data={intelligence?.order_book}
                        enabled={intelligence?.order_book != null}
                        onToggle={(v) => onToggleModule('order_book', v)}
                    />
                    <OIAnalysisCard
                        data={intelligence?.oi_analysis}
                        enabled={intelligence?.oi_analysis != null}
                        onToggle={(v) => onToggleModule('oi_analysis', v)}
                    />
                    <PortfolioGreeksCard
                        data={intelligence?.portfolio_greeks}
                        enabled={intelligence?.portfolio_greeks != null}
                        onToggle={(v) => onToggleModule('portfolio_greeks', v)}
                    />
                </div>
            )}
        </div>
    );
};

export default IntelligencePanel;
