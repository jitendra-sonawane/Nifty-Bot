import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type { HeatmapStock } from './features/market/NiftyHeatmap';
import type { IntelligenceContext, ModuleToggleState } from './types/api';

export interface Nifty50HeatmapResponse {
    stocks: HeatmapStock[];
    error?: string;
}

export interface GreeksUpdate {
    type: 'greeks_update';
    data: {
        atm_strike: number;
        expiry_date: string;
        ce_instrument_key?: string;
        pe_instrument_key?: string;
        ce: {
            delta: number;
            gamma: number;
            theta: number;
            vega: number;
            rho: number;
            iv: number;
            price: number;
        };
        pe: {
            delta: number;
            gamma: number;
            theta: number;
            vega: number;
            rho: number;
            iv: number;
            price: number;
        };
    } | null;
}

export interface PCRUpdate {
    type: 'pcr_update';
    data: {
        pcr: number;
        totalCeOi: number;
        totalPeOi: number;
        timestamp: string;
    };
}

export interface StatusResponse {
    is_running: boolean;
    latest_signal: string;
    current_price: number;
    atm_strike: number;
    last_updated: string;
    logs: string[];
    market_state?: {
        current_price: number;
        atm_strike: number;
        pcr: number | null;
        pcr_analysis: any;
        vix: number | null;
        sentiment: any;
        greeks: any;
        previous_close: number | null;
        market_movement: number | null;
    };
    strategy_data?: {
        signal?: string;
        rsi?: number;
        ema_50?: number;
        ema_5?: number;
        ema_20?: number;
        macd?: number;
        macd_signal?: number;
        supertrend?: string;
        bb_upper?: number;
        bb_lower?: number;
        greeks?: {
            atm_strike: number;
            expiry_date: string;
            ce: { delta: number; gamma: number; theta: number; vega: number; rho: number; iv: number; price: number };
            pe: { delta: number; gamma: number; theta: number; vega: number; rho: number; iv: number; price: number };
        };
        support_resistance?: {
            support_levels: number[];
            resistance_levels: number[];
            nearest_support: number | null;
            nearest_resistance: number | null;
            support_distance_pct: number | null;
            resistance_distance_pct: number | null;
            current_price: number;
        };
        breakout?: {
            is_breakout: boolean;
            breakout_type: 'UPSIDE' | 'DOWNSIDE' | null;
            breakout_level: number | null;
            strength: number;
        };
        filters?: {
            supertrend: boolean;
            rsi: boolean;
            volume: boolean;
            volatility: boolean;
            pcr: boolean;
            greeks: boolean;
            entry_confirmation: boolean;
            ema_crossover?: boolean;
        };
        volume_ratio?: number;
        atr_pct?: number;
    };
    sentiment?: {
        score: number;
        label: string;
        vix: number;
        pcr: number;
    };
    pcr_analysis?: any;
    decision_reason?: string;
    reasoning?: {
        timestamp?: string;
        signal?: string;
        action?: string;
        confidence?: number;
        key_factors?: string[];
        risk_factors?: string[];
        target_levels?: Record<string, any>;
        stop_loss_levels?: Record<string, any>;
        trade_rationale?: string;
        why_now?: string;
        filter_summary?: Record<string, string>;
    };
    target_contract?: string | null;
    trading_mode: string;
    paper_balance: number;
    paper_pnl: number;
    paper_daily_pnl?: number;
    config: {
        timeframe: string;
        symbol: string;
        access_token_present: boolean;
    };
    positions?: Array<{
        id: string;
        instrument_key: string;
        entry_price: number;
        current_price: number;
        quantity: number;
        position_type: string;
        strike?: number;
        stop_loss: number;
        target: number;
        trailing_sl: number | null;
        trailing_sl_activated: boolean;
        entry_time: string;
        unrealized_pnl: number;
        unrealized_pnl_pct: number;
    }>;
    risk_stats?: {
        daily_pnl: number;
        daily_loss_limit: number;
        risk_per_trade_pct: number;
        max_concurrent_positions: number;
        is_trading_allowed: boolean;
    };
    trade_history?: TradeRecord[];
    portfolio_stats?: PortfolioStats;
    auth?: {
        authenticated: boolean;
        token_status: {
            is_valid: boolean;
            expires_at: number | null;
            remaining_seconds: number;
            error_message: string | null;
        };
    };
    intelligence?: IntelligenceContext;
}

