import React from 'react';
import { Zap, Wallet, Clock } from 'lucide-react';
import Badge from '../shared/Badge';
import StatusDot from '../shared/StatusDot';
import Sparkline from '../shared/Sparkline';
import { useGetUserProfileQuery } from '../apiSlice';

interface TopbarProps {
    currentPrice: number;
    priceHistory: { time: string; price: number }[];
    status: any;
    isAuthenticated: boolean;
    tokenStatus: any;
    time: Date;
    handleModeToggle: () => void;
    handleAddFunds: () => void;
}

const Topbar: React.FC<TopbarProps> = ({
    currentPrice,
    priceHistory,
    status,
    isAuthenticated,
    tokenStatus,
    time,
    handleModeToggle,
    handleAddFunds,
}) => {
    const { data: userProfile } = useGetUserProfileQuery(undefined, {
        skip: !isAuthenticated,
    });

    const marketMovement = status?.market_state?.market_movement;
    const isUp = marketMovement != null && marketMovement >= 0;
    const sparkData = priceHistory.map((p) => p.price);

    return (
        <div className="max-w-[var(--max-content)] mx-auto px-3 lg:px-4 h-[var(--topbar-height)] flex items-center justify-between gap-4">
            {/* LEFT: Logo + Connection */}
            <div className="flex items-center gap-3 flex-shrink-0">
                <div className="flex items-center gap-2">
                    <Zap size={18} className="text-[var(--accent-indigo)]" />
                    <span className="text-[var(--text-lg)] font-bold tracking-tight bg-gradient-to-r from-[var(--accent-blue)] to-[var(--accent-purple)] bg-clip-text text-transparent">
                        NIFTYBOT
                    </span>
                </div>

                <StatusDot
                    active={isAuthenticated}
                    label={isAuthenticated ? 'Live' : 'Offline'}
                />
            </div>

            {/* CENTER: Market Ticker */}
            <div className="flex items-center gap-4 flex-1 justify-center">
                <div className="flex items-center gap-3">
                    <span className="label">Nifty 50</span>
                    <span className="text-lg font-bold mono">
                        {currentPrice > 0
                            ? currentPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })
                            : '--'}
                    </span>
                    {marketMovement != null && (
                        <span
                            className={`text-sm font-semibold mono ${isUp ? 'profit' : 'loss'}`}
                        >
                            {isUp ? '▲' : '▼'} {Math.abs(marketMovement).toFixed(2)}
                        </span>
                    )}
                    <Sparkline data={sparkData} width={64} height={20} />
                </div>
            </div>

            {/* RIGHT: Controls */}
            <div className="flex items-center gap-2 flex-shrink-0">
                {/* Token expiry warning */}
                {isAuthenticated &&
                    tokenStatus?.remaining_seconds &&
                    tokenStatus.remaining_seconds < 3600 &&
                    tokenStatus.remaining_seconds > 0 && (
                        <Badge variant="warning" dot size="sm">
                            Token {Math.floor(tokenStatus.remaining_seconds / 60)}m
                        </Badge>
                    )}

                {/* User welcome */}
                {isAuthenticated && userProfile?.user_name && (
                    <span className="text-[var(--text-tertiary)] text-[11px] hidden lg:block">
                        {userProfile.user_name}
                    </span>
                )}

                {/* Paper balance */}
                {status?.trading_mode === 'PAPER' && (
                    <button
                        onClick={handleAddFunds}
                        className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-[var(--bg-hover)] hover:bg-[var(--bg-active)] transition-colors"
                    >
                        <Wallet size={13} className="text-[var(--accent-blue)]" />
                        <span className="mono text-[11px] text-[var(--text-secondary)]">
                            ₹{status.paper_balance?.toLocaleString('en-IN')}
                        </span>
                    </button>
                )}

                {/* Mode badge */}
                <button onClick={handleModeToggle}>
                    <Badge
                        variant={status?.trading_mode === 'REAL' ? 'real' : 'paper'}
                        dot
                        size="md"
                    >
                        {status?.trading_mode === 'REAL' ? 'REAL' : 'PAPER'}
                    </Badge>
                </button>

                {/* Clock */}
                <div className="flex items-center gap-1 text-[var(--text-muted)] text-[11px] mono">
                    <Clock size={12} />
                    {time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
            </div>
        </div>
    );
};

export default Topbar;
