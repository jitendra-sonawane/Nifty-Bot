import React, { useState, useEffect, useRef } from 'react';
import PositionCards from './PositionCards';
import BacktestPanel from './BacktestPanel';
import PriceChart from './PriceChart';
import IndicatorPanel from './IndicatorPanel';
import SupportResistance from './SupportResistance';
import GreeksPanel from './GreeksPanel';
import ReasoningCard from './ReasoningCard';
import FilterStatusPanel from './FilterStatusPanel';
import SentimentPanel from './SentimentPanel';
import { useGetStatusQuery, useStreamGreeksQuery, useStartBotMutation, useStopBotMutation, useSetTradingModeMutation, useAddPaperFundsMutation, useClosePositionMutation } from './apiSlice';
import { Activity } from 'lucide-react';

// New Components
import Header from './components/dashboard/Header';
import MetricsGrid from './components/dashboard/MetricsGrid';
import ControlPanel from './components/dashboard/ControlPanel';
import LogViewer from './components/dashboard/LogViewer';
import DashboardLayout from './components/layout/DashboardLayout';
import Column from './components/layout/Column';

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
        <DashboardLayout>
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
                isAuthenticated={isAuthenticated || false}
                tokenStatus={tokenStatus || ''}
                time={time}
                handleModeToggle={handleModeToggle}
                handleAddFunds={handleAddFunds}
            />

            {/* KEY METRICS */}
            <MetricsGrid
                currentPrice={currentPrice}
                priceHistory={priceHistory}
                signal={signal}
                status={status}
            />

            {/* MAIN 3-COLUMN GRID */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">

                {/* COLUMN 1: MARKET CONTEXT (40%) */}
                <Column className="lg:col-span-5">
                    {/* Main Chart Area */}
                    <div className="card p-4 rounded-xl bg-[#151925] border border-white/5 shadow-lg h-[350px] flex flex-col">
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
                            <PriceChart data={priceHistory} height={280} />
                        </div>
                    </div>

                    {/* Indicator Grid */}
                    <IndicatorPanel strategyData={strategyData} currentPrice={currentPrice} />

                    {/* Support/Resistance */}
                    <div className="card p-4 rounded-xl bg-[#151925] border border-white/5 shadow-lg max-h-[400px] overflow-y-auto">
                        <h2 className="text-sm font-medium mb-3 text-white">Support & Resistance</h2>
                        <SupportResistance
                            supportResistance={strategyData?.support_resistance}
                            breakout={strategyData?.breakout}
                        />
                    </div>
                </Column>

                {/* COLUMN 2: BOT INTELLIGENCE (30%) */}
                <Column className="lg:col-span-4">
                    {/* Market Sentiment */}
                    <SentimentPanel status={status} />

                    {/* Trading Reasoning */}
                    <div className="card rounded-xl bg-[#151925] border border-white/5 shadow-lg overflow-hidden">
                        <div className="p-4 overflow-y-auto max-h-[300px]">
                            <ReasoningCard
                                reasoning={status?.reasoning}
                                currentPrice={currentPrice}
                            />
                        </div>
                    </div>

                    {/* Live Filter Metrics */}
                    <div className="card rounded-xl bg-[#151925] border border-white/5 shadow-lg overflow-hidden">
                        <div className="p-4 overflow-y-auto max-h-[300px]">
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

                    {/* Logs (Compact) */}
                    <div className="card rounded-xl bg-[#151925] border border-white/5 shadow-lg overflow-hidden h-[300px]">
                        <LogViewer
                            status={status}
                            activeTab={activeTab}
                            setActiveTab={setActiveTab}
                        />
                    </div>
                </Column>

                {/* COLUMN 3: EXECUTION & CONTROL (30%) */}
                <Column className="lg:col-span-3">
                    {/* Controls */}
                    <ControlPanel
                        isAuthenticated={isAuthenticated || false}
                        isRunning={isRunning || false}
                        startBot={startBot}
                        stopBot={stopBot}
                    />

                    {/* Open Positions */}
                    <PositionCards status={status} closePosition={closePosition} />

                    {/* Greeks Panel */}
                    <div className="card rounded-xl bg-[#151925] border border-white/5 shadow-lg overflow-hidden">
                        <div className="p-4 overflow-y-auto max-h-[400px]">
                            <GreeksPanel greeks={mergedGreeksData || strategyData?.greeks} />
                        </div>
                    </div>
                </Column>
            </div>

            {/* BOTTOM: BACKTEST */}
            <BacktestPanel />
        </DashboardLayout>
    );
};

export default Dashboard;
