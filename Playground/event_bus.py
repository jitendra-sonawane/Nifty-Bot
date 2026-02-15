import asyncio
from typing import Dict, Any,Callable   
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class ExceptionMode(Enum):
    SEQENTIAL = "sequential"
    PARALLEL = "parallel"
    STAGE="stage"  # sequence of both order and parallel 

@dataclass
class MarketEvent:
    event_type:str
    data:dict
    timestamp:datetime =None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class CallbackHandler:
    callback: Callable
    mode: ExceptionMode
    stage: int = 0

class AsyncEventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[CallbackHandler]] = {}

    def subscribe(self, event_type:str,callback:Callable, mode :ExceptionMode=ExceptionMode.SEQENTIAL, stage :int=0):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []

        handler = CallbackHandler(callback,mode,stage)
        self.subscribers[event_type].append(handler)

    async def publish(self,event:MarketEvent):
        if event.event_type not in self.subscribers:
            return
        handlers = self.subscribers[event.event_type]

        sequential = [h for h in handlers if h.mode == ExceptionMode.SEQENTIAL]
        parallel = [h for h in handlers if h.mode == ExceptionMode.PARALLEL]
        stage = [h for h in handlers if h.mode == ExceptionMode.STAGE]

        for handler in sequential:
            try:
                await self._execute_callback(handler.callback,event)
            except Exception as e:
                print(f"Error executing callback: {e}")

        if parallel:
            tasks = [self._execute_callback(h.callback,event) for h in parallel]
            try:
                await asyncio.gather(*tasks)
            except Exception as e:
                print(f"Error executing parallel callbacks: {e}")

        if stage:
            stages = {}
            for handler in stage:
                if handler.stage not in stages:
                    stages[handler.stage]=[]
                stages[handler.stage].append(handler)
            
            for stage_num in sorted(stages.keys()):
                tasks = [self._execute_callback(h.callback,event) for h in stages[stage_num]]
                try:
                    await asyncio.gather(*tasks)
                except Exception as e:
                    print(f"Error executing stage {stage_num} callbacks: {e}")



    async def _execute_callback(self, callback:Callable,event :MarketEvent):
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(event)
            else:
                callback(event)
        except Exception as e:
            print(f"Error executing callback: {e}")
            
event_bus = AsyncEventBus()

async def calculate_atm_strike(event:MarketEvent):
    print(f"Calculating ATM strike for {event.data['symbol']}")
    await asyncio.sleep(1)
    print("RSI: 65.2")
    

async def check_trend(event: MarketEvent):
    print("🎯 Checking trend...")
    await asyncio.sleep(0.5)
    print("   Trend: Bearish ✓")

# STAGE 2: Risk check (sequential - must run one by one)
async def check_position_size(event: MarketEvent):
    print("⚠️  Checking position size...")
    await asyncio.sleep(0.5)
    print("   Position: Valid ✓")

async def check_stop_loss(event: MarketEvent):
    print("⚠️  Checking stop loss...")
    await asyncio.sleep(0.5)
    print("   Stop Loss: 18200 ✓")


if __name__ == "__main__":
    event_bus.subscribe("calculate_atm_strike",calculate_atm_strike,ExceptionMode.STAGE,stage=0)
    event_bus.subscribe("check_trend",check_trend,ExceptionMode.STAGE,stage=1)
    event_bus.subscribe("check_position_size",check_position_size,ExceptionMode.STAGE,stage=2)
    event_bus.subscribe("check_stop_loss",check_stop_loss,ExceptionMode.STAGE,stage=3)

    async def main():
        await event_bus.publish(MarketEvent(event_type="calculate_atm_strike",data={"symbol":"NIFTY"}))
        
    asyncio.run(main())     