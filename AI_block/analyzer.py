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
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"Начинаем AI анализ для {symbol}")
            
            # Создаем промпт
            user_prompt = create_analysis_prompt(market_data, symbol)
            logger.debug(f"Промпт создан, длина: {len(user_prompt)} символов")
            
            # Выполняем запрос в отдельном потоке (API синхронное)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                partial(
                    self._make_api_call,
                    user_prompt
                )
            )
            
            if response and response.strip():
                logger.info(f"AI анализ успешно завершен для {symbol}, длина ответа: {len(response)} символов")
                return response.strip()
            else:
                logger.warning(f"AI анализ вернул пустой ответ для {symbol}. Response: '{response}'")
                return None
            
        except Exception as e:
            logger.error(f"Ошибка при AI анализе {symbol}: {e}")
            import traceback
            logger.error(f"Полная ошибка: {traceback.format_exc()}")
            return None
    
    def _make_api_call(self, user_prompt: str) -> str:
        """
        Выполнить синхронный API вызов
        
        Args:
            user_prompt: Промпт пользователя
            
        Returns:
            Ответ от AI
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.debug(f"Отправляем запрос к AI API, модель: {self.model}")
            
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
            
            if response and response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                logger.debug(f"AI API вернул ответ длиной {len(content) if content else 0} символов")
                if content:
                    logger.debug(f"Первые 100 символов ответа: {content[:100]}")
                return content or ""
            else:
                logger.error("AI API вернул пустой ответ")
                return ""
                
        except Exception as e:
            logger.error(f"Ошибка при вызове AI API: {e}")
            raise
    
    async def quick_analysis(self, market_data: str, symbol: str) -> Optional[str]:
        """
        Быстрый анализ (краткий)
        
        Args:
            market_data: Отформатированные данные
            symbol: Символ криптовалюты
            
        Returns:
            Краткий анализ
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"Начинаем быстрый анализ для {symbol}")
            
            user_prompt = f"{create_analysis_prompt(market_data, symbol)}\n\nПредоставь КРАТКИЙ анализ (3-5 предложений)."
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                partial(self._make_api_call, user_prompt)
            )
            
            if response and response.strip():
                logger.info(f"Быстрый анализ успешно завершен для {symbol}")
                return response
            else:
                logger.warning(f"Быстрый анализ вернул пустой ответ для {symbol}")
                return None
            
        except Exception as e:
            logger.error(f"Ошибка при быстром анализе {symbol}: {e}")
            import traceback
            logger.error(f"Полная ошибка: {traceback.format_exc()}")
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
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info("Начинаем кастомный анализ")
            
            full_prompt = f"{market_data}\n\n{custom_prompt}"
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                partial(self._make_api_call, full_prompt)
            )
            
            if response and response.strip():
                logger.info("Кастомный анализ успешно завершен")
                return response
            else:
                logger.warning("Кастомный анализ вернул пустой ответ")
                return None
            
        except Exception as e:
            logger.error(f"Ошибка при кастомном анализе: {e}")
            import traceback
            logger.error(f"Полная ошибка: {traceback.format_exc()}")
            return None

