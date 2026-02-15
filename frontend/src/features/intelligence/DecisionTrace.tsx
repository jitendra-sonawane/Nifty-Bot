import React, { useState } from 'react';
import { GitBranch, ChevronDown, ChevronUp, CheckCircle, XCircle, Circle } from 'lucide-react';
import type { IntelligenceContext, FilterData, ReasoningData } from '../../types/api';

interface DecisionTraceProps {
    intelligence?: IntelligenceContext;
    filters?: FilterData;
    reasoning?: ReasoningData;
    signal?: string;
    pcr?: number | null;
    greeks?: any;
}

// ── Helpers ────────────────────────────────────────────────────────────────

const signalColor = (sig?: string) => {
    if (!sig) return 'var(--text-muted)';
    if (sig.includes('BUY_CE')) return 'var(--color-profit-text)';
    if (sig.includes('BUY_PE')) return 'var(--color-loss-text)';
    return 'var(--text-secondary)';
};

function TraceRow({
    pass,
    label,
    detail,
    na,
}: {
    pass: boolean | null;
    label: string;
    detail?: string;
    na?: boolean;
}) {
    const color = na ? 'var(--text-muted)' : pass ? 'var(--color-profit-text)' : 'var(--color-loss-text)';
    return (
        <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '3px 0',
        }}>
            <span style={{ color, display: 'flex', flexShrink: 0 }}>
                {na ? <Circle size={11} opacity={0.4} /> : pass ? <CheckCircle size={11} /> : <XCircle size={11} />}
            </span>
            <span style={{ fontSize: 11, color: na ? 'var(--text-muted)' : 'var(--text-secondary)', flex: 1 }}>
                {label}
            </span>
            {detail && (
                <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>
                    {detail}
                </span>
            )}
        </div>
    );
}

