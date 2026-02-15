import React from 'react';
import IntelligencePanel from '../features/intelligence/IntelligencePanel';
import DecisionTrace from '../features/intelligence/DecisionTrace';
import ReasoningPanel from '../features/signals/ReasoningPanel';
import SetupPipeline from '../features/signals/SetupPipeline';
import StrategyMatcher from '../features/signals/StrategyMatcher';
import type { IntelligenceContext, FilterData } from '../types/api';

interface IntelligenceTabContentProps {
    intelligence?: IntelligenceContext;
    onToggleModule: (module: string, enabled: boolean) => void;
    filters?: FilterData;
    reasoning?: any;
    signal?: string;
    currentPrice: number;
    strategyData?: any;
    pcr?: any;
    greeks?: any;
}

const IntelligenceTabContent: React.FC<IntelligenceTabContentProps> = React.memo((props) => (
    <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
        <IntelligencePanel
            intelligence={props.intelligence}
            onToggleModule={props.onToggleModule}
        />
        <DecisionTrace
            intelligence={props.intelligence}
            filters={props.filters}
            reasoning={props.reasoning}
            signal={props.signal}
            pcr={props.pcr}
            greeks={props.greeks}
        />
        <div className="space-y-3 lg:col-span-2 xl:col-span-1">
            <ReasoningPanel reasoning={props.reasoning} currentPrice={props.currentPrice} />
            <SetupPipeline strategyData={props.strategyData} signal={props.signal} />
            <StrategyMatcher strategyData={props.strategyData} signal={props.signal} />
        </div>
    </div>
));

IntelligenceTabContent.displayName = 'IntelligenceTabContent';
export default IntelligenceTabContent;
