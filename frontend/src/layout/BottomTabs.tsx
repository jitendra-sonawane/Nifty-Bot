import React, { useState, useCallback, Suspense } from 'react';
import { BarChart2, Brain, History, TestTube2, Activity, Waves } from 'lucide-react';
import PortfolioStats from '../features/positions/PortfolioStats';
import PositionList from '../features/positions/PositionList';
import TradeJournal from '../features/positions/TradeJournal';
import GreeksTable from '../features/options/GreeksTable';
import SupportResistance from '../features/options/SupportResistance';
import PCRGauge from '../features/options/PCRGauge';
import BacktestPanel from '../features/backtest/BacktestPanel';
import Skeleton from '../shared/Skeleton';
import type { FilterData, IntelligenceContext, ScalpHealthContext } from '../types/api';

// Intelligence tab is lazily loaded to split its bundle
const IntelligenceTabContent = React.lazy(() => import('./IntelligenceTabContent'));
const ScalpHealthTabContent = React.lazy(() => import('../features/scalp-health/ScalpHealthTab'));
const OrderFlowTabContent = React.lazy(() => import('../features/order-flow/OrderFlowTab'));

type TabId = 'positions' | 'analytics' | 'scalp_health' | 'order_flow' | 'intelligence' | 'backtest';

interface TabDef {
    id: TabId;
    label: string;
    icon: React.ReactNode;
}

const TABS: TabDef[] = [
    { id: 'positions',    label: 'Positions',    icon: <History size={13} /> },
    { id: 'analytics',    label: 'Analytics',     icon: <BarChart2 size={13} /> },
    { id: 'scalp_health', label: 'Scalp Health',  icon: <Activity size={13} /> },
    { id: 'order_flow',  label: 'Order Flow',    icon: <Waves size={13} /> },
    { id: 'intelligence', label: 'Intelligence',  icon: <Brain size={13} /> },
    { id: 'backtest',    label: 'Backtest',      icon: <TestTube2 size={13} /> },
];

interface BottomTabsProps {
    // Positions tab
    status?: any;
    closePosition: (params: { position_id: string; exit_price: number }) => void;
    // Analytics tab
    greeks?: any;
    supportResistance?: any;
    breakout?: any;
    currentPrice: number;
    pcrAnalysis?: any;
    sentiment?: any;
    // Intelligence tab
    intelligence?: IntelligenceContext;
    toggleIntelligenceModule: (module: string, enabled: boolean) => void;
    filters?: FilterData;
    reasoning?: any;
    signal?: string;
    strategyData?: any;
    pcr?: any;
    // Scalp Health tab
    scalpHealth?: ScalpHealthContext;
    // Order Flow tab
    orderFlowData?: any;
    futuresLtp?: number;
    // Badge
    openPositionCount: number;
}

/* ── Sub-tab content (memoized) ──────────────────────────────── */

interface PositionsTabProps {
    status?: any;
    closePosition: (params: { position_id: string; exit_price: number }) => void;
}
const PositionsTabContent: React.FC<PositionsTabProps> = React.memo(({ status, closePosition }) => (
    <div className="grid gap-3 lg:grid-cols-3">
        <PortfolioStats stats={status?.portfolio_stats} />
        <PositionList status={status} closePosition={closePosition} />
        <TradeJournal trades={status?.trade_history} />
    </div>
));
PositionsTabContent.displayName = 'PositionsTabContent';

interface AnalyticsTabProps {
    greeks?: any;
    supportResistance?: any;
    breakout?: any;
    currentPrice: number;
    pcrAnalysis?: any;
    sentiment?: any;
}
const AnalyticsTabContent: React.FC<AnalyticsTabProps> = React.memo((props) => (
    <div className="grid gap-3 lg:grid-cols-3">
        <GreeksTable greeks={props.greeks} />
        <SupportResistance
            supportResistance={props.supportResistance}
            breakout={props.breakout}
            currentPrice={props.currentPrice}
        />
        <PCRGauge pcrAnalysis={props.pcrAnalysis} sentiment={props.sentiment} />
    </div>
));
AnalyticsTabContent.displayName = 'AnalyticsTabContent';

/* ── Main BottomTabs component ───────────────────────────────── */

