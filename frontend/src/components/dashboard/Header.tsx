import React from 'react';
import { Wallet } from 'lucide-react';

interface HeaderProps {
    status: any;
    isAuthenticated: boolean;
    tokenStatus: any;
    time: Date;
    handleModeToggle: () => void;
    handleAddFunds: () => void;
}

const Header: React.FC<HeaderProps> = ({ status, isAuthenticated, tokenStatus, time, handleModeToggle, handleAddFunds }) => {
    return (
        <div className="rounded-lg p-3 flex justify-between items-center bg-gradient-to-r from-[#0f1724] via-[#1b1033] to-[#2b0650] shadow-lg border border-white/5">
            <div className="flex items-center gap-3">
                <h1 className="text-2xl font-extrabold tracking-wide bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-400">NIFTYBOT</h1>
                <div className={`px-3 py-1 rounded-full text-xs font-bold border ${status?.trading_mode === 'REAL' ? 'bg-red-500/20 border-red-500 text-red-400' : 'bg-blue-500/20 border-blue-500 text-blue-400'}`}>
                    {status?.trading_mode === 'REAL' ? 'REAL MONEY' : 'PAPER TRADING'}
                </div>
                {isAuthenticated && tokenStatus?.remaining_seconds && tokenStatus.remaining_seconds < 3600 && tokenStatus.remaining_seconds > 0 && (
                    <div className="px-3 py-1 rounded-full text-xs font-bold bg-yellow-500/20 border border-yellow-500 text-yellow-400">
                        ⚠️ Token expires in {Math.floor(tokenStatus.remaining_seconds / 60)}m
                    </div>
                )}
            </div>
            <div className="flex items-center gap-3">
                {status?.trading_mode === 'PAPER' && (
                    <div className="flex items-center gap-2 bg-white/5 px-3 py-1.5 rounded-lg border border-white/5">
                        <div className="text-right">
                            <div className="text-[9px] text-gray-400 uppercase tracking-wider">Paper Balance</div>
                            <div className="font-mono text-sm font-bold text-white">₹{status.paper_balance?.toLocaleString('en-IN')}</div>
                        </div>
                        <button onClick={handleAddFunds} className="p-1.5 hover:bg-white/10 rounded-lg transition-colors"><Wallet size={16} className="text-blue-400" /></button>
                    </div>
                )}
                <button onClick={handleModeToggle} className={`px-3 py-1.5 rounded-lg font-bold text-xs border ${status?.trading_mode === 'REAL' ? 'bg-blue-500 hover:bg-blue-600 border-blue-600' : 'bg-red-500 hover:bg-red-600 border-red-600'}`}>
                    {status?.trading_mode === 'REAL' ? 'PAPER' : 'REAL'}
                </button>
                <div className="px-3 py-1.5 rounded-lg bg-white/5 text-gray-300 font-mono text-xs">{time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
            </div>
        </div>
    );
};

export default Header;
