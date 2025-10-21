"""
AI анализ данных через OpenRouter API
"""

from openai import OpenAI
from typing import Optional
import asyncio
from functools import partial

from .prompts import SYSTEM_PROMPT, create_analysis_prompt


class AIAnalyzer:
    """Класс для AI анализа криптовалют через OpenRouter"""
    
    def __init__(self, api_key: str, model: str = "meta-llama/llama-3.1-8b-instruct:free"):
        """
        Инициализация анализатора
        
        Args:
            api_key: API ключ OpenRouter
            model: Модель для использования (по умолчанию бесплатная модель)
        """
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        self.model = model
    
    async def analyze_crypto(self, market_data: str, symbol: str) -> Optional[str]:
        """
        Анализировать криптовалюту
        
        Args:
            market_data: Отформатированные данные о криптовалюте
            symbol: Символ криптовалюты
            
        Returns:
            Текст анализа или None в случае ошибки
        """
        try:
            # Создаем промпт
            user_prompt = create_analysis_prompt(market_data, symbol)
            
            # Выполняем запрос в отдельном потоке (API синхронное)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                partial(
                    self._make_api_call,
                    user_prompt
                )
            )
            
            return response
            
        except Exception as e:
            print(f"Ошибка при анализе {symbol}: {e}")
            return None
    
    def _make_api_call(self, user_prompt: str) -> str:
        """
        Выполнить синхронный API вызов
        
        Args:
            user_prompt: Промпт пользователя
            
        Returns:
            Ответ от AI
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        return response.choices[0].message.content
    
    async def quick_analysis(self, market_data: str, symbol: str) -> Optional[str]:
        """
        Быстрый анализ (краткий)
        
        Args:
            market_data: Отформатированные данные
            symbol: Символ криптовалюты
            
        Returns:
            Краткий анализ
        """
        try:
            user_prompt = f"{create_analysis_prompt(market_data, symbol)}\n\nПредоставь КРАТКИЙ анализ (3-5 предложений)."
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                partial(self._make_api_call, user_prompt)
            )
            
            return response
            
        except Exception as e:
            print(f"Ошибка при быстром анализе {symbol}: {e}")
            return None
    
    async def analyze_with_custom_prompt(self, market_data: str, 
                                        custom_prompt: str) -> Optional[str]:
        """
        Анализ с кастомным промптом
        
        Args:
            market_data: Рыночные данные
            custom_prompt: Пользовательский промпт
            
        Returns:
            Результат анализа
        """
        try:
            full_prompt = f"{market_data}\n\n{custom_prompt}"
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                partial(self._make_api_call, full_prompt)
            )
            
            return response
            
        except Exception as e:
            print(f"Ошибка при кастомном анализе: {e}")
            return None

