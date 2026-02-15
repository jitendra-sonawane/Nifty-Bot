import { useState, useEffect, useRef, useCallback } from 'react';
import {
    useGetStatusQuery,
    useStreamGreeksQuery,
    useStartBotMutation,
    useStopBotMutation,
    useSetTradingModeMutation,
    useAddPaperFundsMutation,
    useClosePositionMutation,
    useToggleIntelligenceModuleMutation,
} from '../apiSlice';
import type { PricePoint, IntelligenceContext } from '../types/api';

export function useDashboard() {
    const { data: status, isLoading, isError, refetch } = useGetStatusQuery(undefined, {
        pollingInterval: 2000,
    });
    const { data: greeksStreamData } = useStreamGreeksQuery();

    // Merge WebSocket stream data with HTTP data
    const [mergedGreeksData, setMergedGreeksData] = useState<any>(null);

    const isAuthenticated = status?.auth?.authenticated ?? false;
    const tokenStatus = status?.auth?.token_status;

    useEffect(() => {
        if (greeksStreamData?.data) {
            const wsData = greeksStreamData.data;
            if (wsData.ce && wsData.pe) {
                setMergedGreeksData(wsData);
            }
        } else if (status?.market_state?.greeks) {
            setMergedGreeksData(status.market_state.greeks);
        } else if (status?.strategy_data?.greeks) {
            setMergedGreeksData(status.strategy_data.greeks);
        }
    }, [greeksStreamData, status?.market_state?.greeks, status?.strategy_data?.greeks]);

    // Listen for auth_success from OAuth popup
    useEffect(() => {
        const handler = (event: MessageEvent) => {
            if (event.data === 'auth_success') {
                setTimeout(() => refetch(), 2000);
                setTimeout(() => refetch(), 4000);
                setTimeout(() => refetch(), 6000);
            }
        };
        window.addEventListener('message', handler);
        return () => window.removeEventListener('message', handler);
    }, [refetch]);

    // Mutations
    const [startBot] = useStartBotMutation();
    const [stopBot] = useStopBotMutation();
    const [setTradingMode] = useSetTradingModeMutation();
    const [addPaperFunds] = useAddPaperFundsMutation();
    const [closePosition] = useClosePositionMutation();
    const [toggleModuleMutation] = useToggleIntelligenceModuleMutation();

    // Mode switch modal state
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [pendingMode, setPendingMode] = useState<string | null>(null);

    const handleModeToggle = useCallback(() => {
        const newMode = status?.trading_mode === 'REAL' ? 'PAPER' : 'REAL';
        setPendingMode(newMode);
        setIsModalOpen(true);
    }, [status?.trading_mode]);

    const confirmSwitch = useCallback(() => {
        if (pendingMode) setTradingMode({ mode: pendingMode });
        setIsModalOpen(false);
        setPendingMode(null);
    }, [pendingMode, setTradingMode]);

    const cancelSwitch = useCallback(() => {
        setIsModalOpen(false);
        setPendingMode(null);
    }, []);

    const handleAddFunds = useCallback(() => {
        const amount = prompt('Enter amount to add to Paper Funds:', '100000');
        if (amount && !isNaN(parseFloat(amount))) {
            addPaperFunds({ amount: parseFloat(amount) });
        }
    }, [addPaperFunds]);

    // Intelligence module toggle
    const toggleIntelligenceModule = useCallback((module: string, enabled: boolean) => {
        toggleModuleMutation({ module, enabled });
    }, [toggleModuleMutation]);

    // Derived data
    const currentPrice = status?.current_price || 0;
    const isRunning = status?.is_running ?? false;
    const strategyData = status?.strategy_data || {};
    const signal = status?.latest_signal || 'WAITING';
    const intelligence: IntelligenceContext | undefined = status?.intelligence;

    // Price history
    const [priceHistory, setPriceHistory] = useState<PricePoint[]>([]);
    const lastPriceRef = useRef(0);

    useEffect(() => {
        if (currentPrice && currentPrice !== lastPriceRef.current) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
            });
            setPriceHistory((prev) => {
                const newHistory = [...prev, { time: timeStr, price: currentPrice }];
                return newHistory.slice(-60);
            });
            lastPriceRef.current = currentPrice;
        }
    }, [currentPrice]);

    // Live clock
    const [time, setTime] = useState(new Date());
    useEffect(() => {
        const timer = setInterval(() => setTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    return {
        // Data
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
        intelligence,

        // Modal state
        isModalOpen,
        pendingMode,

        // Actions
        startBot,
        stopBot,
        handleModeToggle,
        confirmSwitch,
        cancelSwitch,
        handleAddFunds,
        closePosition,
        toggleIntelligenceModule,
    };
}
