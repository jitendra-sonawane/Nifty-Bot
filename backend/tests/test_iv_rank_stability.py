import unittest
import time
from collections import deque
from unittest.mock import patch

import pytest

from app.intelligence.iv_rank import IVRankModule


class TestIVRankComputeOrder:

    def test_current_iv_excluded_from_range(self):
        """Current IV should NOT be in the history when computing rank.

        If we feed history [0.10, 0.20] and then current_iv=0.25,
        rank should be computed against range [0.10, 0.20] -> rank = 150%.
        If bug exists, current_iv is IN history -> range [0.10, 0.25] -> rank = 100%.
        """
        module = IVRankModule(history_size=100, history_interval=0)
        # Manually disable disk persistence for test
        module.save_state = lambda: None
        module.load_state = lambda: None
        module._history.clear()

        # Seed history with known range: low=0.10, high=0.20
        module._history.append(0.10)
        module._history.append(0.20)
        module._last_history_update_time = 0  # Force next append to succeed

        # Feed current IV = 0.25 (above historical range)
        with patch('time.time', return_value=1000.0):
            module.update({"iv": 0.25})

        ctx = module.get_context()
        iv_rank = ctx["iv_rank"]

        # Correct: rank = (0.25 - 0.10) / (0.20 - 0.10) * 100 = 150
        # Bug:     rank = (0.25 - 0.10) / (0.25 - 0.10) * 100 = 100
        assert iv_rank is not None
        assert iv_rank > 100, \
            f"IV Rank={iv_rank:.1f} -- current IV should exceed range (expect >100, got <=100)"

    def test_current_iv_at_new_low_gives_negative_rank(self):
        """When current IV is below all history, rank should be < 0."""
        module = IVRankModule(history_size=100, history_interval=0)
        module.save_state = lambda: None
        module.load_state = lambda: None
        module._history.clear()

        module._history.append(0.15)
        module._history.append(0.25)
        module._last_history_update_time = 0

        with patch('time.time', return_value=1000.0):
            module.update({"iv": 0.10})

        ctx = module.get_context()
        iv_rank = ctx["iv_rank"]

        # Correct: rank = (0.10 - 0.15) / (0.25 - 0.15) * 100 = -50
        assert iv_rank is not None
        assert iv_rank < 0, \
            f"IV Rank={iv_rank:.1f} -- below all history should give negative rank"

