import React from 'react';
import { Play, Square, Wifi, WifiOff } from 'lucide-react';
import Auth from '../../Auth';

interface ControlPanelProps {
    isAuthenticated: boolean;
    isRunning: boolean;
    startBot: () => void;
    stopBot: () => void;
}

const ControlPanel: React.FC<ControlPanelProps> = ({ isAuthenticated, isRunning, startBot, stopBot }) => {
    return (
        <div className="space-y-3">
            {/* Upstox Connection Status */}
            <div className={`card p-4 rounded-xl border shadow-lg flex items-center justify-between ${isAuthenticated ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
                <div className="flex items-center gap-3">
                    {isAuthenticated ? (
                        <>
                            <Wifi size={18} className="text-green-400 animate-pulse" />
                            <div>
                                <div className="text-sm font-bold text-green-400">Upstox Connected</div>
                                <div className="text-[10px] text-green-300/70">Token Valid</div>
                            </div>
                        </>
                    ) : (
                        <>
                            <WifiOff size={18} className="text-red-400" />
                            <div>
                                <div className="text-sm font-bold text-red-400">Upstox Disconnected</div>
                                <div className="text-[10px] text-red-300/70">Token Required</div>
                            </div>
                        </>
                    )}
                </div>
                <div className={`w-3 h-3 rounded-full ${isAuthenticated ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
            </div>

            {/* System Control */}
            <div className="card p-4 rounded-xl bg-[#151925] border border-white/5 shadow-lg">
                <h2 className="text-sm font-medium mb-3 text-white">System Control</h2>
                {isAuthenticated ? (
                    !isRunning ? (
                        <button onClick={() => startBot()} className="w-full py-3 bg-gradient-to-r from-teal-400 to-cyan-500 text-white font-bold rounded-lg hover:shadow-lg transition-all flex items-center justify-center gap-2 text-sm">
                            <Play size={18} fill="currentColor" /> START BOT
                        </button>
                    ) : (
                        <button onClick={() => stopBot()} className="w-full py-3 bg-gradient-to-r from-orange-400 to-pink-500 text-white font-bold rounded-lg shadow-lg hover:shadow-xl transition-all flex items-center justify-center gap-2 text-sm animate-pulse-soft">
                            <Square size={18} fill="currentColor" /> STOP BOT
                        </button>
                    )
                ) : (
                    <Auth />
                )}
                <div className="mt-3 pt-3 border-t border-white/10 flex justify-between text-xs text-gray-400">
                    <span>Status</span>
                    <span className={isRunning ? "text-green-400" : "text-gray-500"}>{isRunning ? "Running" : "Stopped"}</span>
                </div>
            </div>
        </div>
    );
};

export default ControlPanel;
