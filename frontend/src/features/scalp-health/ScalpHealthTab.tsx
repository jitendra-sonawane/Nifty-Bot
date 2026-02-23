import React from 'react';
import Card from '../../shared/Card';
import ProgressBar from '../../shared/ProgressBar';
import Badge from '../../shared/Badge';
import { Activity, BarChart2, Droplets } from 'lucide-react';
import type { ScalpHealthContext } from '../../types/api';

interface ScalpHealthTabProps {
    data?: ScalpHealthContext;
}

/* -- Helpers ------------------------------------------------ */

const fmt = (v: number | null | undefined, decimals = 2): string =>
    v != null ? v.toFixed(decimals) : '--';

const fmtInt = (v: number | null | undefined): string =>
    v != null ? Math.round(v).toLocaleString('en-IN') : '--';

const signColor = (v: number): string =>
    v > 0 ? 'var(--color-profit-text)' : v < 0 ? 'var(--color-loss-text)' : 'var(--text-secondary)';

const bandColor = (band: string): string => {
    switch (band) {
        case 'PRIME': return 'var(--color-profit-text)';
        case 'GOOD': return 'var(--accent-blue)';
        case 'CAUTION': return 'var(--color-warning-text)';
        case 'AVOID': return 'var(--color-loss-text)';
        default: return 'var(--text-secondary)';
    }
};

const bandVariant = (band: string): 'profit' | 'info' | 'warning' | 'loss' | 'neutral' => {
    switch (band) {
        case 'PRIME': return 'profit';
        case 'GOOD': return 'info';
        case 'CAUTION': return 'warning';
        case 'AVOID': return 'loss';
        default: return 'neutral';
    }
};

const thresholdColor = (value: number, green: number, amber: number, invert = false): string => {
    if (invert) return value <= green ? 'var(--color-profit-text)' : value <= amber ? 'var(--color-warning-text)' : 'var(--color-loss-text)';
    return value >= green ? 'var(--color-profit-text)' : value >= amber ? 'var(--color-warning-text)' : 'var(--color-loss-text)';
};

const spreadLabelColor = (label: string): string => {
    switch (label) {
        case 'EXCELLENT': return 'var(--color-profit-text)';
        case 'GOOD': return 'var(--accent-blue)';
        default: return 'var(--color-loss-text)';
    }
};

const buildupColor = (signal: string): string => {
    if (signal.includes('LONG') || signal === 'SHORT_COVERING') return 'var(--color-profit-text)';
    if (signal.includes('SHORT') || signal === 'LONG_UNWINDING') return 'var(--color-loss-text)';
    return 'var(--text-secondary)';
};

const trendArrow = (trend: string): string => {
    switch (trend) {
        case 'RISING': case 'UP': return '\u2191';
        case 'FALLING': case 'DOWN': return '\u2193';
        default: return '\u2192';
    }
};

/* -- Metric Row --------------------------------------------- */

interface MetricRowProps {
    label: string;
    value: React.ReactNode;
    color?: string;
    suffix?: string;
}

const MetricRow: React.FC<MetricRowProps> = ({ label, value, color, suffix }) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '3px 0' }}>
        <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 500 }}>{label}</span>
        <span className="mono" style={{ fontSize: '11px', fontWeight: 600, color: color || 'var(--text-primary)' }}>
            {value}{suffix || ''}
        </span>
    </div>
);

/* -- Score Header ------------------------------------------- */

const ScoreHeader: React.FC<{ data: ScalpHealthContext }> = ({ data }) => (
    <div style={{
        padding: '12px 16px',
        borderBottom: '1px solid var(--border-subtle)',
        background: 'var(--bg-primary)',
    }}>
        {/* Score bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Scalp Health
                </span>
                <span className="mono" style={{ fontSize: '20px', fontWeight: 800, color: bandColor(data.score_band) }}>
                    {data.score}
                </span>
                <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>/100</span>
            </div>
            <div style={{ flex: 1 }}>
                <ProgressBar value={data.score} max={100} color={data.score >= 60 ? 'green' : data.score >= 40 ? 'yellow' : 'red'} />
            </div>
            <Badge variant={bandVariant(data.score_band)} size="sm">
                {data.score_band}
            </Badge>
        </div>
        {/* Quick chips */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <span className="mono" style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '9999px', background: 'var(--bg-overlay)', color: 'var(--text-secondary)' }}>
                DTE: {data.dte_days}d {data.dte_hours}h {data.dte_minutes}m
            </span>
            <span className="mono" style={{
                fontSize: '10px', padding: '2px 8px', borderRadius: '9999px',
                background: data.gamma_peak ? 'rgba(16,185,129,0.15)' : 'var(--bg-overlay)',
                color: data.gamma_peak ? 'var(--color-profit-text)' : 'var(--text-secondary)',
                fontWeight: data.gamma_peak ? 700 : 500,
            }}>
                Gamma Peak: {data.gamma_peak ? 'YES' : 'NO'}
            </span>
            <span className="mono" style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '9999px', background: 'var(--bg-overlay)', color: 'var(--text-secondary)' }}>
                {data.regime}
            </span>
        </div>
    </div>
);

