import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from data_collectors.rate_limiter import RateLimiter


def test_rate_limiter_basic_quota():
    rl = RateLimiter(monthly_limit=5, daily_limit=3, reserved_user_percent=20)
    # 3 дневных запроса допустимы
    assert rl.can_make_request() is True
    rl.record_request('BTC')
    rl.record_request('BTC')
    assert rl.can_make_request() is True
    rl.record_request('ETH')
    # Дневной лимит исчерпан
    assert rl.can_make_request() is False


def test_rate_limiter_priority():
    rl = RateLimiter(monthly_limit=10, daily_limit=10, reserved_user_percent=20)
    assert rl.get_priority_score('BTC') == 0
    rl.record_request('BTC')
    rl.record_request('BTC')
    assert rl.get_priority_score('BTC') == 2


