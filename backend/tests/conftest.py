"""Shared fixtures for all tests."""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os


@pytest.fixture
def sample_ohlcv_df():
    """Generate a realistic OHLCV DataFrame for strategy testing."""
    np.random.seed(42)
    n = 100
    base_price = 24000
    returns = np.random.normal(0.0001, 0.005, n)
    prices = base_price * np.exp(np.cumsum(returns))

    df = pd.DataFrame({
        'open': prices * (1 + np.random.uniform(-0.002, 0.002, n)),
        'high': prices * (1 + np.abs(np.random.uniform(0, 0.01, n))),
        'low': prices * (1 - np.abs(np.random.uniform(0, 0.01, n))),
        'close': prices,
        'volume': np.random.randint(100000, 1000000, n),
    })
    df.index = pd.date_range('2025-01-01', periods=n, freq='5min')
    return df


@pytest.fixture
def small_ohlcv_df():
    """A small DataFrame with insufficient data for indicators."""
    return pd.DataFrame({
        'open': [100, 101],
        'high': [102, 103],
        'low': [99, 100],
        'close': [101, 102],
        'volume': [1000, 1100],
    })


@pytest.fixture
def tmp_json_file():
    """Provide a temporary JSON file path, cleaned up after test."""
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)