/* -- Greeks Column ------------------------------------------ */

const GreeksColumn: React.FC<{ data: ScalpHealthContext }> = ({ data }) => (
    <Card compact header={
        <div className="flex items-center gap-2">
            <Activity size={13} className="text-[var(--accent-purple)]" />
            <span className="text-xs font-semibold">Greeks</span>
            <span className="mono text-[9px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--bg-overlay)', color: 'var(--text-muted)' }}>
                {data.sub_scores?.greeks ?? '--'}/100
            </span>
        </div>
    }>
        <MetricRow label="GEX" value={`\u20B9${fmtInt(data.gex_rupees)}`} color={thresholdColor(data.gex_rupees, 3000, 1000)} />
        <MetricRow label="ATM Proximity" value={data.atm_proximity} color={thresholdColor(data.atm_proximity, 80, 50)} suffix="/100" />
        <MetricRow label="\u03B3/\u03B8 Ratio" value={fmt(data.gamma_theta_ratio, 4)} color={thresholdColor(data.gamma_theta_ratio, 2.0, 1.0)} />
        <MetricRow label="Delta Flip" value={`${fmtInt(data.delta_flip_price)} (${data.delta_flip_distance > 0 ? '+' : ''}${fmt(data.delta_flip_distance, 0)})`} />
        <div style={{ borderTop: '1px solid var(--border-subtle)', margin: '4px 0' }} />
        <MetricRow label="CE \u03B4" value={fmt(data.ce_delta, 4)} />
        <MetricRow label="PE \u03B4" value={fmt(data.pe_delta, 4)} />
        <MetricRow label="\u03B4/\u20B9 CE" value={fmt(data.delta_per_rupee_ce, 5)} />
        <MetricRow label="\u03B4/\u20B9 PE" value={fmt(data.delta_per_rupee_pe, 5)} />
        <div style={{ borderTop: '1px solid var(--border-subtle)', margin: '4px 0' }} />
        <MetricRow label="IV-HV" value={`${data.iv_hv_spread > 0 ? '+' : ''}${fmt(data.iv_hv_spread, 1)}%`} color={signColor(-data.iv_hv_spread)} />
        <MetricRow label="Vega" value={fmt(data.vega_risk, 2)} suffix={` (${data.vega_risk_label})`} />
        <MetricRow label="\u03B8/min" value={`\u20B9${fmt(data.theta_per_minute, 4)}`} color="var(--color-loss-text)" />
        <MetricRow
            label="Gamma Peak"
            value={data.gamma_peak ? 'YES' : 'NO'}
            color={data.gamma_peak ? 'var(--color-profit-text)' : 'var(--text-muted)'}
        />
    </Card>
);

/* -- OI Column ---------------------------------------------- */