function StageBlock({
    number,
    title,
    children,
    passCount,
    totalCount,
}: {
    number: number;
    title: string;
    children: React.ReactNode;
    passCount: number;
    totalCount: number;
}) {
    const allPassed = passCount === totalCount;
    const somePass = passCount > 0;
    const stageColor = allPassed
        ? 'var(--color-profit-text)'
        : somePass
            ? 'var(--color-warning)'
            : 'var(--color-loss-text)';

    return (
        <div style={{ marginBottom: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
                <div style={{
                    width: 18,
                    height: 18,
                    borderRadius: '50%',
                    background: stageColor + '22',
                    border: `1px solid ${stageColor}44`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 9,
                    fontWeight: 700,
                    color: stageColor,
                    flexShrink: 0,
                }}>
                    {number}
                </div>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    {title}
                </span>
                <span style={{ marginLeft: 'auto', fontSize: 10, color: stageColor, fontWeight: 600 }}>
                    {passCount}/{totalCount}
                </span>
            </div>
            <div style={{
                paddingLeft: 12,
                borderLeft: `2px solid ${stageColor}30`,
                marginLeft: 8,
            }}>
                {children}
            </div>
        </div>
    );
}

// ── Main Component ─────────────────────────────────────────────────────────

const DecisionTrace: React.FC<DecisionTraceProps> = ({
    intelligence,
    filters,
    reasoning,
    signal,
    pcr,
    greeks,
}) => {
    const [open, setOpen] = useState(false);

    // ── Stage 1: Intelligence Gate ───────────────────────────────────────
    const regime = intelligence?.market_regime;
    const ivRank = intelligence?.iv_rank;
    const breadth = intelligence?.market_breadth;
    const orderBook = intelligence?.order_book;

    const isBullish = signal === 'BUY_CE';
    const isBearish = signal === 'BUY_PE';
    const isDirectional = isBullish || isBearish;

    const regimePass = regime
        ? isDirectional
            ? (isBullish
                ? regime.allowed_strategies.some(s => s.includes('bull') || s.includes('breakout'))
                : regime.allowed_strategies.some(s => s.includes('bear') || s.includes('breakout')))
            : true
        : null;

    const ivPass = ivRank?.iv_rank != null
        ? ivRank.iv_rank >= 20  // iv_block_below_rank threshold
        : null;

    const breadthPass = breadth
        ? isDirectional
            ? (isBullish ? !['STRONG_BEARISH'].includes(breadth.breadth_bias) : !['STRONG_BULLISH'].includes(breadth.breadth_bias))
            : true
        : null;

    const obPass = orderBook
        ? orderBook.ce_liquidity !== 'POOR' && orderBook.pe_liquidity !== 'POOR'
        : null;

    const intelItems: { pass: boolean | null; label: string; detail: string; na: boolean }[] = [
        {
            pass: regimePass,
            label: 'Market Regime',
            detail: regime?.regime ?? '—',
            na: regime == null,
        },
        {
            pass: ivPass,
            label: 'IV Rank',
            detail: ivRank?.iv_rank != null ? `Rank ${ivRank.iv_rank.toFixed(0)} · ${ivRank.recommendation}` : '—',
            na: ivRank == null,
        },
        {
            pass: breadthPass,
            label: 'Market Breadth',
            detail: breadth?.breadth_bias ?? '—',
            na: breadth == null,
        },
        {
            pass: obPass,
            label: 'Order Book Liquidity',
            detail: orderBook ? `CE:${orderBook.ce_liquidity} PE:${orderBook.pe_liquidity}` : '—',
            na: orderBook == null,
        },
    ];
    const intelPass = intelItems.filter(i => !i.na && i.pass === true).length;
    const intelTotal = intelItems.filter(i => !i.na).length;

    // ── Stage 2: Technical Filters ───────────────────────────────────────
    const techItems: { key: keyof FilterData; label: string; detail?: string }[] = [
        { key: 'ema_crossover', label: 'EMA Crossover' },
        { key: 'rsi', label: 'RSI' },
        { key: 'supertrend', label: 'Supertrend' },
        { key: 'volume', label: 'Volume Spike' },
        { key: 'volatility', label: 'Volatility (ATR)' },
        { key: 'entry_confirmation', label: 'Entry Confirm' },
    ];
    const techPass = techItems.filter(t => filters?.[t.key]).length;

    // ── Stage 3: Options Alignment ───────────────────────────────────────
    const pcrOk = pcr != null ? (isBullish ? pcr < 1.2 : isBearish ? pcr > 0.8 : true) : null;
    const greeksOk = greeks
        ? (isBullish ? (greeks.ce?.delta ?? 0) > 0.3 : isBearish ? (greeks.pe?.delta ?? 0) < -0.3 : true)
        : null;
    const optionsPass = [pcrOk, greeksOk].filter(v => v === true).length;
    const optionsTotal = [pcrOk, greeksOk].filter(v => v !== null).length;

    // ── Stage 4: Final signal ────────────────────────────────────────────
    const confidence = reasoning?.confidence ?? null;

    const totalPass = intelPass + techPass + optionsPass;
    const grandTotal = intelTotal + techItems.length + optionsTotal;

    return (
        <div className="surface-elevated p-3" style={{ borderRadius: 'var(--radius-lg)' }}>
            <button
                onClick={() => setOpen(o => !o)}
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 7,
                    width: '100%',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 0,
                    marginBottom: open ? 10 : 0,
                }}
            >
                <GitBranch size={14} style={{ color: 'var(--accent-blue)' }} />
                <span style={{ flex: 1, fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', textAlign: 'left', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Decision Trace
                </span>
                {grandTotal > 0 && (
                    <span style={{
                        fontSize: 10,
                        fontWeight: 700,
                        color: totalPass >= grandTotal * 0.75 ? 'var(--color-profit-text)' : totalPass >= grandTotal * 0.5 ? 'var(--color-warning)' : 'var(--color-loss-text)',
                        marginRight: 4,
                    }}>
                        {totalPass}/{grandTotal}
                    </span>
                )}
                {open ? <ChevronUp size={14} style={{ color: 'var(--text-muted)' }} /> : <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />}
            </button>

            {open && (
                <div>
                    {/* Stage 1 */}
                    <StageBlock number={1} title="Intelligence Gate" passCount={intelPass} totalCount={Math.max(intelTotal, 1)}>
                        {intelItems.map(item => (
                            <TraceRow key={item.label} pass={item.pass} label={item.label} detail={item.detail} na={item.na} />
                        ))}
                    </StageBlock>

                    {/* Stage 2 */}
                    <StageBlock number={2} title="Technical Filters" passCount={techPass} totalCount={techItems.length}>
                        {techItems.map(item => (
                            <TraceRow
                                key={item.key}
                                pass={filters?.[item.key] ?? null}
                                label={item.label}
                                na={!filters}
                            />
                        ))}
                    </StageBlock>

                    {/* Stage 3 */}
                    <StageBlock number={3} title="Options Alignment" passCount={optionsPass} totalCount={Math.max(optionsTotal, 1)}>
                        <TraceRow
                            pass={pcrOk}
                            label="PCR"
                            detail={pcr != null ? pcr.toFixed(2) : undefined}
                            na={pcr == null}
                        />
                        <TraceRow
                            pass={greeksOk}
                            label="Greeks Delta"
                            detail={greeks ? (isBullish ? `CE Δ ${(greeks.ce?.delta ?? 0).toFixed(3)}` : isBearish ? `PE Δ ${(greeks.pe?.delta ?? 0).toFixed(3)}` : '—') : undefined}
                            na={greeks == null}
                        />
                    </StageBlock>

                    {/* Stage 4 */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 4, borderTop: '1px solid var(--border-subtle)' }}>
                        <div style={{
                            width: 18, height: 18, borderRadius: '50%',
                            background: signalColor(signal) + '22',
                            border: `1px solid ${signalColor(signal)}44`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 9, fontWeight: 700, color: signalColor(signal), flexShrink: 0,
                        }}>4</div>
                        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                            Final Signal
                        </span>
                        <span style={{ fontSize: 11, fontWeight: 800, color: signalColor(signal), marginLeft: 'auto' }}>
                            {signal || 'WAITING'}
                        </span>
                        {confidence != null && (
                            <span style={{
                                fontSize: 10,
                                color: confidence >= 70 ? 'var(--color-profit-text)' : confidence >= 40 ? 'var(--color-warning)' : 'var(--color-loss-text)',
                                fontWeight: 600,
                            }}>
                                {confidence.toFixed(0)}%
                            </span>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default DecisionTrace;
