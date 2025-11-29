"""
Utility functions for JSON serialization and numpy type conversion.
Handles conversion of numpy types to native Python types for JSON compatibility.
"""

import numpy as np
from typing import Any


def convert_numpy_types(obj: Any) -> Any:
    """
    Recursively convert numpy types to native Python types.
    
    Args:
        obj: Object to convert (can be dict, list, or any value)
        
    Returns:
        Object with all numpy types converted to Python native types
    """
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, (np.bool_, np.bool)):
        return bool(obj)
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj
