"""Tests for performance metrics — pure Python fallback path."""

import math

import numpy as np
import pytest


class TestMaxDrawdown:
    def test_empty_array(self):
        from rust_accelerators.metrics import calculate_max_drawdown

        dd, dd_pct = calculate_max_drawdown(np.array([], dtype=np.float64))
        assert dd == 0.0
        assert dd_pct == 0.0

    def test_monotonically_increasing(self):
        from rust_accelerators.metrics import calculate_max_drawdown

        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        dd, dd_pct = calculate_max_drawdown(data)
        assert dd == 0.0
        assert dd_pct == 0.0

    def test_known_drawdown(self):
        from rust_accelerators.metrics import calculate_max_drawdown

        # Peak at 100, drops to 80, then recovers
        data = np.array([50.0, 100.0, 80.0, 90.0, 95.0])
        dd, dd_pct = calculate_max_drawdown(data)
        assert dd == pytest.approx(20.0)
        assert dd_pct == pytest.approx(0.2)

    def test_single_element(self):
        from rust_accelerators.metrics import calculate_max_drawdown

        dd, dd_pct = calculate_max_drawdown(np.array([42.0]))
        assert dd == 0.0
        assert dd_pct == 0.0


class TestSharpeRatio:
    def test_empty_array(self):
        from rust_accelerators.metrics import calculate_sharpe_ratio

        assert calculate_sharpe_ratio(np.array([], dtype=np.float64)) == 0.0

    def test_single_element(self):
        from rust_accelerators.metrics import calculate_sharpe_ratio

        assert calculate_sharpe_ratio(np.array([1.0])) == 0.0

    def test_zero_std(self):
        from rust_accelerators.metrics import calculate_sharpe_ratio

        assert calculate_sharpe_ratio(np.array([1.0, 1.0, 1.0])) == 0.0

    def test_known_sharpe(self):
        from rust_accelerators.metrics import calculate_sharpe_ratio

        # Deterministic data with known mean/std
        rng = np.random.default_rng(42)
        returns = rng.normal(0.001, 0.02, 252)
        sharpe = calculate_sharpe_ratio(returns, periods_per_year=252)
        # Should be roughly mean/std * sqrt(252), non-zero
        assert sharpe != 0.0


class TestProfitFactor:
    def test_all_wins(self):
        from rust_accelerators.metrics import calculate_profit_factor

        pf = calculate_profit_factor(np.array([1.0, 2.0, 3.0]))
        assert pf == float("inf")

    def test_all_losses(self):
        from rust_accelerators.metrics import calculate_profit_factor

        pf = calculate_profit_factor(np.array([-1.0, -2.0, -3.0]))
        assert pf == 0.0

    def test_known_factor(self):
        from rust_accelerators.metrics import calculate_profit_factor

        # 6 profit, 3 loss → PF = 2.0
        pf = calculate_profit_factor(np.array([1.0, 2.0, 3.0, -1.0, -2.0]))
        assert pf == pytest.approx(2.0)

    def test_empty(self):
        from rust_accelerators.metrics import calculate_profit_factor

        pf = calculate_profit_factor(np.array([], dtype=np.float64))
        assert math.isinf(pf)


class TestAllMetrics:
    def test_returns_four_values(self):
        from rust_accelerators.metrics import calculate_all_metrics

        data = np.array([50.0, 100.0, 80.0, 90.0, 95.0])
        result = calculate_all_metrics(data)
        assert len(result) == 4
        max_dd, max_dd_pct, sharpe, pf = result
        assert max_dd == pytest.approx(20.0)
        assert max_dd_pct == pytest.approx(0.2)

    def test_empty(self):
        from rust_accelerators.metrics import calculate_all_metrics

        result = calculate_all_metrics(np.array([], dtype=np.float64))
        assert result == (0.0, 0.0, 0.0, 0.0)


class TestAcceleration:
    def test_is_accelerated_returns_bool(self):
        from rust_accelerators.metrics import is_accelerated

        assert isinstance(is_accelerated(), bool)