export interface TradeLeg {
    instrument_key: string;
    option_type: string;
    transaction_type: string;
    quantity: number;
    entry_price: number;
    exit_price?: number;
    unrealized_pnl?: number;
    strike?: number;
    leg_id?: string;
}

export interface TradeRecord {
    trade_id: string;
    strategy_name: string;
    entry_time: string;
    exit_time: string;
    duration_minutes: number;
    legs: TradeLeg[];
    entry_premium: number;
    exit_premium: number;
    pnl: number;
    pnl_pct: number;
    exit_reason: string;
    // Legacy single-leg fields (may be present for old trades)
    position_id?: string;
    instrument?: string;
    type?: string;
    entry_price?: number;
    exit_price?: number;
    quantity?: number;
    reason?: string;
}

export interface StrategyAnalytics {
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    win_rate: number;
    total_pnl: number;
    avg_pnl: number;
    best_trade: number;
    worst_trade: number;
    profit_factor: number;
}

export interface PortfolioStats {
    initial_capital: number;
    current_balance: number;
    total_equity: number;
    unrealized_pnl: number;
    realized_pnl: number;
    session_pnl: number;
    total_return_pct: number;
    open_positions: number;
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    win_rate: number;
    avg_win: number;
    avg_loss: number;
    best_trade: number;
    worst_trade: number;
    profit_factor: number;
    strategy_analytics: Record<string, StrategyAnalytics>;
}