class TestIVRankStability(unittest.TestCase):
    def setUp(self):
        # Use a short interval for testing (e.g., 0.1 seconds)
        self.history_interval = 0.1
        self.iv_module = IVRankModule(history_size=10, history_interval=self.history_interval)
        # Patch warmup interval for testing
        self.iv_module.WARMUP_INTERVAL = 0.1
        
        # Clear any loaded history and mock file path to prevent real disk I/O
        self.iv_module._history.clear()
        self.iv_module._get_file_path = lambda: None

    def test_throttling(self):
        """Test that history is not updated on every call within the interval."""
        
        # Initial update
        self.iv_module.update({"iv": 0.20, "expiry": "2024-12-26"})
        context = self.iv_module.get_context()
        self.assertEqual(context["history_size"], 1)
        self.assertEqual(context["current_iv"], 20.0)

        # Immediate follow-up update (should be ignored for history, but update current)
        self.iv_module.update({"iv": 0.21, "expiry": "2024-12-26"})
        context = self.iv_module.get_context()
        self.assertEqual(context["history_size"], 1, "History size should not increase immediately")
        self.assertEqual(context["current_iv"], 21.0, "Current IV should update immediately")

        # Wait for interval to pass
        time.sleep(self.history_interval + 0.05)

        # Update after interval
        self.iv_module.update({"iv": 0.22, "expiry": "2024-12-26"})
        context = self.iv_module.get_context()
        self.assertEqual(context["history_size"], 2, "History size should increase after interval")
        self.assertEqual(context["current_iv"], 22.0)

    def test_rank_not_computed_with_single_history_point(self):
        """Test that IV rank is None with only 1 history point (need at least 2)."""
        self.iv_module.update({"iv": 0.20})
        context = self.iv_module.get_context()
        self.assertIsNone(context["iv_rank"])
        self.assertEqual(context["history_size"], 1)

    def test_rank_calculation_with_two_history_points(self):
        """Test IV rank calculation with 2 history points.

        With compute-before-append, rank is computed against history that
        existed BEFORE the current update appends. So we need at least 2
        points already in history for rank to be computed.
        """
        # Seed history directly with 2 points
        self.iv_module._history.append(0.20)
        self.iv_module._history.append(0.30)

        # Now update with current IV = 0.25
        # History is [0.20, 0.30]. Rank = (0.25 - 0.20) / (0.30 - 0.20) = 50%
        self.iv_module.update({"iv": 0.25})
        context = self.iv_module.get_context()
        self.assertEqual(context["iv_rank"], 50.0)

        # Immediate update (no history change): Current 0.30
        # History is [0.20, 0.30, 0.25]. Rank = (0.30 - 0.20) / (0.30 - 0.20) = 100%
        self.iv_module.update({"iv": 0.30})
        context = self.iv_module.get_context()
        self.assertEqual(context["iv_rank"], 100.0)

    def test_rank_can_exceed_100(self):
        """Test that IV rank can go above 100 when current IV exceeds historical high."""
        self.iv_module.update({"iv": 0.20})
        time.sleep(self.history_interval + 0.01)
        self.iv_module.update({"iv": 0.30})

        # Now current IV goes beyond historical high
        self.iv_module.update({"iv": 0.35})
        context = self.iv_module.get_context()
        # Rank = (0.35-0.20)/(0.30-0.20) = 150%
        self.assertEqual(context["iv_rank"], 150.0)

    def test_percentile_uses_strict_less_than(self):
        """Test that IV percentile counts values strictly below current IV."""
        # Seed history directly with 2 identical points
        self.iv_module._history.append(0.20)
        self.iv_module._history.append(0.20)

        # Update with current IV = 0.20
        # History is [0.20, 0.20]. Strict less-than: 0 values below 0.20 -> percentile = 0%
        self.iv_module.update({"iv": 0.20})
        context = self.iv_module.get_context()
        self.assertEqual(context["iv_percentile"], 0.0)

    def test_rapid_updates_spam(self):
        """Simulate market data spam (100 updates in < interval)."""
        current_iv = 0.10
        for _ in range(100):
            current_iv += 0.0001
            self.iv_module.update({"iv": current_iv})
        
        # Should still be 1 history entry (the first one, or the one when interval ticked? 
        # logic: if now - last > interval. First call: last=0, so update. Set last=now.
        # Next 99 calls: now - last < interval. No update.
        # So history size = 1.
        context = self.iv_module.get_context()
        self.assertEqual(context["history_size"], 1)

    def test_persistence(self):
        """Test that history is saved and loaded from disk."""
        import tempfile
        import os
        from pathlib import Path
        
        # Create a temp file for testing
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            # 1. Initialize module with mocked path
            module1 = IVRankModule(history_size=10, history_interval=0.1)
            module1._history.clear() # Clear any real data loaded during init
            module1.WARMUP_INTERVAL = 0.1
            module1._get_file_path = lambda: tmp_path
            
            # 2. Add some history
            module1.update({"iv": 0.20})
            time.sleep(0.15)
            module1.update({"iv": 0.25}) # Should save here
            
            # Debug print
            # print(f"History size: {len(module1._history)}")
            
            self.assertEqual(len(module1._history), 2)
            
            # 3. Initialize NEW module (simulating restart)
            module2 = IVRankModule(history_size=10, history_interval=0.1)
            module2._history.clear() # Clear any real data loaded during init
            # No need to patch interval for module2 as we just load state
            module2._get_file_path = lambda: tmp_path
            module2.load_state() # Manually load from tmp path
            
            # 4. Verify history is restored
            self.assertEqual(len(module2._history), 2)
            self.assertEqual(list(module2._history), [0.20, 0.25])
            
        finally:
            if tmp_path.exists():
                os.unlink(tmp_path)

if __name__ == '__main__':
    unittest.main()
