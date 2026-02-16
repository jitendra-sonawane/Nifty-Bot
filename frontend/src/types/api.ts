/* ═══════════════════════════════════════════
   API TYPE DEFINITIONS
   Extracted from apiSlice.ts for reuse
   ═══════════════════════════════════════════ */

export interface GreeksData {
    delta?: number;
    gamma?: number;
    theta?: number;
    vega?: number;
    rho?: number;
    iv?: number;
    price?: number;
}

export interface GreeksInfo {
    atm_strike?: number;
    expiry_date?: string;
    ce?: GreeksData;
    pe?: GreeksData;
}

export interface SupportResistanceData {
    support_levels: number[];
    resistance_levels: number[];
    nearest_support: number | null;
    nearest_resistance: number | null;
    support_distance_pct: number | null;
    resistance_distance_pct: number | null;
    current_price: number;
}

export interface BreakoutData {
    is_breakout: boolean;
    breakout_type: 'UPSIDE' | 'DOWNSIDE' | null;
    breakout_level: number | null;
    strength: number;
}

export interface FilterData {
    supertrend: boolean;
    rsi: boolean;
    volume: boolean;
    volatility: boolean;
    pcr: boolean;
    greeks: boolean;
    entry_confirmation: boolean;
    ema_crossover?: boolean;

    // Intelligence Filters
    market_regime?: boolean;
    iv_rank?: boolean;
    market_breadth?: boolean;
    order_book?: boolean;
    vix?: boolean;
    pcr_trend?: boolean;
    time_of_day?: boolean;
    oi_buildup?: boolean;
    expiry_day?: boolean;
}

export interface StrategyData {
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
    greeks?: GreeksInfo;
    support_resistance?: SupportResistanceData;
    breakout?: BreakoutData;
    filters?: FilterData;
    volume_ratio?: number;
    atr_pct?: number;
}

export interface ReasoningData {
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
}

export interface Position {
    id: string;
    order_id?: string;
    order_status?: string;
    instrument_key: string;
    entry_price: number;
    current_price?: number;
    quantity: number;
    position_type: string;
    strike?: number;
    stop_loss: number;
    target: number;
    trailing_sl: number | null;
    trailing_sl_activated: boolean;
    entry_time: string;
    unrealized_pnl?: number;
    unrealized_pnl_pct?: number;
}

export interface Trade {
    position_id: string;
    instrument: string;
    type: string;
    entry_price: number;
    exit_price: number;
    quantity: number;
    pnl: number;
    pnl_pct: number;
    reason: string;
    entry_time: string;
    exit_time: string;
}

export interface RiskStats {
    daily_pnl: number;
    daily_loss_limit: number;
    risk_per_trade_pct: number;
    max_concurrent_positions: number;
    is_trading_allowed: boolean;
}

export interface PricePoint {
    time: string;
    price: number;
}

// ═══ Intelligence Engine Types ═══════════════════════════════════════════

export interface MarketRegimeContext {
    regime: 'TRENDING' | 'RANGING' | 'HIGH_VOLATILITY' | 'UNKNOWN';
    adx: number | null;
    bb_width_pct: number | null;
    atr_pct: number | null;
    allowed_strategies: string[];
    regime_reason: string;
}

export interface IVRankContext {
    iv_rank: number | null;
    iv_percentile: number | null;
    current_iv: number | null;
    iv_30d_high: number | null;
    iv_30d_low: number | null;
    iv_avg: number | null;
    recommendation: 'SELL_PREMIUM' | 'BUY_DEBIT' | 'NEUTRAL';
    premium_selling_ok: boolean;
    history_size: number;
}

export interface MarketBreadthContext {
    advancing: number;
    declining: number;
    unchanged: number;
    ad_ratio: number | null;
    breadth_score: number;
    breadth_bias: string;
    top_movers_up: string[];
    top_movers_down: string[];
    coverage: number;
    breadth_confirms_ce: boolean;
    breadth_confirms_pe: boolean;
}

export interface OrderBookContext {
    ce_imbalance: number | null;
    pe_imbalance: number | null;
    ce_spread_pct: number | null;
    pe_spread_pct: number | null;
    imbalance_signal: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    ce_liquidity: string;
    pe_liquidity: string;
    entry_quality: number;
}

export interface PortfolioGreeksContext {
    net_delta: number;
    net_gamma: number;
    net_theta: number;
    net_vega: number;
    delta_bias: string;
    hedge_needed: boolean;
    hedge_action: string | null;
    portfolio_risk: 'HIGH' | 'MEDIUM' | 'LOW';
    position_count: number;
}

export interface OIAnalysisContext {
    buildup_signal: 'LONG_BUILDUP' | 'SHORT_COVERING' | 'SHORT_BUILDUP' | 'LONG_UNWINDING' | 'NEUTRAL';
    oi_change_pct: number;
    ce_oi_change_pct: number;
    pe_oi_change_pct: number;
    price_direction: 'UP' | 'DOWN' | 'FLAT';
    confirms_ce: boolean;
    confirms_pe: boolean;
    max_oi_ce_strike: number | null;
    max_oi_pe_strike: number | null;
    max_pain_strike: number | null;
    distance_from_max_pain: number | null;
    distance_from_max_pain_pct: number | null;
    snapshots_count: number;
}

export interface PDHPDLPDCData {
    pdh: number | null;
    pdl: number | null;
    pdc: number | null;
}

export interface IntelligenceContext {
    market_regime?: MarketRegimeContext;
    iv_rank?: IVRankContext;
    market_breadth?: MarketBreadthContext;
    order_book?: OrderBookContext;
    portfolio_greeks?: PortfolioGreeksContext;
    oi_analysis?: OIAnalysisContext;
}

export interface ModuleToggleState {
    [moduleName: string]: boolean;
}