const OIColumn: React.FC<{ data: ScalpHealthContext }> = ({ data }) => (
    <Card compact header={
        <div className="flex items-center gap-2">
            <BarChart2 size={13} className="text-[var(--accent-blue)]" />
            <span className="text-xs font-semibold">OI & Flow</span>
            <span className="mono text-[9px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--bg-overlay)', color: 'var(--text-muted)' }}>
                {data.sub_scores?.oi ?? '--'}/100
            </span>
        </div>
    }>
        <MetricRow label="Signal" value={data.oi_buildup_signal.replace('_', ' ')} color={buildupColor(data.oi_buildup_signal)} />
        <MetricRow label="OI Chg CE" value={`${data.oi_change_ce >= 0 ? '+' : ''}${fmtInt(data.oi_change_ce)}`} color={signColor(data.oi_change_ce)} />
        <MetricRow label="OI Chg PE" value={`${data.oi_change_pe >= 0 ? '+' : ''}${fmtInt(data.oi_change_pe)}`} color={signColor(data.oi_change_pe)} />
        <MetricRow
            label="OI Rate"
            value={`${fmtInt(data.oi_change_rate)}/min`}
            color={data.oi_rate_alert ? 'var(--color-warning-text)' : undefined}
            suffix={data.oi_rate_alert ? ' !' : ''}
        />
        <div style={{ borderTop: '1px solid var(--border-subtle)', margin: '4px 0' }} />
        <MetricRow label="Max Pain" value={fmtInt(data.max_pain_strike)} suffix={data.max_pain_distance ? ` (${data.max_pain_distance > 0 ? '+' : ''}${fmt(data.max_pain_distance, 0)})` : ''} />
        <MetricRow label="Max OI CE" value={fmtInt(data.max_oi_ce_strike)} />
        <MetricRow label="Max OI PE" value={fmtInt(data.max_oi_pe_strike)} />
        <MetricRow label="OI Conc." value={data.oi_concentration} color={thresholdColor(data.oi_concentration, 70, 30)} suffix="/100" />
        <div style={{ borderTop: '1px solid var(--border-subtle)', margin: '4px 0' }} />
        <MetricRow label="Vol/OI CE" value={fmt(data.volume_oi_ratio_ce, 3)} color={thresholdColor(data.volume_oi_ratio_ce, 1.0, 0.3)} />
        <MetricRow label="Vol/OI PE" value={fmt(data.volume_oi_ratio_pe, 3)} color={thresholdColor(data.volume_oi_ratio_pe, 1.0, 0.3)} />
        <MetricRow label="PCR Trend" value={`${data.pcr_trend} ${trendArrow(data.pcr_trend)}`} />
        <MetricRow
            label="Unwinding"
            value={data.unwinding_alert ? `${fmtInt(data.unwinding_alert.strike)} (-${data.unwinding_alert.oi_drop_pct}%)` : '\u2014'}
            color={data.unwinding_alert ? 'var(--color-loss-text)' : 'var(--text-muted)'}
        />
    </Card>
);

/* -- Liquidity + Context Column ----------------------------- */

const LiquidityContextColumn: React.FC<{ data: ScalpHealthContext }> = ({ data }) => (
    <Card compact header={
        <div className="flex items-center gap-2">
            <Droplets size={13} className="text-[var(--accent-blue)]" />
            <span className="text-xs font-semibold">Liquidity + Context</span>
            <span className="mono text-[9px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--bg-overlay)', color: 'var(--text-muted)' }}>
                {data.sub_scores?.liquidity ?? '--'}/100
            </span>
        </div>
    }>
        <MetricRow label="Spread CE" value={data.spread_ce_pct != null ? `${fmt(data.spread_ce_pct, 2)}%` : '--'} color={spreadLabelColor(data.spread_ce_label)} suffix={` ${data.spread_ce_label[0]}`} />
        <MetricRow label="Spread PE" value={data.spread_pe_pct != null ? `${fmt(data.spread_pe_pct, 2)}%` : '--'} color={spreadLabelColor(data.spread_pe_label)} suffix={` ${data.spread_pe_label[0]}`} />
        <MetricRow label="Lot Liquidity" value={data.lot_liquidity_score} color={thresholdColor(data.lot_liquidity_score, 70, 40)} suffix="/100" />
        <div style={{ borderTop: '1px solid var(--border-subtle)', margin: '4px 0' }} />
        <MetricRow label="VIX" value={`${fmt(data.vix_level, 1)} ${trendArrow(data.vix_trend)}`} color={data.vix_level >= 18 ? 'var(--color-warning-text)' : 'var(--text-primary)'} />
        <MetricRow label="Momentum" value={`${fmt(data.intraday_momentum, 0)}%`} color={thresholdColor(data.intraday_momentum, 30, 80, true)} />
        <MetricRow
            label="Time Zone"
            value={`${data.time_of_day_zone} (${data.minutes_to_next_zone}m)`}
            color={data.time_of_day_zone === 'PEAK' ? 'var(--color-profit-text)' : data.time_of_day_zone === 'MODERATE' ? 'var(--accent-blue)' : 'var(--text-muted)'}
        />
        <MetricRow label="Regime" value={data.regime} />
        <MetricRow label="Recommendation" value={data.regime_scalp_recommendation} color="var(--accent-blue)" />
    </Card>
);

/* -- Main Tab ----------------------------------------------- */

const ScalpHealthTab: React.FC<ScalpHealthTabProps> = React.memo(({ data }) => {
    if (!data || data.score == null) {
        return (
            <div className="text-center py-8 text-[var(--text-muted)] text-sm">
                Waiting for Scalp Health data. Ensure the module is enabled in Intelligence settings.
            </div>
        );
    }

    return (
        <div>
            <ScoreHeader data={data} />
            <div className="grid gap-3 lg:grid-cols-3 p-3">
                <GreeksColumn data={data} />
                <OIColumn data={data} />
                <LiquidityContextColumn data={data} />
            </div>
        </div>
    );
});

ScalpHealthTab.displayName = 'ScalpHealthTab';
export default ScalpHealthTab;
