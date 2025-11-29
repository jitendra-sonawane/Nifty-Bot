import React from 'react';
import { TrendingUp, TrendingDown, Zap, AlertCircle } from 'lucide-react';

interface GreeksData {
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;
  iv?: number;
  price?: number;
}

interface GreeksPanelProps {
  greeks?: {
    atm_strike?: number;
    expiry_date?: string;
    ce?: GreeksData;
    pe?: GreeksData;
  };
}

const GreeksPanel: React.FC<GreeksPanelProps> = ({ greeks }) => {
  if (!greeks || !greeks.ce || !greeks.pe) {
    return (
      <div className="bg-purple-500/5 border border-purple-500/20 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-3">
          <Zap className="w-4 h-4 text-purple-400" />
          <h2 className="text-sm font-medium text-purple-300">Option Greeks</h2>
        </div>
        <div className="space-y-2">
          <div className="text-xs text-gray-400 text-center py-2">
            <div className="mb-2">⏳ Waiting for Greeks data...</div>
            <div className="text-[10px] text-gray-500 bg-yellow-500/10 border border-yellow-500/20 rounded p-2">
              <div className="font-semibold text-yellow-400 mb-1">💡 Tip:</div>
              <div>1. Make sure you're authenticated with Upstox</div>
              <div>2. Click <strong>START BOT</strong> to begin market data streaming</div>
              <div>3. Greeks will calculate every 5 seconds once running</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const ce = greeks.ce;
  const pe = greeks.pe;
  const strike = greeks.atm_strike || 0;
  const expiry = greeks.expiry_date || '';

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-500/20 to-blue-500/20 border border-purple-500/30 rounded-lg p-3">
        <div className="flex items-center gap-2 mb-2">
          <Zap className="w-4 h-4 text-purple-400" />
          <h2 className="text-sm font-bold text-purple-300">Option Greeks</h2>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-gray-400">ATM Strike</span>
            <div className="font-bold text-white">₹{strike}</div>
          </div>
          <div>
            <span className="text-gray-400">Expiry</span>
            <div className="font-bold text-white">{expiry}</div>
          </div>
        </div>
      </div>

      {/* Call Options (CE) */}
      <div className="bg-green-500/5 border border-green-500/20 rounded-lg p-3">
        <div className="flex items-center gap-2 mb-3 pb-2 border-b border-green-500/20">
          <TrendingUp className="w-4 h-4 text-green-400" />
          <h3 className="text-sm font-bold text-green-300">Call Options (CE)</h3>
          <span className="ml-auto text-xs bg-green-500/20 px-2 py-1 rounded text-green-300 font-mono">
            ₹{ce.price?.toFixed(2)}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          {/* Delta */}
          <div className="bg-green-500/10 rounded p-2">
            <div className="text-[10px] text-green-200/60 mb-1">Delta</div>
            <div className="text-sm font-bold text-green-300">{ce.delta?.toFixed(3)}</div>
            <div className="text-[9px] text-green-200/50">Directional</div>
          </div>

          {/* Gamma */}
          <div className="bg-green-500/10 rounded p-2">
            <div className="text-[10px] text-green-200/60 mb-1">Gamma</div>
            <div className="text-sm font-bold text-green-300">{ce.gamma?.toFixed(4)}</div>
            <div className="text-[9px] text-green-200/50">Delta Change</div>
          </div>

          {/* Theta */}
          <div className={`rounded p-2 ${ce.theta && ce.theta < -50 ? 'bg-red-500/10 border border-red-500/30' : 'bg-green-500/10'}`}>
            <div className="text-[10px] text-green-200/60 mb-1">Theta</div>
            <div className={`text-sm font-bold ${ce.theta && ce.theta < -50 ? 'text-red-300' : 'text-green-300'}`}>
              {ce.theta?.toFixed(2)}
            </div>
            <div className="text-[9px] text-green-200/50">Time Decay/Day</div>
          </div>

          {/* Vega */}
          <div className="bg-green-500/10 rounded p-2">
            <div className="text-[10px] text-green-200/60 mb-1">Vega</div>
            <div className="text-sm font-bold text-green-300">{ce.vega?.toFixed(4)}</div>
            <div className="text-[9px] text-green-200/50">IV Sensitivity</div>
          </div>

          {/* IV */}
          <div className="bg-blue-500/10 rounded p-2">
            <div className="text-[10px] text-blue-200/60 mb-1">IV</div>
            <div className="text-sm font-bold text-blue-300">{((ce.iv || 0) * 100).toFixed(1)}%</div>
            <div className="text-[9px] text-blue-200/50">Volatility</div>
          </div>

          {/* Rho */}
          <div className="bg-green-500/10 rounded p-2">
            <div className="text-[10px] text-green-200/60 mb-1">Rho</div>
            <div className="text-sm font-bold text-green-300">{ce.rho?.toFixed(4)}</div>
            <div className="text-[9px] text-green-200/50">Rate Sensitive</div>
          </div>
        </div>
      </div>

      {/* Put Options (PE) */}
      <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
        <div className="flex items-center gap-2 mb-3 pb-2 border-b border-red-500/20">
          <TrendingDown className="w-4 h-4 text-red-400" />
          <h3 className="text-sm font-bold text-red-300">Put Options (PE)</h3>
          <span className="ml-auto text-xs bg-red-500/20 px-2 py-1 rounded text-red-300 font-mono">
            ₹{pe.price?.toFixed(2)}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          {/* Delta */}
          <div className="bg-red-500/10 rounded p-2">
            <div className="text-[10px] text-red-200/60 mb-1">Delta</div>
            <div className="text-sm font-bold text-red-300">{pe.delta?.toFixed(3)}</div>
            <div className="text-[9px] text-red-200/50">Directional</div>
          </div>

          {/* Gamma */}
          <div className="bg-red-500/10 rounded p-2">
            <div className="text-[10px] text-red-200/60 mb-1">Gamma</div>
            <div className="text-sm font-bold text-red-300">{pe.gamma?.toFixed(4)}</div>
            <div className="text-[9px] text-red-200/50">Delta Change</div>
          </div>

          {/* Theta */}
          <div className={`rounded p-2 ${pe.theta && pe.theta < -50 ? 'bg-red-500/10 border border-red-500/30' : 'bg-red-500/10'}`}>
            <div className="text-[10px] text-red-200/60 mb-1">Theta</div>
            <div className={`text-sm font-bold ${pe.theta && pe.theta < -50 ? 'text-red-300' : 'text-red-300'}`}>
              {pe.theta?.toFixed(2)}
            </div>
            <div className="text-[9px] text-red-200/50">Time Decay/Day</div>
          </div>

          {/* Vega */}
          <div className="bg-red-500/10 rounded p-2">
            <div className="text-[10px] text-red-200/60 mb-1">Vega</div>
            <div className="text-sm font-bold text-red-300">{pe.vega?.toFixed(4)}</div>
            <div className="text-[9px] text-red-200/50">IV Sensitivity</div>
          </div>

          {/* IV */}
          <div className="bg-blue-500/10 rounded p-2">
            <div className="text-[10px] text-blue-200/60 mb-1">IV</div>
            <div className="text-sm font-bold text-blue-300">{((pe.iv || 0) * 100).toFixed(1)}%</div>
            <div className="text-[9px] text-blue-200/50">Volatility</div>
          </div>

          {/* Rho */}
          <div className="bg-red-500/10 rounded p-2">
            <div className="text-[10px] text-red-200/60 mb-1">Rho</div>
            <div className="text-sm font-bold text-red-300">{pe.rho?.toFixed(4)}</div>
            <div className="text-[9px] text-red-200/50">Rate Sensitive</div>
          </div>
        </div>
      </div>

      {/* Greeks Legend */}
      <div className="bg-yellow-500/5 border border-yellow-500/20 rounded-lg p-3">
        <div className="flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
          <div className="text-[10px] text-yellow-200/70 space-y-1">
            <div><span className="font-semibold">Delta:</span> Rate of change of option price (0-1 for calls, -1-0 for puts)</div>
            <div><span className="font-semibold">Gamma:</span> Rate of delta change, higher = more sensitive</div>
            <div><span className="font-semibold">Theta:</span> Time decay (negative = option loses value daily)</div>
            <div><span className="font-semibold">Vega:</span> IV sensitivity, positive = benefits from volatility increase</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GreeksPanel;
