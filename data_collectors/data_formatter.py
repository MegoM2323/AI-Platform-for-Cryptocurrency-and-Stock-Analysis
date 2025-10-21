"""
Форматирование данных для анализа AI
"""

import pandas as pd
from typing import Dict, Optional
from datetime import datetime


class DataFormatter:
    """Класс для форматирования данных криптовалют"""
    
    @staticmethod
    def format_for_analysis(data: pd.DataFrame, symbol: str, 
                           current_price: Optional[float] = None) -> str:
        """
        Форматировать данные для отправки в AI
        
        Args:
            data: DataFrame с историческими данными
            symbol: Символ криптовалюты
            current_price: Текущая цена (опционально)
            
        Returns:
            Отформатированная строка с данными
        """
        if data is None or data.empty:
            return f"Нет данных для {symbol}"
        
        # Базовая статистика
        latest = data.iloc[-1]
        oldest = data.iloc[0]
        
        # Расчет изменений
        price_change = latest['close'] - oldest['close']
        price_change_pct = (price_change / oldest['close']) * 100
        
        # Статистика за период
        high = data['high'].max()
        low = data['low'].min()
        avg_volume = data['volume'].mean() if 'volume' in data.columns else 0
        
        # Последние 7 дней
        last_7_days = data.tail(7)
        recent_trend = DataFormatter._calculate_trend(last_7_days)
        
        # Формируем текст
        text = f"""
Анализ криптовалюты: {symbol}

ТЕКУЩИЕ ДАННЫЕ:
{'Текущая цена: $' + f'{current_price:.2f}' if current_price else ''}
Последняя зафиксированная цена: ${latest['close']:.2f}
Дата: {latest.name.strftime('%Y-%m-%d') if hasattr(latest.name, 'strftime') else 'N/A'}

СТАТИСТИКА ЗА ПЕРИОД ({len(data)} дней):
Начальная цена: ${oldest['close']:.2f}
Изменение: ${price_change:.2f} ({price_change_pct:+.2f}%)
Максимум: ${high:.2f}
Минимум: ${low:.2f}
Средний объем: {avg_volume:,.0f}

ПОСЛЕДНИЕ 7 ДНЕЙ:
Тренд: {recent_trend}
Открытие: ${last_7_days.iloc[0]['open']:.2f}
Закрытие: ${last_7_days.iloc[-1]['close']:.2f}
Изменение: {DataFormatter._calculate_change_pct(last_7_days.iloc[0]['open'], last_7_days.iloc[-1]['close']):+.2f}%

ДЕТАЛЬНАЯ ИСТОРИЯ (последние 10 дней):
{DataFormatter._format_history_table(data.tail(10))}

ТЕХНИЧЕСКИЕ ИНДИКАТОРЫ:
{DataFormatter._calculate_indicators(data)}
"""
        return text.strip()
    
    @staticmethod
    def _calculate_trend(data: pd.DataFrame) -> str:
        """Определить тренд"""
        if data.empty or len(data) < 2:
            return "Недостаточно данных"
        
        first_price = data.iloc[0]['close']
        last_price = data.iloc[-1]['close']
        change_pct = ((last_price - first_price) / first_price) * 100
        
        if change_pct > 5:
            return f"Восходящий (+{change_pct:.2f}%)"
        elif change_pct < -5:
            return f"Нисходящий ({change_pct:.2f}%)"
        else:
            return f"Боковой ({change_pct:+.2f}%)"
    
    @staticmethod
    def _calculate_change_pct(old_price: float, new_price: float) -> float:
        """Рассчитать процентное изменение"""
        if old_price == 0:
            return 0.0
        return ((new_price - old_price) / old_price) * 100
    
    @staticmethod
    def _format_history_table(data: pd.DataFrame) -> str:
        """Форматировать таблицу истории"""
        lines = []
        lines.append("Дата       | Открытие  | Максимум  | Минимум   | Закрытие  | Объем")
        lines.append("-" * 75)
        
        for idx, row in data.iterrows():
            date_str = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)[:10]
            lines.append(
                f"{date_str} | "
                f"${row['open']:8.2f} | "
                f"${row['high']:8.2f} | "
                f"${row['low']:8.2f} | "
                f"${row['close']:8.2f} | "
                f"{row.get('volume', 0):>10,.0f}"
            )
        
        return "\n".join(lines)
    
    @staticmethod
    def _calculate_indicators(data: pd.DataFrame) -> str:
        """Рассчитать технические индикаторы"""
        if data.empty or len(data) < 20:
            return "Недостаточно данных для расчета индикаторов"
        
        indicators = []
        
        # Простая скользящая средняя (SMA)
        sma_20 = data['close'].tail(20).mean()
        current_price = data['close'].iloc[-1]
        sma_position = "выше" if current_price > sma_20 else "ниже"
        indicators.append(f"SMA(20): ${sma_20:.2f} (цена {sma_position} SMA)")
        
        # Волатильность (стандартное отклонение)
        volatility = data['close'].tail(20).std()
        volatility_pct = (volatility / current_price) * 100
        indicators.append(f"Волатильность (20д): {volatility_pct:.2f}%")
        
        # RSI упрощенный
        price_changes = data['close'].diff().tail(14)
        gains = price_changes[price_changes > 0].mean()
        losses = abs(price_changes[price_changes < 0].mean())
        
        if losses != 0:
            rs = gains / losses
            rsi = 100 - (100 / (1 + rs))
            rsi_signal = "перекуплен" if rsi > 70 else "перепродан" if rsi < 30 else "нейтрален"
            indicators.append(f"RSI(14): {rsi:.2f} ({rsi_signal})")
        
        return "\n".join(indicators)
    
    @staticmethod
    def format_short_summary(symbol: str, current_price: float, 
                            price_change_pct: float) -> str:
        """
        Короткое резюме для быстрого ответа
        
        Args:
            symbol: Символ криптовалюты
            current_price: Текущая цена
            price_change_pct: Изменение в процентах
            
        Returns:
            Короткая строка с резюме
        """
        trend_emoji = "📈" if price_change_pct > 0 else "📉"
        return (
            f"{trend_emoji} {symbol}: ${current_price:.2f} "
            f"({price_change_pct:+.2f}% за период)"
        )

