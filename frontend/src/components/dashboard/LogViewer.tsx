import React from 'react';
import { Terminal, Database } from 'lucide-react';

interface LogViewerProps {
    status: any;
    activeTab: 'logs' | 'history';
    setActiveTab: (tab: 'logs' | 'history') => void;
}

const LogViewer: React.FC<LogViewerProps> = ({ status, activeTab, setActiveTab }) => {
    return (
        <div className="card rounded-xl bg-[#151925] border border-white/5 shadow-lg overflow-hidden flex flex-col h-[300px]">
            <div className="flex border-b border-white/5">
                <button
                    onClick={() => setActiveTab('logs')}
                    className={`flex-1 py-3 text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 ${activeTab === 'logs' ? 'bg-white/5 text-white border-b-2 border-blue-500' : 'text-gray-500 hover:text-gray-300'}`}
                >
                    <Terminal size={14} /> Live Logs
                </button>
                <button
                    onClick={() => setActiveTab('history')}
                    className={`flex-1 py-3 text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 ${activeTab === 'history' ? 'bg-white/5 text-white border-b-2 border-purple-500' : 'text-gray-500 hover:text-gray-300'}`}
                >
                    <Database size={14} /> Trade History
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-3 font-mono text-[10px]">
                {activeTab === 'logs' ? (
                    <div className="space-y-1">
                        {status?.logs && status.logs.length > 0 ? (
                            status.logs.slice().reverse().map((log: string, i: number) => (
                                <div key={i} className="text-gray-400 border-b border-white/5 pb-1 mb-1 last:border-0">
                                    <span className="text-gray-600 mr-2">{log.split(']')[0]}]</span>
                                    <span className={log.includes('ERROR') ? 'text-red-400' : log.includes('SIGNAL') ? 'text-yellow-400' : 'text-gray-300'}>
                                        {log.split(']')[1]}
                                    </span>
                                </div>
                            ))
                        ) : <div className="text-gray-600 text-center mt-10">No logs yet...</div>}
                    </div>
                ) : (
                    <div className="space-y-2">
                        {status?.trade_history && status.trade_history.length > 0 ? (
                            status.trade_history.slice().reverse().map((trade: any, i: number) => (
                                <div key={i} className="bg-white/5 p-2 rounded border border-white/5">
                                    <div className="flex justify-between mb-1">
                                        <span className={`font-bold ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>{trade.position_type}</span>
                                        <span className="text-gray-500">{trade.exit_time.split('T')[1]?.split('.')[0]}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-gray-400">P&L</span>
                                        <span className={`font-bold ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>₹{trade.pnl.toFixed(2)}</span>
                                    </div>
                                </div>
                            ))
                        ) : <div className="text-gray-600 text-center mt-10">No trades yet...</div>}
                    </div>
                )}
            </div>
        </div>
    );
};

export default LogViewer;
