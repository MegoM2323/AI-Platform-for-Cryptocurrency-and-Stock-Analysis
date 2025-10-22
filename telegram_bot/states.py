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


class PurchaseStates(StatesGroup):
    """Состояния для процесса покупки"""
    selecting_purchase_type = State()  # Выбор типа покупки (подписка/анализы)
    selecting_subscription_plan = State()  # Выбор плана подписки
    selecting_analysis_package = State()  # Выбор пакета анализов
    selecting_payment_method = State()  # Выбор способа оплаты
    processing_payment = State()  # Обработка платежа