export const apiSlice = createApi({
    reducerPath: 'api',
    baseQuery: fetchBaseQuery({
        baseUrl: 'http://localhost:8000',
        timeout: 6000,
    }),
    tagTypes: ['Status'],
    endpoints: (builder) => ({
        getStatus: builder.query<StatusResponse, void>({
            query: () => '/status',
            async onCacheEntryAdded(
                _arg,
                { updateCachedData, cacheDataLoaded, cacheEntryRemoved }
            ) {
                // wait for the initial query to resolve before starting
                await cacheDataLoaded

                // In development, we might need to point to localhost:8000 if proxy isn't set up for WS
                // Assuming the frontend proxy handles /ws or we point directly to backend
                const wsUrl = `ws://localhost:8000/ws/status`;

                let ws: WebSocket | null = null;
                let wsConnected = false;
                let reconnectAttempts = 0;
                // Infinite retries for status connection to ensure resilience
                const maxReconnectAttempts = Infinity;
                const baseReconnectDelay = 1000;
                const maxReconnectDelay = 30000;
                let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

                const connectWebSocket = () => {
                    if (reconnectAttempts >= maxReconnectAttempts) {
                        console.warn('Max WebSocket reconnection attempts reached, relying on polling');
                        return;
                    }

                    try {
                        // Close previous connection if exists
                        if (ws) {
                            try {
                                ws.close();
                            } catch (e) {
                                // Ignore
                            }
                            ws = null;
                        }

                        ws = new WebSocket(wsUrl);

                        ws.onopen = () => {
                            wsConnected = true;
                            reconnectAttempts = 0; // Reset on successful connection
                            console.log('✅ WebSocket connected for status updates');
                        };

                        ws.onmessage = (event) => {
                            try {
                                const data = JSON.parse(event.data);
                                updateCachedData((draft) => {
                                    Object.assign(draft, data);
                                });
                            } catch (error) {
                                console.error('Error parsing WebSocket message:', error);
                            }
                        };

                        ws.onerror = (error) => {
                            console.error('⚠️ WebSocket error:', error);
                            wsConnected = false;
                        };

                        ws.onclose = () => {
                            wsConnected = false;
                            console.log('❌ WebSocket disconnected, will attempt to reconnect...');
                            // Attempt to reconnect with exponential backoff
                            reconnectAttempts++;
                            if (reconnectAttempts < maxReconnectAttempts) {
                                const delay = Math.min(baseReconnectDelay * Math.pow(1.5, reconnectAttempts), maxReconnectDelay);
                                console.log(`Reconnecting status in ${delay}ms (Attempt ${reconnectAttempts})`);
                                reconnectTimeout = setTimeout(connectWebSocket, delay);
                            }
                        };
                    } catch (error) {
                        console.error('Error creating WebSocket:', error);
                        reconnectAttempts++;
                        if (reconnectAttempts < maxReconnectAttempts) {
                            const delay = Math.min(baseReconnectDelay * Math.pow(1.5, reconnectAttempts), maxReconnectDelay);
                            reconnectTimeout = setTimeout(connectWebSocket, delay);
                        }
                    }
                };

                // Initial connection attempt
                connectWebSocket();

                await cacheEntryRemoved;
                if (ws !== null && ws !== undefined) {
                    try {
                        (ws as WebSocket).close();
                    } catch (e) {
                        // Ignore
                    }
                }
                if (reconnectTimeout) {
                    clearTimeout(reconnectTimeout);
                }
            },
            keepUnusedDataFor: 0,
        }),
        // Greeks streaming endpoint
        streamGreeks: builder.query<GreeksUpdate, void>({
            query: () => '/greeks',
            async onCacheEntryAdded(
                _arg,
                { updateCachedData, cacheDataLoaded, cacheEntryRemoved }
            ) {
                await cacheDataLoaded;

                const wsUrl = `ws://localhost:8000/ws/greeks`;
                let ws: WebSocket | null = null;
                let reconnectAttempts = 0;
                const maxReconnectAttempts = Infinity;
                const baseReconnectDelay = 1000;
                const maxReconnectDelay = 30000;
                let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

                const connectWebSocket = () => {
                    if (reconnectAttempts >= maxReconnectAttempts) {
                        console.warn('Max Greeks WebSocket reconnection attempts reached');
                        return;
                    }

                    try {
                        // Close previous connection if exists
                        if (ws) {
                            try {
                                ws.close();
                            } catch (e) {
                                // Ignore
                            }
                            ws = null;
                        }

                        ws = new WebSocket(wsUrl);

                        ws.onopen = () => {
                            reconnectAttempts = 0;
                            console.log('✅ WebSocket connected for Greeks streaming');
                        };

                        ws.onmessage = (event) => {
                            try {
                                const update = JSON.parse(event.data);
                                if (update.type === 'greeks_update' || update.data) {
                                    updateCachedData((draft) => {
                                        Object.assign(draft, update);
                                    });
                                }
                            } catch (error) {
                                console.error('Error parsing Greeks update:', error);
                            }
                        };

                        ws.onerror = (error) => {
                            console.error('⚠️ Greeks WebSocket error:', error);
                        };

                        ws.onclose = () => {
                            console.log('❌ Greeks WebSocket disconnected, will attempt to reconnect...');
                            reconnectAttempts++;
                            if (reconnectAttempts < maxReconnectAttempts) {
                                const delay = Math.min(baseReconnectDelay * Math.pow(1.5, reconnectAttempts), maxReconnectDelay);
                                reconnectTimeout = setTimeout(connectWebSocket, delay);
                            }
                        };
                    } catch (error) {
                        console.error('Error creating Greeks WebSocket:', error);
                        reconnectAttempts++;
                        if (reconnectAttempts < maxReconnectAttempts) {
                            const delay = Math.min(baseReconnectDelay * Math.pow(1.5, reconnectAttempts), maxReconnectDelay);
                            reconnectTimeout = setTimeout(connectWebSocket, delay);
                        }
                    }
                };

                connectWebSocket();

                await cacheEntryRemoved;
                if (ws !== null && ws !== undefined) {
                    try {
                        (ws as WebSocket).close();
                    } catch (e) {
                        // Ignore
                    }
                }
                if (reconnectTimeout) {
                    clearTimeout(reconnectTimeout);
                }
            },
            keepUnusedDataFor: 0,
        }),
        // PCR streaming endpoint
        streamPCR: builder.query<PCRUpdate, void>({
            query: () => '/pcr',
            async onCacheEntryAdded(
                _arg,
                { updateCachedData, cacheDataLoaded, cacheEntryRemoved }
            ) {
                await cacheDataLoaded;

                const wsUrl = `ws://localhost:8000/ws/status`; // Use same endpoint, filter by type
                let ws: WebSocket | null = null;
                let reconnectAttempts = 0;
                const maxReconnectAttempts = Infinity;
                const baseReconnectDelay = 1000;
                const maxReconnectDelay = 30000;

                const connectWebSocket = () => {
                    if (reconnectAttempts >= maxReconnectAttempts) {
                        console.warn('Max PCR WebSocket reconnection attempts reached');
                        return;
                    }

                    try {
                        ws = new WebSocket(wsUrl);

                        ws.onopen = () => {
                            reconnectAttempts = 0;
                            console.log('WebSocket connected for PCR streaming');
                        };

                        ws.onmessage = (event) => {
                            try {
                                const update = JSON.parse(event.data);
                                if (update.type === 'pcr_update' || update.data?.pcr) {
                                    updateCachedData((draft) => {
                                        Object.assign(draft, update);
                                    });
                                }
                            } catch (error) {
                                console.error('Error parsing PCR update:', error);
                            }
                        };

                        ws.onerror = (error) => {
                            console.error('PCR WebSocket error:', error);
                        };

                        ws.onclose = () => {
                            console.log('PCR WebSocket disconnected, will attempt to reconnect...');
                            reconnectAttempts++;
                            const delay = Math.min(baseReconnectDelay * Math.pow(1.5, reconnectAttempts), maxReconnectDelay);
                            setTimeout(connectWebSocket, delay);
                        };
                    } catch (error) {
                        console.error('Error creating PCR WebSocket:', error);
                        reconnectAttempts++;
                        const delay = Math.min(baseReconnectDelay * Math.pow(1.5, reconnectAttempts), maxReconnectDelay);
                        setTimeout(connectWebSocket, delay);
                    }
                };

                connectWebSocket();

                await cacheEntryRemoved;
                if (ws !== null && ws !== undefined) {
                    try {
                        (ws as WebSocket).close();
                    } catch (e) {
                        // Ignore
                    }
                }
            },
            keepUnusedDataFor: 0,
        }),
        getLoginUrl: builder.query<{ login_url: string }, void>({
            query: () => '/auth/login',
        }),
        getUserProfile: builder.query<{ user_id: string; user_name: string; email: string }, void>({
            query: () => '/user/profile',
        }),
        startBot: builder.mutation<void, void>({
            query: () => ({
                url: '/start',
                method: 'POST',
            }),
            invalidatesTags: ['Status'],
        }),
        stopBot: builder.mutation<void, void>({
            query: () => ({
                url: '/stop',
                method: 'POST',
            }),
            invalidatesTags: ['Status'],
        }),
        updateConfig: builder.mutation<void, { timeframe: string }>({
            query: (body) => ({
                url: '/config',
                method: 'POST',
                body,
            }),
            invalidatesTags: ['Status'],
        }),
        setTradingMode: builder.mutation<void, { mode: string }>({
            query: (body) => ({
                url: '/mode',
                method: 'POST',
                body,
            }),
            invalidatesTags: ['Status'],
        }),
        addPaperFunds: builder.mutation<void, { amount: number }>({
            query: (body) => ({
                url: '/paper/funds',
                method: 'POST',
                body,
            }),
            invalidatesTags: ['Status'],
        }),
        closePosition: builder.mutation<void, { position_id: string; exit_price: number }>({
            query: (body) => ({
                url: '/positions/close',
                method: 'POST',
                body,
            }),
            invalidatesTags: ['Status'],
        }),
        runBacktest: builder.mutation<any, { from_date: string; to_date: string; initial_capital?: number }>({
            query: (body) => ({
                url: '/backtest',
                method: 'POST',
                body,
            }),
        }),
        toggleIntelligenceModule: builder.mutation<
            { module: string; enabled: boolean; modules: ModuleToggleState },
            { module: string; enabled: boolean }
        >({
            query: (body) => ({
                url: '/intelligence/toggle',
                method: 'POST',
                body,
            }),
            invalidatesTags: ['Status'],
        }),
        // Portfolio stats
        getPortfolioStats: builder.query<PortfolioStats, void>({
            query: () => '/portfolio/stats',
            providesTags: ['Status'],
        }),
        // Trade history / journal
        getTradeHistory: builder.query<{ trades: TradeRecord[] }, { strategy?: string; limit?: number } | void>({
            query: (params) => {
                const p = params as { strategy?: string; limit?: number } | undefined;
                const qs = new URLSearchParams();
                if (p?.strategy) qs.set('strategy', p.strategy);
                if (p?.limit) qs.set('limit', String(p.limit));
                const q = qs.toString();
                return `/portfolio/history${q ? `?${q}` : ''}`;
            },
            providesTags: ['Status'],
        }),
        // Reset portfolio
        resetPortfolio: builder.mutation<{ message: string; stats: PortfolioStats }, void>({
            query: () => ({ url: '/portfolio/reset', method: 'POST' }),
            invalidatesTags: ['Status'],
        }),
        // Nifty 50 Heatmap
        getNifty50Heatmap: builder.query<Nifty50HeatmapResponse, void>({
            query: () => '/api/nifty50/heatmap',
            keepUnusedDataFor: 60,
        }),
        // Nifty 50 Heatmap Streaming
        streamNifty50Heatmap: builder.query<Nifty50HeatmapResponse, void>({
            query: () => '/api/nifty50/heatmap', // Initial fetch via REST
            async onCacheEntryAdded(
                _arg,
                { updateCachedData, cacheDataLoaded, cacheEntryRemoved }
            ) {
                await cacheDataLoaded;

                const wsUrl = `ws://localhost:8000/ws/heatmap`;
                let ws: WebSocket | null = null;
                let reconnectAttempts = 0;
                const maxReconnectAttempts = Infinity;
                const baseReconnectDelay = 1000;
                const maxReconnectDelay = 30000;
                let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

                const connectWebSocket = () => {
                    if (reconnectAttempts >= maxReconnectAttempts) {
                        console.warn('Max Heatmap WebSocket reconnection attempts reached');
                        return;
                    }

                    try {
                        if (ws) {
                            try {
                                ws.close();
                            } catch (e) {
                                // Ignore
                            }
                            ws = null;
                        }

                        ws = new WebSocket(wsUrl);

                        ws.onopen = () => {
                            reconnectAttempts = 0;
                            console.log('✅ WebSocket connected for Heatmap');
                        };

                        ws.onmessage = (event) => {
                            try {
                                const update = JSON.parse(event.data);
                                if (update.type === 'heatmap_update' && update.stocks) {
                                    updateCachedData((draft) => {
                                        if (update.stocks && update.stocks.length > 0) {
                                            draft.stocks = update.stocks;
                                        }
                                    });
                                }
                            } catch (error) {
                                console.error('Error parsing Heatmap update:', error);
                            }
                        };

                        ws.onerror = (error) => {
                            console.error('⚠️ Heatmap WebSocket error:', error);
                        };

                        ws.onclose = () => {
                            console.log('❌ Heatmap WebSocket disconnected, will attempt to reconnect...');
                            reconnectAttempts++;
                            if (reconnectAttempts < maxReconnectAttempts) {
                                const delay = Math.min(baseReconnectDelay * Math.pow(1.5, reconnectAttempts), maxReconnectDelay);
                                reconnectTimeout = setTimeout(connectWebSocket, delay);
                            }
                        };
                    } catch (error) {
                        console.error('Error creating Heatmap WebSocket:', error);
                        reconnectAttempts++;
                        if (reconnectAttempts < maxReconnectAttempts) {
                            const delay = Math.min(baseReconnectDelay * Math.pow(1.5, reconnectAttempts), maxReconnectDelay);
                            reconnectTimeout = setTimeout(connectWebSocket, delay);
                        }
                    }
                };

                connectWebSocket();

                await cacheEntryRemoved;
                if (ws !== null && ws !== undefined) {
                    try {
                        (ws as WebSocket).close();
                    } catch (e) {
                        // Ignore
                    }
                }
                if (reconnectTimeout) {
                    clearTimeout(reconnectTimeout);
                }
            },
            keepUnusedDataFor: 0,
        }),
    }),
});

export const {
    useGetStatusQuery,
    useStartBotMutation,
    useStopBotMutation,
    useUpdateConfigMutation,
    useGetLoginUrlQuery,
    useGetUserProfileQuery,
    useSetTradingModeMutation,
    useAddPaperFundsMutation,
    useClosePositionMutation,
    useRunBacktestMutation,
    useStreamGreeksQuery,
    useStreamPCRQuery,
    useGetNifty50HeatmapQuery,
    useStreamNifty50HeatmapQuery,
    useToggleIntelligenceModuleMutation,
    useGetPortfolioStatsQuery,
    useGetTradeHistoryQuery,
    useResetPortfolioMutation,
} = apiSlice;

