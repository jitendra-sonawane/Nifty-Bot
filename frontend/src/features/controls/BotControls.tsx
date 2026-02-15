import React from 'react';
import Card from '../../shared/Card';
import StatusDot from '../../shared/StatusDot';
import Auth from './Auth';
import { Play, Square } from 'lucide-react';

interface BotControlsProps {
    isAuthenticated: boolean;
    isRunning: boolean;
    startBot: () => void;
    stopBot: () => void;
}

const BotControls: React.FC<BotControlsProps> = ({
    isAuthenticated,
    isRunning,
    startBot,
    stopBot,
}) => {
    return (
        <Card compact>
            <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium">Bot Control</span>
                <StatusDot
                    active={isAuthenticated}
                    label={isAuthenticated ? 'Connected' : 'Disconnected'}
                />
            </div>

            {isAuthenticated ? (
                <div className="space-y-2">
                    {!isRunning ? (
                        <button
                            onClick={() => startBot()}
                            className="w-full py-2.5 rounded-lg font-bold text-sm text-white
                bg-gradient-to-r from-[var(--accent-teal)] to-[var(--accent-cyan)]
                hover:opacity-90 transition-opacity
                flex items-center justify-center gap-2"
                        >
                            <Play size={16} fill="currentColor" />
                            START BOT
                        </button>
                    ) : (
                        <button
                            onClick={() => stopBot()}
                            className="w-full py-2.5 rounded-lg font-bold text-sm text-white
                bg-gradient-to-r from-orange-500 to-rose-500
                hover:opacity-90 transition-opacity animate-pulse-live
                flex items-center justify-center gap-2"
                        >
                            <Square size={16} fill="currentColor" />
                            STOP BOT
                        </button>
                    )}

                    <div className="flex justify-between text-[11px] text-[var(--text-tertiary)] pt-1">
                        <span>Status</span>
                        <span className={isRunning ? 'text-[var(--color-profit-text)]' : 'text-[var(--text-muted)]'}>
                            {isRunning ? '● Running' : '○ Stopped'}
                        </span>
                    </div>
                </div>
            ) : (
                <Auth />
            )}
        </Card>
    );
};

export default BotControls;
