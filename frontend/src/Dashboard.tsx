import React, { useState, useMemo } from 'react';
import { useDashboard } from './hooks/useDashboard';
import { useStreamNifty50HeatmapQuery } from './apiSlice';

// Layout
import Shell from './layout/Shell';
import Topbar from './layout/Topbar';
import MarketOverviewBar from './layout/MarketOverviewBar';
import BottomTabs from './layout/BottomTabs';

// Market
import PriceChart from './features/market/PriceChart';
import NiftyHeatmap from './features/market/NiftyHeatmap';
import MarketSnapshotDashboard from './features/market/MarketSnapshotDashboard';
import IndicatorStrip from './features/market/IndicatorStrip';

// Decision Panel
import BotControls from './features/controls/BotControls';
import SignalCard from './features/signals/SignalCard';
import FilterMatrix from './features/signals/FilterMatrix';

import Skeleton from './shared/Skeleton';

const MAX_LOADING_SKELETON_MS = 4000;

const Dashboard: React.FC = () => {
    const {
        status,
        isLoading,
        isError,
        isAuthenticated,
        tokenStatus,
        currentPrice,
        isRunning,
        strategyData,
        signal,
        priceHistory,
        mergedGreeksData,
        time,
        isModalOpen,
        pendingMode,
        startBot,
        stopBot,
        handleModeToggle,
        confirmSwitch,
        cancelSwitch,
        handleAddFunds,
        closePosition,
        intelligence,
        toggleIntelligenceModule,
    } = useDashboard();

    const [skeletonExpired, setSkeletonExpired] = useState(false);
    React.useEffect(() => {
        if (isLoading && !status) {
            const t = setTimeout(() => setSkeletonExpired(true), MAX_LOADING_SKELETON_MS);
            return () => clearTimeout(t);
        }
        if (status) setSkeletonExpired(false);
    }, [isLoading, status]);

    const showSkeleton = isLoading && !skeletonExpired && !status;
    const backendUnavailable = (!status && (isError || skeletonExpired)) || isError;

    // Chart view toggle
    const [chartView, setChartView] = useState<'snapshot' | 'chart' | 'heatmap'>('snapshot');
    const { data: heatmapData, isLoading: heatmapLoading } = useStreamNifty50HeatmapQuery(undefined, {
        skip: chartView !== 'heatmap',
    });

    // Derived data for passing to children
    const reasoning = status?.reasoning;
    const pcrAnalysis = status?.market_state?.pcr_analysis;
    const sentiment = status?.market_state?.sentiment || status?.sentiment;
    const openPositionCount = (status as any)?.positions?.length ?? 0;

    // Memoize BottomTabs props to avoid unnecessary re-renders
    const bottomTabsProps = useMemo(() => ({
        status,
        greeks: mergedGreeksData,
        supportResistance: strategyData?.support_resistance,
        breakout: strategyData?.breakout,
        pcrAnalysis,
        sentiment,
        intelligence,
        filters: strategyData?.filters,
        reasoning,
        signal,
        strategyData,
        pcr: status?.market_state?.pcr,
        openPositionCount,
    }), [status, mergedGreeksData, strategyData, pcrAnalysis, sentiment, intelligence, reasoning, signal, openPositionCount]);

    if (showSkeleton) {
        return (
            <Shell
                topbar={
                    <div className="max-w-[var(--max-content)] mx-auto px-4 h-[var(--topbar-height)] flex items-center">
                        <Skeleton className="w-32" />
                    </div>
                }
            >
                {/* Skeleton matching new layout */}
                <div className="h-10 mb-3 rounded-lg overflow-hidden">
                    <Skeleton lines={1} />
                </div>
                <div className="grid gap-3 lg:grid-cols-[1fr_var(--decision-panel-width)] mb-3">
                    <Skeleton lines={8} />
                    <Skeleton lines={5} />
                </div>
                <Skeleton lines={6} />
            </Shell>
        );
    }

    return (
        <Shell
            topbar={
                <Topbar
                    currentPrice={currentPrice}
                    priceHistory={priceHistory}
                    status={status}
                    isAuthenticated={isAuthenticated}
                    tokenStatus={tokenStatus}
                    time={time}
                    handleModeToggle={handleModeToggle}
                    handleAddFunds={handleAddFunds}
                />
            }
            marketBar={
                <MarketOverviewBar
                    strategyData={strategyData}
                    currentPrice={currentPrice}
                    pcrAnalysis={pcrAnalysis}
                    sentiment={sentiment}
                    isRunning={isRunning}
                    intelligence={intelligence}
                />
            }
        >
            {/* ── Error Banners ── */}
            {backendUnavailable && (
                <div className="mb-3 p-3 rounded-lg bg-amber-500/15 border border-amber-500/40 text-amber-200 text-sm flex items-center justify-between gap-2">
                    <span>Backend not connected. Start the backend (e.g. <code className="bg-black/20 px-1 rounded">python server.py</code>) on port 8000.</span>
                    <button onClick={() => window.location.reload()} className="px-2 py-1 rounded bg-amber-500/30 hover:bg-amber-500/50 text-xs font-medium">Retry</button>
                </div>
            )}
            {status && (status as any).token_valid === false && (
                <div className="mb-3 p-3 rounded-lg bg-red-500/15 border border-red-500/40 text-red-200 text-sm flex items-center justify-between gap-2">
                    <span>🔑 <strong>Upstox token expired.</strong> Market data is unavailable — please re-authenticate to resume live feeds.</span>
                    <a href="http://localhost:8000/auth/login" target="_blank" rel="noopener noreferrer"
                        className="px-2 py-1 rounded bg-red-500/30 hover:bg-red-500/50 text-xs font-medium whitespace-nowrap">
                        Re-Login
                    </a>
                </div>
            )}

            {/* ═══ MAIN 2-COLUMN LAYOUT (65% chart / 35% decision) ═══ */}
            <div className="grid gap-3 lg:grid-cols-[1fr_var(--decision-panel-width)]">

                {/* ─── LEFT: Chart + Indicator Strip ─── */}
                <div className="space-y-3 min-w-0">
                    {/* Chart / Heatmap Toggle */}
                    <div className="surface-elevated rounded-xl overflow-hidden">
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '8px 12px',
                            borderBottom: '1px solid var(--border-subtle)',
                        }}>
                            <span style={{
                                fontSize: 'var(--text-sm)',
                                fontWeight: 600,
                                color: 'var(--text-secondary)',
                                textTransform: 'uppercase' as const,
                                letterSpacing: '0.05em',
                            }}>
                                {chartView === 'snapshot' ? 'Market Snapshot' : chartView === 'chart' ? 'Nifty 50 Price' : 'Nifty 50 Heatmap'}
                            </span>
                            <div style={{
                                display: 'flex',
                                gap: '2px',
                                background: 'var(--bg-overlay)',
                                borderRadius: 'var(--radius-sm)',
                                padding: '2px',
                            }}>
                                {(['snapshot', 'chart', 'heatmap'] as const).map((view) => (
                                    <button
                                        key={view}
                                        onClick={() => setChartView(view)}
                                        style={{
                                            fontSize: '11px',
                                            fontWeight: 500,
                                            padding: '4px 10px',
                                            border: 'none',
                                            borderRadius: '4px',
                                            cursor: 'pointer',
                                            color: chartView === view ? 'var(--text-primary)' : 'var(--text-tertiary)',
                                            background: chartView === view ? 'var(--bg-elevated)' : 'transparent',
                                            boxShadow: chartView === view ? 'var(--shadow-sm)' : 'none',
                                            transition: 'all 0.15s',
                                        }}
                                    >
                                        {view === 'snapshot' ? 'Snapshot' : view === 'chart' ? 'Chart' : 'Heatmap'}
                                    </button>
                                ))}
                            </div>
                        </div>
                        {chartView === 'snapshot' ? (
                            <MarketSnapshotDashboard
                                strategyData={strategyData}
                                currentPrice={currentPrice}
                                intelligence={intelligence}
                                positions={(status as any)?.positions ?? []}
                                pnl={{
                                    daily: (status as any)?.paper_daily_pnl ?? (status as any)?.risk_stats?.daily_pnl ?? 0,
                                    unrealized: (status as any)?.paper_pnl ?? 0,
                                }}
                                riskStats={(status as any)?.risk_stats}
                                signal={signal}
                                pcrAnalysis={pcrAnalysis}
                            />
                        ) : chartView === 'chart' ? (
                            <PriceChart data={priceHistory} height={340} />
                        ) : (
                            <NiftyHeatmap
                                data={heatmapData?.stocks}
                                isLoading={heatmapLoading}
                                height={340}
                            />
                        )}
                    </div>

                    {/* Indicator Strip */}
                    <IndicatorStrip strategyData={strategyData} currentPrice={currentPrice} />
                </div>

                {/* ─── RIGHT: Decision Panel ─── */}
                <div className="space-y-3 flex-shrink-0">
                    <BotControls
                        isAuthenticated={isAuthenticated}
                        isRunning={isRunning}
                        startBot={startBot}
                        stopBot={stopBot}
                    />
                    <SignalCard signal={signal} reasoning={reasoning} strategyData={strategyData} />
                    <FilterMatrix filters={strategyData?.filters} />
                </div>
            </div>

            {/* ═══ BOTTOM TABS (full width) ═══ */}
            <BottomTabs
                {...bottomTabsProps}
                closePosition={closePosition}
                toggleIntelligenceModule={toggleIntelligenceModule}
                currentPrice={currentPrice}
            />

            {/* ═══ MODE SWITCH MODAL ═══ */}
            {isModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
                    <div className="surface-elevated max-w-sm w-full mx-4 p-6 animate-slide-up">
                        <h3 className="text-lg font-bold mb-2">Switch Trading Mode</h3>
                        <p className="text-sm text-[var(--text-secondary)] mb-4">
                            {pendingMode === 'REAL' ? (
                                <>
                                    ⚠️ You are switching to <strong className="text-[var(--color-loss-text)]">REAL TRADING</strong>.
                                    This will use actual funds and execute live trades.
                                </>
                            ) : (
                                <>
                                    You are switching to <strong className="text-[var(--accent-blue)]">PAPER TRADING</strong>.
                                    No real funds will be used.
                                </>
                            )}
                        </p>
                        <div className="flex gap-2">
                            <button
                                onClick={cancelSwitch}
                                className="flex-1 py-2 rounded-lg text-sm font-medium bg-[var(--bg-overlay)] hover:bg-[var(--bg-hover)] transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmSwitch}
                                className={`flex-1 py-2 rounded-lg text-sm font-bold text-white transition-opacity hover:opacity-90 ${pendingMode === 'REAL'
                                    ? 'bg-gradient-to-r from-[var(--color-loss)] to-orange-500'
                                    : 'bg-gradient-to-r from-[var(--accent-blue)] to-[var(--accent-indigo)]'
                                    }`}
                            >
                                Confirm
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </Shell>
    );
};

export default Dashboard;
