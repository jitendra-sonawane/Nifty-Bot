import React, { useState, useEffect, useRef } from 'react';
import PositionCards from './PositionCards';
import BacktestPanel from './BacktestPanel';
import PriceChart from './PriceChart';
import IndicatorPanel from './IndicatorPanel';
import SupportResistance from './SupportResistance';
import GreeksPanel from './GreeksPanel';
import ReasoningCard from './ReasoningCard';
import FilterStatusPanel from './FilterStatusPanel';
import { useGetStatusQuery, useStreamGreeksQuery, useStartBotMutation, useStopBotMutation, useSetTradingModeMutation, useAddPaperFundsMutation, useClosePositionMutation } from './apiSlice';
import { Activity } from 'lucide-react';

// New Components
import Header from './components/dashboard/Header';
import MetricsGrid from './components/dashboard/MetricsGrid';
import ControlPanel from './components/dashboard/ControlPanel';
import LogViewer from './components/dashboard/LogViewer';

const Dashboard: React.FC = () => {
    const { data: status, isLoading, refetch } = useGetStatusQuery();

    // Real-time Greeks WebSocket stream
    const { data: greeksStreamData } = useStreamGreeksQuery();

    // Merge WebSocket stream data with HTTP data (prefer WebSocket for real-time updates)
    const [mergedGreeksData, setMergedGreeksData] = useState<any>(null);

    // Check if authenticated
    const isAuthenticated = status?.auth?.authenticated;
    const tokenStatus = status?.auth?.token_status;

    useEffect(() => {
        // Check WebSocket data first
        if (greeksStreamData?.data) {
            const wsData = greeksStreamData.data;
            if (wsData.ce && wsData.pe) {
                setMergedGreeksData(wsData);
            }
        }
        // Fallback to HTTP status data
        else if (status?.strategy_data?.greeks) {
            setMergedGreeksData(status.strategy_data.greeks);
        }
    }, [greeksStreamData, status?.strategy_data?.greeks]);

    useEffect(() => {
        const handler = (event: MessageEvent) => {
            if (event.data === 'auth_success') {
                console.log('✅✅✅ Auth success message received!');
                setTimeout(() => refetch(), 2000);
                setTimeout(() => refetch(), 4000);
                setTimeout(() => refetch(), 6000);
            }
        };
        window.addEventListener('message', handler);
        return () => window.removeEventListener('message', handler);
    }, [refetch]);

    const [startBot] = useStartBotMutation();
    const [stopBot] = useStopBotMutation();
    const [setTradingMode] = useSetTradingModeMutation();
    const [addPaperFunds] = useAddPaperFundsMutation();
    const [closePosition] = useClosePositionMutation();

    const [isModalOpen, setIsModalOpen] = useState(false);
    const [pendingMode, setPendingMode] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<'logs' | 'history'>('logs');

    const handleModeToggle = () => {
        const newMode = status?.trading_mode === 'REAL' ? 'PAPER' : 'REAL';
        setPendingMode(newMode);
        setIsModalOpen(true);
    };

    const confirmSwitch = () => {
        if (pendingMode) {
            setTradingMode({ mode: pendingMode });
        }
        setIsModalOpen(false);
        setPendingMode(null);
    };

    const cancelSwitch = () => {
        setIsModalOpen(false);
        setPendingMode(null);
    };

    const handleAddFunds = () => {
        const amount = prompt("Enter amount to add to Paper Funds:", "100000");
        if (amount && !isNaN(parseFloat(amount))) {
            addPaperFunds({ amount: parseFloat(amount) });
        }
    };

    // Real Data Integration
    const currentPrice = status?.current_price || 0;
    const isRunning = status?.is_running;
    const strategyData = status?.strategy_data || {};
    const signal = status?.latest_signal || 'WAITING';

    // Price History for Chart
    const [priceHistory, setPriceHistory] = useState<{ time: string, price: number }[]>([]);
    const lastPriceRef = useRef(0);

    useEffect(() => {
        if (currentPrice && currentPrice !== lastPriceRef.current) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

            setPriceHistory(prev => {
                const newHistory = [...prev, { time: timeStr, price: currentPrice }];
                return newHistory.slice(-50); // Keep last 50 points for chart
            });
            lastPriceRef.current = currentPrice;
        }
    }, [currentPrice]);

    // Time formatting
    const [time, setTime] = useState(new Date());
    useEffect(() => {
        const timer = setInterval(() => setTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    if (isLoading) return <div className="min-h-screen bg-[#0B0E14] flex items-center justify-center text-white">Loading...</div>;

    return (
        <div className="min-h-screen bg-gradient-to-br from-[#0b1020] via-[#101228] to-[#2b0f30] text-white p-2 font-[var(--font-ui)] relative overflow-x-hidden w-screen">
            <div className="w-full max-w-7xl mx-auto space-y-3">

                {/* Modal Overlay */}
                {isModalOpen && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
                        <div className="bg-[#161b2e] border border-white/10 rounded-2xl p-6 max-w-md w-full shadow-2xl">
                            <h3 className={`text-xl font-bold mb-4 ${pendingMode === 'REAL' ? 'text-red-400' : 'text-blue-400'}`}>
                                {pendingMode === 'REAL' ? '⚠️ Switch to Real Money?' : 'ℹ️ Switch to Paper Trading?'}
                            </h3>
                            <p className="text-gray-300 mb-6">
                                {pendingMode === 'REAL'
                                    ? "You are about to enable REAL MONEY trading. Trades will be executed on your Upstox account with actual funds. Are you sure?"
                                    : "You are switching to Paper Trading. No real money will be used."}
                            </p>
                            <div className="flex gap-3 justify-end">
                                <button onClick={cancelSwitch} className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white font-medium">Cancel</button>
                                <button onClick={confirmSwitch} className={`px-4 py-2 rounded-lg font-bold text-white ${pendingMode === 'REAL' ? 'bg-red-500 hover:bg-red-600' : 'bg-blue-500 hover:bg-blue-600'}`}>Confirm Switch</button>
                            </div>
                        </div>
                    </div>
                )}

                {/* HEADER */}
                <Header
                    status={status}
                    isAuthenticated={isAuthenticated}
                    tokenStatus={tokenStatus}
                    time={time}
                    handleModeToggle={handleModeToggle}
                    handleAddFunds={handleAddFunds}
                />

                {/* ROW 1: KEY METRICS */}
                <MetricsGrid
                    currentPrice={currentPrice}
                    priceHistory={priceHistory}
                    signal={signal}
                    status={status}
                />

                {/* ROW 2: MAIN ANALYSIS */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                    {/* Left Column: Chart & Indicators */}
                    <div className="lg:col-span-2 space-y-3">
                        {/* Main Chart Area */}
                        <div className="card p-4 rounded-xl bg-[#151925] border border-white/5 shadow-lg h-[300px] flex flex-col">
                            <div className="flex justify-between items-center mb-4">
                                <h2 className="text-sm font-medium text-white flex items-center gap-2">
                                    <Activity size={16} className="text-cyan-400" /> Price Action
                                </h2>
                                <div className="flex gap-2">
                                    {['1m', '5m', '15m'].map(tf => (
                                        <button key={tf} className="px-2 py-1 text-[10px] rounded bg-white/5 hover:bg-white/10 text-gray-300">{tf}</button>
                                    ))}
                                </div>
                            </div>
                            <div className="flex-1 w-full bg-black/20 rounded-lg overflow-hidden relative">
                                <PriceChart data={priceHistory} height={240} />
                            </div>
                        </div>

                        {/* Indicator Grid */}
                        <IndicatorPanel strategyData={strategyData} currentPrice={currentPrice} />
                    </div>

                    {/* Right Column: Reasoning & Controls */}
                    <div className="space-y-3">
                        {/* Trading Reasoning Card */}
                        <div className="card rounded-xl bg-[#151925] border border-white/5 shadow-lg overflow-hidden">
                            <div className="p-4 overflow-y-auto max-h-[700px]">
                                <ReasoningCard
                                    reasoning={status?.reasoning}
                                    currentPrice={currentPrice}
                                />
                            </div>
                        </div>

                        {/* Live Filter Metrics */}
                        <div className="card rounded-xl bg-[#151925] border border-white/5 shadow-lg overflow-hidden">
                            <div className="p-4 overflow-y-auto max-h-[600px]">
                                <FilterStatusPanel
                                    filters={strategyData?.filters}
                                    rsi={strategyData?.rsi}
                                    volumeRatio={strategyData?.volume_ratio}
                                    atrPct={strategyData?.atr_pct}
                                    vwap={strategyData?.vwap}
                                    currentPrice={currentPrice}
                                    supertrend={strategyData?.supertrend}
                                />
                            </div>
                        </div>
                    </div>
                </div>

                {/* ROW 2B: SUPPORT/RESISTANCE & CONTROLS */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                    {/* System Control & Support/Resistance (2/3) */}
                    <div className="lg:col-span-2 space-y-3">

                        <ControlPanel
                            isAuthenticated={isAuthenticated}
                            isRunning={isRunning}
                            startBot={startBot}
                            stopBot={stopBot}
                        />

                        {/* Support/Resistance & Breakout */}
                        <div className="card p-4 rounded-xl bg-[#151925] border border-white/5 shadow-lg max-h-[550px] overflow-y-auto">
                            <h2 className="text-sm font-medium mb-3 text-white">Support & Resistance</h2>
                            <SupportResistance
                                supportResistance={strategyData?.support_resistance}
                                breakout={strategyData?.breakout}
                            />
                        </div>
                    </div>

                    {/* Market Sentiment (1/3) */}
                    <div className="card p-4 rounded-xl bg-[#151925] border border-white/5 shadow-lg">
                        <h2 className="text-sm font-medium mb-3 text-white">Market Sentiment</h2>
                        {status?.sentiment ? (
                            <>
                                <div className="flex justify-between items-center mb-2">
                                    <div className={`font-bold text-lg ${status.sentiment.score >= 60 ? 'text-green-400' : status.sentiment.score <= 40 ? 'text-red-400' : 'text-yellow-400'}`}>
                                        {status.sentiment.label}
                                    </div>
                                    <div className="text-xs font-mono bg-white/5 px-2 py-1 rounded">{status.sentiment.score}/100</div>
                                </div>
                                <div className="h-2 bg-[#2A2F45] rounded-full overflow-hidden mb-4">
                                    <div className={`h-full rounded-full transition-all duration-1000 ${status.sentiment.score >= 60 ? 'bg-green-500' : status.sentiment.score <= 40 ? 'bg-red-500' : 'bg-yellow-500'}`} style={{ width: `${status.sentiment.score}%` }}></div>
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-xs">
                                    <div className="bg-white/5 p-2 rounded text-center">
                                        <div className="text-gray-500 mb-1">VIX</div>
                                        <div className="font-mono font-bold">{status.sentiment.vix?.toFixed(2)}</div>
                                    </div>
                                    <div className="bg-white/5 p-2 rounded text-center">
                                        <div className="text-gray-500 mb-1">PCR</div>
                                        <div className="font-mono font-bold">{status.sentiment.pcr?.toFixed(2)}</div>
                                    </div>
                                </div>
                            </>
                        ) : (
                            <div className="text-center text-gray-500 text-xs py-4">Waiting for data...</div>
                        )}
                    </div>
                </div>

                {/* ROW 3: EXECUTION & LOGS */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                    {/* Open Positions (2/3) */}
                    <div className="lg:col-span-2">
                        <PositionCards status={status} closePosition={closePosition} />
                    </div>

                    {/* Greeks Panel (1/3) */}
                    <div className="card rounded-xl bg-[#151925] border border-white/5 shadow-lg overflow-hidden">
                        <div className="p-4 overflow-y-auto max-h-[600px]">
                            <GreeksPanel greeks={mergedGreeksData || strategyData?.greeks} />
                        </div>
                    </div>
                </div>

                {/* ROW 4: LOGS / HISTORY */}
                <LogViewer
                    status={status}
                    activeTab={activeTab}
                    setActiveTab={setActiveTab}
                />

                {/* ROW 4: BACKTEST */}
                <BacktestPanel />
            </div>
        </div>
    );
};

export default Dashboard;
