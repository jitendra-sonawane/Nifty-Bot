import React from 'react';
import { TrendingUp, TrendingDown, AlertCircle, Target } from 'lucide-react';

interface SupportResistanceData {
  support_levels?: number[];
  resistance_levels?: number[];
  nearest_support?: number | null;
  nearest_resistance?: number | null;
  support_distance_pct?: number | null;
  resistance_distance_pct?: number | null;
  current_price?: number;
}

interface BreakoutData {
  is_breakout?: boolean;
  breakout_type?: 'UPSIDE' | 'DOWNSIDE' | null;
  breakout_level?: number | null;
  strength?: number;
}

interface SupportResistanceProps {
  supportResistance?: SupportResistanceData;
  breakout?: BreakoutData;
  currentPrice?: number;
}

const SupportResistance: React.FC<SupportResistanceProps> = ({
  supportResistance,
  breakout,
  currentPrice
}) => {
  const {
    support_levels = [],
    resistance_levels = [],
    nearest_support,
    nearest_resistance,
    support_distance_pct,
    resistance_distance_pct,
    current_price = 0
  } = supportResistance || {};

  const displayPrice = currentPrice || current_price || 0;
  const liveSupportDist = nearest_support && displayPrice > 0
    ? ((displayPrice - nearest_support) / displayPrice) * 100
    : support_distance_pct;
  const liveResistanceDist = nearest_resistance && displayPrice > 0
    ? ((nearest_resistance - displayPrice) / displayPrice) * 100
    : resistance_distance_pct;

  const {
    is_breakout = false,
    breakout_type = null,
    breakout_level = null,
    strength = 0
  } = breakout || {};

  return (
    <div className="space-y-3">
      {/* Current Price Header */}
      <div className="bg-gradient-to-r from-slate-700/30 to-slate-600/30 border border-slate-500/30 rounded-lg p-3">
        <div className="text-xs text-slate-400 mb-1">Current Price</div>
        <div className="text-lg font-bold text-white">
          ₹{displayPrice?.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
        </div>
      </div>

      {/* Breakout Alert */}
      {is_breakout && (
        <div className={`border-l-4 rounded p-3 flex items-start gap-2 ${
          breakout_type === 'UPSIDE'
            ? 'bg-green-500/10 border-green-500 text-green-300'
            : 'bg-red-500/10 border-red-500 text-red-300'
        }`}>
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div className="text-xs">
            <div className="font-semibold">
              🔥 {breakout_type === 'UPSIDE' ? 'UPSIDE' : 'DOWNSIDE'} BREAKOUT
            </div>
            <div className="text-xs opacity-90">
              Level: ₹{breakout_level?.toFixed(2)} | Strength: {strength?.toFixed(2)}%
            </div>
          </div>
        </div>
      )}

      {/* Resistance Section */}
      <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
        <div className="flex items-center gap-2 mb-2">
          <TrendingDown className="w-4 h-4 text-red-400" />
          <div className="text-xs font-semibold text-red-300">RESISTANCE</div>
        </div>
        
        {nearest_resistance && (
          <div className="bg-red-500/10 rounded p-2 mb-2">
            <div className="text-xs text-red-200">Nearest</div>
            <div className="flex items-baseline justify-between">
              <div className="text-sm font-bold text-red-300">
                ₹{nearest_resistance?.toFixed(2)}
              </div>
              <div className="text-xs text-red-200/70">
                +{liveResistanceDist?.toFixed(2)}%
              </div>
            </div>
          </div>
        )}

        {resistance_levels.length > 0 && (
          <div className="space-y-1">
            <div className="text-xs text-red-200/60">Other levels:</div>
            {resistance_levels.slice(0, 2).map((level, idx) => (
              <div key={idx} className="flex justify-between text-xs text-red-200/50">
                <span>R{idx + 1}</span>
                <span>₹{level.toFixed(2)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Support Section */}
      <div className="bg-green-500/5 border border-green-500/20 rounded-lg p-3">
        <div className="flex items-center gap-2 mb-2">
          <TrendingUp className="w-4 h-4 text-green-400" />
          <div className="text-xs font-semibold text-green-300">SUPPORT</div>
        </div>
        
        {nearest_support && (
          <div className="bg-green-500/10 rounded p-2 mb-2">
            <div className="text-xs text-green-200">Nearest</div>
            <div className="flex items-baseline justify-between">
              <div className="text-sm font-bold text-green-300">
                ₹{nearest_support?.toFixed(2)}
              </div>
              <div className="text-xs text-green-200/70">
                -{liveSupportDist?.toFixed(2)}%
              </div>
            </div>
          </div>
        )}

        {support_levels.length > 0 && (
          <div className="space-y-1">
            <div className="text-xs text-green-200/60">Other levels:</div>
            {support_levels.slice(0, 2).map((level, idx) => (
              <div key={idx} className="flex justify-between text-xs text-green-200/50">
                <span>S{idx + 1}</span>
                <span>₹{level.toFixed(2)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Target Zone */}
      {nearest_support && nearest_resistance && (
        <div className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-blue-400" />
            <div className="text-xs font-semibold text-blue-300">TARGET ZONE</div>
          </div>
          <div className="bg-blue-500/10 rounded p-2">
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <div className="text-blue-200/60">Support</div>
                <div className="font-bold text-blue-300">₹{nearest_support?.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-blue-200/60">Resistance</div>
                <div className="font-bold text-blue-300">₹{nearest_resistance?.toFixed(2)}</div>
              </div>
            </div>
            <div className="text-xs text-blue-200/60 mt-1">
              Range: ₹{(nearest_resistance! - nearest_support!).toFixed(2)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SupportResistance;
