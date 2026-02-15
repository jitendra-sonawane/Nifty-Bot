import sys
import os

# Add current directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from position_manager import Position

def test_trailing_stop():
    print("🧪 Testing Trailing Stop Logic...")
    
    # Initialize position: Entry 100, Target 150, SL 70
    # Trailing Activation: 10% (Price 110), Trail: 5%
    pos = Position(
        instrument_key="TEST",
        entry_price=100.0,
        quantity=1,
        position_type="CE",
        stop_loss_pct=0.30,
        target_multiplier=1.5,
        trailing_activation_pct=10.0,
        trailing_pct=5.0
    )
    
    print(f"Initial State: Entry={pos.entry_price}, SL={pos.stop_loss}, Target={pos.target}")
    
    # 1. Price moves up but not enough to activate (105)
    pos.update_trailing_stop(105.0)
    print(f"Price 105: Activated={pos.trailing_sl_activated}, TrailingSL={pos.trailing_sl}")
    assert not pos.trailing_sl_activated
    
    # 2. Price hits activation (110) -> 10% gain
    pos.update_trailing_stop(110.0)
    # Expect activation. Trail should be max(100, 110 * 0.95 = 104.5) -> 104.5
    print(f"Price 110: Activated={pos.trailing_sl_activated}, TrailingSL={pos.trailing_sl}")
    assert pos.trailing_sl_activated
    assert pos.trailing_sl == 104.5
    
    # 3. Price moves up to 120
    pos.update_trailing_stop(120.0)
    # New trail: 120 * 0.95 = 114.0
    print(f"Price 120: Activated={pos.trailing_sl_activated}, TrailingSL={pos.trailing_sl}")
    assert pos.trailing_sl == 114.0
    
    # 4. Price drops to 115 (should not lower SL)
    pos.update_trailing_stop(115.0)
    print(f"Price 115: Activated={pos.trailing_sl_activated}, TrailingSL={pos.trailing_sl}")
    assert pos.trailing_sl == 114.0
    
    print("✅ All tests passed!")

if __name__ == "__main__":
    test_trailing_stop()
