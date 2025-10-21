"""
Состояния FSM (Finite State Machine) для диалогов бота
"""

from aiogram.fsm.state import State, StatesGroup


class AnalysisStates(StatesGroup):
    """Состояния для процесса анализа"""
    waiting_for_symbol = State()  # Ожидание ввода символа криптовалюты


class SubscriptionStates(StatesGroup):
    """Состояния для процесса оформления подписки"""
    choosing_plan = State()  # Выбор плана подписки
    waiting_for_payment = State()  # Ожидание оплаты
    confirming_payment = State()  # Подтверждение оплаты

