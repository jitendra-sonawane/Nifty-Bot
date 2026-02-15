"""Tests for JSON utility functions."""

import pytest
import numpy as np
from app.utils.json_utils import convert_numpy_types


class TestConvertNumpyTypes:

    def test_int64(self):
        assert convert_numpy_types(np.int64(42)) == 42
        assert isinstance(convert_numpy_types(np.int64(42)), int)

    def test_int32(self):
        assert convert_numpy_types(np.int32(10)) == 10
        assert isinstance(convert_numpy_types(np.int32(10)), int)

    def test_float64(self):
        result = convert_numpy_types(np.float64(3.14))
        assert result == 3.14
        assert isinstance(result, float)

    def test_float32(self):
        result = convert_numpy_types(np.float32(2.5))
        assert isinstance(result, float)

    def test_bool_(self):
        assert convert_numpy_types(np.bool_(True)) is True
        assert isinstance(convert_numpy_types(np.bool_(True)), bool)

    def test_ndarray(self):
        arr = np.array([1, 2, 3])
        result = convert_numpy_types(arr)
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_dict_recursive(self):
        data = {'a': np.int64(1), 'b': np.float64(2.5), 'c': 'hello'}
        result = convert_numpy_types(data)
        assert result == {'a': 1, 'b': 2.5, 'c': 'hello'}
        assert isinstance(result['a'], int)
        assert isinstance(result['b'], float)

    def test_list_recursive(self):
        data = [np.int64(1), np.float64(2.5), 'hello']
        result = convert_numpy_types(data)
        assert result == [1, 2.5, 'hello']

    def test_nested_dict_in_list(self):
        data = [{'val': np.int64(42)}]
        result = convert_numpy_types(data)
        assert result == [{'val': 42}]

    def test_plain_python_types_unchanged(self):
        assert convert_numpy_types(42) == 42
        assert convert_numpy_types(3.14) == 3.14
        assert convert_numpy_types("hello") == "hello"
        assert convert_numpy_types(None) is None
        assert convert_numpy_types(True) is True

    def test_2d_ndarray(self):
        arr = np.array([[1, 2], [3, 4]])
        result = convert_numpy_types(arr)
        assert result == [[1, 2], [3, 4]]
