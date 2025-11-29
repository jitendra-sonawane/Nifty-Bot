import React, { useState } from 'react';
import { ChevronDown, ChevronUp, AlertCircle, Target, Shield, Zap } from 'lucide-react';

interface ReasoningProps {
  reasoning?: {
    timestamp?: string;
    signal?: string;
    action?: string;
    confidence?: number;
    key_factors?: string[];
    risk_factors?: string[];
    target_levels?: {
      primary?: number;
      extended?: number;
      reasoning?: string;
    };
    stop_loss_levels?: {
      primary?: number;
      reasoning?: string;
    };
    trade_rationale?: string;
    why_now?: string;
    filter_summary?: Record<string, string>;
  };
  currentPrice?: number;
}

const ReasoningCard: React.FC<ReasoningProps> = ({ reasoning = {}, currentPrice = 0 }) => {
  const [expandedSection, setExpandedSection] = useState<string | null>('overview');

  const {
    signal = 'HOLD',
    action = '⏸️ WAIT',
    confidence = 0,
    key_factors = [],
    risk_factors = [],
    target_levels = {},
    stop_loss_levels = {},
    trade_rationale = '',
    why_now = '',
    filter_summary = {},
    timestamp = new Date().toLocaleTimeString()
  } = reasoning;

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  const getActionColor = () => {
    if (signal === 'BUY_CE') return 'from-green-500/20 to-green-600/5 border-green-500/30';
    if (signal === 'BUY_PE') return 'from-red-500/20 to-red-600/5 border-red-500/30';
    return 'from-blue-500/20 to-blue-600/5 border-blue-500/30';
  };

  const getConfidenceColor = () => {
    if (confidence >= 80) return 'text-green-400';
    if (confidence >= 60) return 'text-yellow-400';
    if (confidence >= 40) return 'text-orange-400';
    return 'text-red-400';
  };

  const getConfidenceLabel = () => {
    if (confidence >= 80) return 'High';
    if (confidence >= 60) return 'Medium';
    if (confidence >= 40) return 'Low';
    return 'Very Low';
  };

  return (
    <div className="space-y-3">
      {/* HEADER */}
      <div className={`bg-gradient-to-r ${getActionColor()} rounded-lg border p-4`}>
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <div className="text-2xl font-bold text-white mb-1">{action}</div>
            <div className="text-xs text-gray-400">{timestamp}</div>
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-400 mb-1">Confidence</div>
            <div className={`text-2xl font-bold ${getConfidenceColor()}`}>{confidence.toFixed(0)}%</div>
            <div className="text-xs text-gray-500">{getConfidenceLabel()}</div>
          </div>
        </div>
        
        {/* Confidence Bar */}
        <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
          <div 
            className={`h-full rounded-full transition-all duration-500 ${
              confidence >= 80 ? 'bg-green-500' : 
              confidence >= 60 ? 'bg-yellow-500' : 
              confidence >= 40 ? 'bg-orange-500' : 'bg-red-500'
            }`}
            style={{ width: `${confidence}%` }}
          ></div>
        </div>
      </div>

      {/* FILTER STATUS */}
      {Object.keys(filter_summary).length > 0 && (
        <div className="bg-white/5 border border-white/10 rounded-lg p-3">
          <button
            onClick={() => toggleSection('filters')}
            className="w-full flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              <Zap size={16} className="text-cyan-400" />
              <span className="text-xs font-semibold text-white uppercase">Filter Status</span>
            </div>
            {expandedSection === 'filters' ? (
              <ChevronUp size={16} className="text-gray-500" />
            ) : (
              <ChevronDown size={16} className="text-gray-500" />
            )}
          </button>

          {expandedSection === 'filters' && (
            <div className="mt-3 grid grid-cols-2 gap-2">
              {Object.entries(filter_summary).map(([filterName, status]) => (
                <div key={filterName} className="bg-white/5 rounded p-2 border border-white/5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-300">{filterName}</span>
                    <span className={`text-sm font-bold ${status === '✅' ? 'text-green-400' : 'text-red-400'}`}>
                      {status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* KEY FACTORS */}
      {key_factors.length > 0 && (
        <div className="bg-white/5 border border-white/10 rounded-lg p-3">
          <button
            onClick={() => toggleSection('factors')}
            className="w-full flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              <AlertCircle size={16} className="text-yellow-400" />
              <span className="text-xs font-semibold text-white uppercase">Key Factors ({key_factors.length})</span>
            </div>
            {expandedSection === 'factors' ? (
              <ChevronUp size={16} className="text-gray-500" />
            ) : (
              <ChevronDown size={16} className="text-gray-500" />
            )}
          </button>

          {expandedSection === 'factors' && (
            <div className="mt-3 space-y-2">
              {key_factors.map((factor, idx) => (
                <div key={idx} className="bg-white/5 rounded p-2 border border-white/5">
                  <div className="text-xs text-gray-300 leading-relaxed">{factor}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TRADE RATIONALE */}
      {trade_rationale && (
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3">
          <button
            onClick={() => toggleSection('rationale')}
            className="w-full flex items-center justify-between"
          >
            <span className="text-xs font-semibold text-blue-300 uppercase">Why This Trade?</span>
            {expandedSection === 'rationale' ? (
              <ChevronUp size={16} className="text-blue-500" />
            ) : (
              <ChevronDown size={16} className="text-blue-500" />
            )}
          </button>

          {expandedSection === 'rationale' && (
            <div className="mt-2 text-xs text-gray-300 leading-relaxed bg-blue-500/5 rounded p-2">
              {trade_rationale}
            </div>
          )}
        </div>
      )}

      {/* WHY NOW */}
      {why_now && (
        <div className="bg-purple-500/10 border border-purple-500/20 rounded-lg p-3">
          <button
            onClick={() => toggleSection('timing')}
            className="w-full flex items-center justify-between"
          >
            <span className="text-xs font-semibold text-purple-300 uppercase">Why Now?</span>
            {expandedSection === 'timing' ? (
              <ChevronUp size={16} className="text-purple-500" />
            ) : (
              <ChevronDown size={16} className="text-purple-500" />
            )}
          </button>

          {expandedSection === 'timing' && (
            <div className="mt-2 text-xs text-gray-300 leading-relaxed bg-purple-500/5 rounded p-2">
              {why_now}
            </div>
          )}
        </div>
      )}

      {/* RISK FACTORS */}
      {risk_factors.length > 0 && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
          <button
            onClick={() => toggleSection('risks')}
            className="w-full flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              <Shield size={16} className="text-red-400" />
              <span className="text-xs font-semibold text-red-300 uppercase">Risk Factors ({risk_factors.length})</span>
            </div>
            {expandedSection === 'risks' ? (
              <ChevronUp size={16} className="text-gray-500" />
            ) : (
              <ChevronDown size={16} className="text-gray-500" />
            )}
          </button>

          {expandedSection === 'risks' && (
            <div className="mt-3 space-y-2">
              {risk_factors.map((risk, idx) => (
                <div key={idx} className="bg-red-500/5 rounded p-2 border border-red-500/10">
                  <div className="text-xs text-red-200 leading-relaxed">⚠️ {risk}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TARGET & STOP LOSS */}
      <div className="grid grid-cols-2 gap-3">
        {/* TARGET LEVELS */}
        {target_levels.primary && (
          <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <Target size={14} className="text-green-400" />
              <span className="text-xs text-green-300 font-semibold uppercase">Target</span>
            </div>
            <div className="text-lg font-bold text-green-300">
              ₹{(target_levels.primary as number).toFixed(2)}
            </div>
            <div className="text-xs text-green-200/60 mt-1">
              {target_levels.reasoning || 'Profit target'}
            </div>
            {currentPrice > 0 && (
              <div className="text-xs text-green-200/40 mt-1 font-mono">
                Upside: +{(((target_levels.primary as number) - currentPrice) / currentPrice * 100).toFixed(2)}%
              </div>
            )}
          </div>
        )}

        {/* STOP LOSS */}
        {stop_loss_levels.primary && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <Shield size={14} className="text-red-400" />
              <span className="text-xs text-red-300 font-semibold uppercase">Stop Loss</span>
            </div>
            <div className="text-lg font-bold text-red-300">
              ₹{(stop_loss_levels.primary as number).toFixed(2)}
            </div>
            <div className="text-xs text-red-200/60 mt-1">
              {stop_loss_levels.reasoning || 'Risk protection'}
            </div>
            {currentPrice > 0 && (
              <div className="text-xs text-red-200/40 mt-1 font-mono">
                Risk: -{(((currentPrice - (stop_loss_levels.primary as number)) / currentPrice) * 100).toFixed(2)}%
              </div>
            )}
          </div>
        )}
      </div>

      {/* NO DATA STATE */}
      {signal === 'HOLD' && !key_factors.length && (
        <div className="bg-white/5 border border-white/10 rounded-lg p-4 text-center">
          <div className="text-sm text-gray-400">
            ⏳ Waiting for clear market signals...
          </div>
          <div className="text-xs text-gray-500 mt-2">
            The bot is analyzing market conditions and waiting for all filters to align for a high-probability trade.
          </div>
        </div>
      )}
    </div>
  );
};

export default ReasoningCard;
