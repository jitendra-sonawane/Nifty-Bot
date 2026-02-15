import React from 'react';
import Card from '../../shared/Card';
import ProgressBar from '../../shared/ProgressBar';

interface PCRGaugeProps {
    pcrAnalysis: any;
    sentiment: any;
}

const PCRGauge: React.FC<PCRGaugeProps> = React.memo(({ pcrAnalysis, sentiment }) => {
    const pcr = pcrAnalysis?.pcr ?? sentiment?.pcr;
    const pcrSentiment = pcrAnalysis?.sentiment ?? sentiment?.pcr_sentiment ?? '';
    const interpretation = pcrAnalysis?.interpretation;
    const trend = pcrAnalysis?.trend ?? sentiment?.pcr_trend;
    const vix = sentiment?.vix;
    const sentimentScore = sentiment?.score ?? 50;
    const sentimentLabel = sentiment?.label ?? 'Neutral';

    const getSentimentColor = (): 'green' | 'red' | 'yellow' => {
        if (sentimentScore >= 60) return 'green';
        if (sentimentScore <= 40) return 'red';
        return 'yellow';
    };

    const getPCRColor = () => {
        if (!pcr) return 'var(--text-muted)';
        if (pcr > 1.2) return 'var(--color-loss-text)';
        if (pcr < 0.8) return 'var(--color-profit-text)';
        return 'var(--color-warning)';
    };

    return (
        <Card compact>
            {/* Sentiment Header */}
            <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium">Market Sentiment</span>
                <span
                    className="mono text-sm font-bold"
                    style={{
                        color:
                            sentimentScore >= 60
                                ? 'var(--color-profit-text)'
                                : sentimentScore <= 40
                                    ? 'var(--color-loss-text)'
                                    : 'var(--color-warning)',
                    }}
                >
                    {sentimentLabel}
                </span>
            </div>

            {/* Sentiment bar */}
            <ProgressBar value={sentimentScore} color={getSentimentColor()} height="md" showValue />

            {/* PCR + VIX row */}
            <div className="grid grid-cols-2 gap-2 mt-3">
                <div className="surface !rounded-md p-2.5">
                    <div className="label mb-1">PCR</div>
                    <div className="mono text-lg font-bold" style={{ color: getPCRColor() }}>
                        {pcr != null ? pcr.toFixed(3) : '--'}
                    </div>
                    {pcrSentiment && (
                        <div className="text-[10px] text-[var(--text-muted)] mt-0.5">
                            {pcrSentiment.replace(/_/g, ' ')}
                        </div>
                    )}
                </div>

                <div className="surface !rounded-md p-2.5">
                    <div className="label mb-1">VIX</div>
                    <div className="mono text-lg font-bold text-[var(--text-primary)]">
                        {vix != null ? vix.toFixed(2) : '--'}
                    </div>
                    {trend && (
                        <div className="text-[10px] text-[var(--text-muted)] mt-0.5 flex items-center gap-1">
                            {trend === 'INCREASING' ? '📈' : trend === 'DECREASING' ? '📉' : '➡️'}
                            {trend === 'INCREASING' ? 'Rising' : trend === 'DECREASING' ? 'Falling' : 'Stable'}
                        </div>
                    )}
                </div>
            </div>

            {/* Interpretation */}
            {interpretation && (
                <p className="text-[11px] text-[var(--text-tertiary)] mt-2 leading-relaxed">
                    {interpretation}
                </p>
            )}
        </Card>
    );
});

PCRGauge.displayName = 'PCRGauge';
export default PCRGauge;
