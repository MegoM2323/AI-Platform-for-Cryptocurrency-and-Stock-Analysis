import asyncio
from pathlib import Path

import pytest

from database import Database
from telegram_bot.token_manager import TokenManager


@pytest.mark.asyncio
async def test_add_tokens_and_history(tmp_path: Path):
    db_path = tmp_path / "test_tokens.db"
    db = Database(db_path)
    await db.init_db()

    tm = TokenManager(db, initial_bonus=0)
    user_id = 111

    # Стартовый баланс 0
    assert await tm.get_balance(user_id) == 0

    # Начисление
    ok = await tm.add_tokens(user_id, amount=50, transaction_type="purchase", description="Тестовое начисление", payment_id="p-1")
    assert ok is True
    assert await tm.get_balance(user_id) == 50

    # История транзакций
    hist = await tm.get_transaction_history(user_id, limit=5)
    assert len(hist) == 1
    t = hist[0]
    assert t["amount"] == 50
    assert t["transaction_type"] == "purchase"
    assert t["balance_before"] == 0
    assert t["balance_after"] == 50
    assert t["payment_id"] == "p-1"


@pytest.mark.asyncio
async def test_deduct_tokens_and_prevent_negative(tmp_path: Path):
    db_path = tmp_path / "test_tokens.db"
    db = Database(db_path)
    await db.init_db()

    tm = TokenManager(db, initial_bonus=0)
    user_id = 222

    # Пополняем
    assert await tm.add_tokens(user_id, 10, "bonus", "Бонус") is True
    assert await tm.get_balance(user_id) == 10

    # Списание в пределах баланса
    assert await tm.deduct_tokens(user_id, 3, "basic_analysis", "Базовый анализ BTC") is True
    assert await tm.get_balance(user_id) == 7

    # Попытка уйти в отрицательный баланс
    assert await tm.deduct_tokens(user_id, 8, "enhanced_analysis", "Расширенный анализ BTC") is False
    assert await tm.get_balance(user_id) == 7


@pytest.mark.asyncio
async def test_atomicity_concurrent_deducts(tmp_path: Path):
    db_path = tmp_path / "test_tokens.db"
    db = Database(db_path)
    await db.init_db()

    tm = TokenManager(db, initial_bonus=0)
    user_id = 333

    # Баланс = 5
    assert await tm.add_tokens(user_id, 5, "bonus", "Бонус") is True
    assert await tm.get_balance(user_id) == 5

    async def deduct_three():
        return await tm.deduct_tokens(user_id, 3, "basic_analysis", "Базовый")

    # Два конкурентных списания по 3
    r1, r2 = await asyncio.gather(deduct_three(), deduct_three())

    # Ровно одно должно пройти (5 -> 2), второе — отклониться
    assert (r1, r2).count(True) == 1
    assert await tm.get_balance(user_id) == 2


