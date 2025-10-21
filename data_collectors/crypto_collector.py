"""
Сбор данных о криптовалютах через Twelve Data API
"""

from twelvedata import TDClient
from typing import Optional, Dict
import pandas as pd
from datetime import datetime, timedelta
import os
import numpy as np


class CryptoCollector:
    """Класс для сбора данных о криптовалютах через Twelve Data API"""
    
    def __init__(self, api_key: str = None, timeframe: str = '1day', period: str = '30'):
        """
        Инициализация коллектора
        
        Args:
            api_key: API ключ для Twelve Data (если не указан, берется из переменных окружения)
            timeframe: Таймфрейм данных (по умолчанию '1day' - 1 день)
            period: Количество периодов истории (по умолчанию '30' - 30 дней)
        """
        self.api_key = api_key or os.getenv('TWELVE_DATA_API_KEY')
        self.timeframe = timeframe
        self.period = int(period)
        
        # Инициализируем клиент только если не в mock режиме
        if not os.getenv('DEBUG_USE_MOCK_DATA', 'false').lower() in ('true', '1', 'yes', 'on'):
            if not self.api_key:
                raise ValueError("TWELVE_DATA_API_KEY не найден. Укажите API ключ или установите переменную окружения.")
            self.td_client = TDClient(apikey=self.api_key)
        else:
            self.td_client = None
    
    def get_crypto_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Получить исторические данные о криптовалюте
        
        Args:
            symbol: Символ криптовалюты (например, 'BTC', 'ETH')
            
        Returns:
            DataFrame с данными или None в случае ошибки
        """
        # Проверяем, используется ли mock режим
        if os.getenv('DEBUG_USE_MOCK_DATA', 'false').lower() in ('true', '1', 'yes', 'on'):
            return self._generate_mock_data(symbol)
        
        try:
            # Формируем тикер для Twelve Data (добавляем /USD для криптовалют)
            ticker_symbol = self._format_ticker(symbol)
            
            # Получаем данные
            ts = self.td_client.time_series(
                symbol=ticker_symbol,
                interval=self.timeframe,
                outputsize=self.period
            )
            
            df = ts.as_pandas()
            
            if df.empty:
                return None
            
            return df
            
        except Exception as e:
            print(f"Ошибка при получении данных для {symbol}: {e}")
            return None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Получить текущую цену криптовалюты
        
        Args:
            symbol: Символ криптовалюты
            
        Returns:
            Текущая цена или None
        """
        # Проверяем, используется ли mock режим
        if os.getenv('DEBUG_USE_MOCK_DATA', 'false').lower() in ('true', '1', 'yes', 'on'):
            mock_data = self._generate_mock_data(symbol)
            if not mock_data.empty:
                return float(mock_data['close'].iloc[-1])
            return None
        
        try:
            ticker_symbol = self._format_ticker(symbol)
            
            # Получаем последнюю цену
            ts = self.td_client.time_series(
                symbol=ticker_symbol,
                interval='1min',
                outputsize=1
            )
            
            df = ts.as_pandas()
            if not df.empty:
                return float(df['close'].iloc[-1])
            
            return None
            
        except Exception as e:
            print(f"Ошибка при получении цены для {symbol}: {e}")
            return None
    
    def get_crypto_info(self, symbol: str) -> Optional[Dict]:
        """
        Получить дополнительную информацию о криптовалюте
        
        Args:
            symbol: Символ криптовалюты
            
        Returns:
            Словарь с информацией или None
        """
        try:
            ticker_symbol = self._format_ticker(symbol)
            
            # Получаем информацию через quote endpoint
            quote = self.td_client.custom_endpoint(
                name="quote",
                symbol=ticker_symbol
            )
            
            quote_data = quote.as_json()
            
            if 'status' in quote_data and quote_data['status'] == 'error':
                return None
            
            # Извлекаем нужные данные
            result = {
                'symbol': symbol,
                'name': quote_data.get('name', symbol),
                'market_cap': quote_data.get('market_cap'),
                'volume': quote_data.get('volume'),
                'currency': quote_data.get('currency', 'USD'),
                'exchange': quote_data.get('exchange', 'crypto'),
                'country': quote_data.get('country', 'Global')
            }
            
            return result
            
        except Exception as e:
            print(f"Ошибка при получении информации для {symbol}: {e}")
            return None
    
    def _format_ticker(self, symbol: str) -> str:
        """
        Форматировать символ для Twelve Data API
        
        Args:
            symbol: Символ криптовалюты (BTC, ETH и т.д.)
            
        Returns:
            Отформатированный тикер (BTC/USD, ETH/USD и т.д.)
        """
        symbol = symbol.upper().strip()
        
        # Если уже содержит /USD, возвращаем как есть
        if '/USD' in symbol:
            return symbol
        
        # Добавляем /USD для криптовалют
        return f"{symbol}/USD"
    
    def validate_symbol(self, symbol: str) -> bool:
        """
        Проверить, существует ли криптовалюта
        
        Args:
            symbol: Символ криптовалюты
            
        Returns:
            True если существует, False если нет
        """
        try:
            ticker_symbol = self._format_ticker(symbol)
            
            # Пытаемся получить хотя бы один день данных
            ts = self.td_client.time_series(
                symbol=ticker_symbol,
                interval='1day',
                outputsize=1
            )
            
            df = ts.as_pandas()
            return not df.empty
            
        except Exception:
            return False
    
    def get_multiple_crypto_data(self, symbols: list) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Получить данные для нескольких криптовалют одновременно
        
        Args:
            symbols: Список символов криптовалют
            
        Returns:
            Словарь с данными для каждого символа
        """
        result = {}
        
        # Форматируем все символы
        formatted_symbols = [self._format_ticker(symbol) for symbol in symbols]
        
        try:
            # Получаем данные для всех символов одним запросом
            ts = self.td_client.time_series(
                symbol=','.join(formatted_symbols),
                interval=self.timeframe,
                outputsize=self.period
            )
            
            # Получаем данные как JSON для batch запроса
            batch_data = ts.as_json()
            
            # Обрабатываем результаты
            for i, symbol in enumerate(symbols):
                if symbol in batch_data:
                    # Конвертируем данные в DataFrame
                    symbol_data = batch_data[symbol]
                    if isinstance(symbol_data, dict) and 'values' in symbol_data:
                        df = pd.DataFrame(symbol_data['values'])
                        if not df.empty:
                            df['datetime'] = pd.to_datetime(df['datetime'])
                            df.set_index('datetime', inplace=True)
                            # Конвертируем числовые колонки
                            for col in ['open', 'high', 'low', 'close', 'volume']:
                                if col in df.columns:
                                    df[col] = pd.to_numeric(df[col], errors='coerce')
                            result[symbol] = df
                        else:
                            result[symbol] = None
                    else:
                        result[symbol] = None
                else:
                    result[symbol] = None
                    
        except Exception as e:
            print(f"Ошибка при получении batch данных: {e}")
            # В случае ошибки batch запроса, получаем данные по одному
            for symbol in symbols:
                result[symbol] = self.get_crypto_data(symbol)
        
        return result
    
    def get_api_usage(self) -> Optional[Dict]:
        """
        Получить информацию об использовании API
        
        Returns:
            Словарь с информацией об использовании API или None
        """
        try:
            usage = self.td_client.api_usage().as_json()
            return usage
        except Exception as e:
            print(f"Ошибка при получении информации об использовании API: {e}")
            return None
    
    def _generate_mock_data(self, symbol: str) -> pd.DataFrame:
        """
        Генерировать mock данные для тестирования
        
        Args:
            symbol: Символ криптовалюты
            
        Returns:
            DataFrame с mock данными
        """
        # Базовые цены для разных криптовалют
        base_prices = {
            'BTC': 45000,
            'ETH': 3000,
            'SOL': 100,
            'BNB': 300,
            'ADA': 0.5,
            'DOT': 7,
            'LINK': 15,
            'MATIC': 0.8
        }
        
        base_price = base_prices.get(symbol.upper(), 100)
        
        # Генерируем даты
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.period)
        dates = pd.date_range(start=start_date, end=end_date, freq='D')[:self.period]
        
        # Генерируем цены с трендом и волатильностью
        np.random.seed(42)  # Для воспроизводимости
        price_changes = np.random.normal(0, 0.05, len(dates))  # 5% волатильность
        
        prices = [base_price]
        for change in price_changes[1:]:
            new_price = prices[-1] * (1 + change)
            prices.append(new_price)
        
        # Создаем OHLC данные
        data = []
        for i, (date, close_price) in enumerate(zip(dates, prices)):
            # Генерируем open, high, low на основе close
            volatility = 0.02  # 2% внутридневная волатильность
            open_price = close_price * (1 + np.random.normal(0, volatility))
            high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, volatility)))
            low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, volatility)))
            volume = np.random.randint(1000000, 5000000)
            
            data.append({
                'datetime': date,
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': volume
            })
        
        df = pd.DataFrame(data)
        df.set_index('datetime', inplace=True)
        return df