const BottomTabs: React.FC<BottomTabsProps> = React.memo((props) => {
    const [activeTab, setActiveTab] = useState<TabId>('positions');
    // Lazy-mount: positions is pre-mounted, others mount on first click
    const [mounted, setMounted] = useState<Record<TabId, boolean>>({
        positions: true,
        analytics: false,
        scalp_health: false,
        order_flow: false,
        intelligence: false,
        backtest: false,
    });

    const handleTabChange = useCallback((tab: TabId) => {
        setMounted((prev) => ({ ...prev, [tab]: true }));
        setActiveTab(tab);
    }, []);

    return (
        <div className="surface-elevated rounded-xl overflow-hidden mt-3">
            {/* Tab Header Strip */}
            <div
                className="flex items-center border-b border-[var(--border-subtle)] bg-[var(--bg-primary)]/60"
                style={{ height: 'var(--bottom-tabs-header-height)' }}
            >
                {TABS.map((tab) => {
                    const isActive = activeTab === tab.id;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => handleTabChange(tab.id)}
                            className="flex items-center gap-1.5 px-4 h-full text-xs font-medium border-b-2 transition-all duration-150 flex-shrink-0"
                            style={{
                                borderBottomColor: isActive ? 'var(--tab-active-indicator)' : 'transparent',
                                color: isActive ? 'var(--text-primary)' : 'var(--text-tertiary)',
                                background: isActive ? 'var(--tab-bg-active)' : 'transparent',
                            }}
                            onMouseEnter={(e) => {
                                if (!isActive) {
                                    (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-secondary)';
                                    (e.currentTarget as HTMLButtonElement).style.background = 'var(--bg-hover)';
                                }
                            }}
                            onMouseLeave={(e) => {
                                if (!isActive) {
                                    (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-tertiary)';
                                    (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                                }
                            }}
                        >
                            {tab.icon}
                            {tab.label}
                            {tab.id === 'positions' && props.openPositionCount > 0 && (
                                <span
                                    className="mono"
                                    style={{
                                        fontSize: '9px',
                                        fontWeight: 700,
                                        padding: '1px 5px',
                                        borderRadius: '9999px',
                                        background: 'rgba(99,102,241,0.2)',
                                        color: 'var(--accent-indigo)',
                                        marginLeft: '2px',
                                    }}
                                >
                                    {props.openPositionCount}
                                </span>
                            )}
                        </button>
                    );
                })}
            </div>

            {/* Tab Panels — lazy-mounted, hidden when inactive */}
            <div className="p-3" style={{ minHeight: 'var(--bottom-tabs-height)' }}>
                {/* Positions */}
                {mounted.positions && (
                    <div style={{ display: activeTab === 'positions' ? 'block' : 'none' }}>
                        <PositionsTabContent
                            status={props.status}
                            closePosition={props.closePosition}
                        />
                    </div>
                )}

                {/* Analytics */}
                {mounted.analytics && (
                    <div style={{ display: activeTab === 'analytics' ? 'block' : 'none' }}>
                        <AnalyticsTabContent
                            greeks={props.greeks}
                            supportResistance={props.supportResistance}
                            breakout={props.breakout}
                            currentPrice={props.currentPrice}
                            pcrAnalysis={props.pcrAnalysis}
                            sentiment={props.sentiment}
                        />
                    </div>
                )}

                {/* Scalp Health (React.lazy) */}
                {mounted.scalp_health && (
                    <div style={{ display: activeTab === 'scalp_health' ? 'block' : 'none' }}>
                        <Suspense fallback={<Skeleton lines={6} />}>
                            <ScalpHealthTabContent data={props.scalpHealth} />
                        </Suspense>
                    </div>
                )}

                {/* Order Flow (React.lazy) */}
                {mounted.order_flow && (
                    <div style={{ display: activeTab === 'order_flow' ? 'block' : 'none' }}>
                        <Suspense fallback={<Skeleton lines={6} />}>
                            <OrderFlowTabContent
                                data={props.orderFlowData}
                                futuresLtp={props.futuresLtp}
                            />
                        </Suspense>
                    </div>
                )}

                {/* Intelligence (React.lazy) */}
                {mounted.intelligence && (
                    <div style={{ display: activeTab === 'intelligence' ? 'block' : 'none' }}>
                        <Suspense fallback={<Skeleton lines={6} />}>
                            <IntelligenceTabContent
                                intelligence={props.intelligence}
                                onToggleModule={props.toggleIntelligenceModule}
                                filters={props.filters}
                                reasoning={props.reasoning}
                                signal={props.signal}
                                strategyData={props.strategyData}
                                pcr={props.pcr}
                                greeks={props.greeks}
                            />
                        </Suspense>
                    </div>
                )}

                {/* Backtest */}
                {mounted.backtest && (
                    <div style={{ display: activeTab === 'backtest' ? 'block' : 'none' }}>
                        <BacktestPanel />
                    </div>
                )}
            </div>
        </div>
    );
});

BottomTabs.displayName = 'BottomTabs';
export default BottomTabs;
