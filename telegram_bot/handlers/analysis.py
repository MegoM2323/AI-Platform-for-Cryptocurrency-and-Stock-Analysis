"""
Обработчики для анализа криптовалют
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, BufferedInputFile
from aiogram.fsm.context import FSMContext

from ..states import AnalysisStates
from ..keyboards import get_main_keyboard, get_cancel_keyboard
from database import Database
from config import config
from data_collectors import CryptoCollector, DataFormatter
from AI_block import AIAnalyzer
from ..token_manager import TokenManager

router = Router()


@router.message(F.text == "🚀 Расширенный анализ")
async def start_enhanced_analysis_button(message: Message, state: FSMContext, db: Database):
    """Обработчик кнопки расширенного анализа (модель токенов)."""
    tm = TokenManager(db)
    balance = await tm.get_balance(message.from_user.id)
    await message.answer(
        (
            "🚀 <b>Расширенный анализ</b>\n\n"
            f"Стоимость: <b>{config.ENHANCED_ANALYSIS_COST}</b> ток.\n"
            f"Текущий баланс: <b>{balance}</b> ток.\n\n"
            "Отправь символ криптовалюты (например: BTC).\n"
            "Результат будет отправлен в виде серии сообщений в Telegram.\n\n"
            "⚠️ <b>Анализ выполняется на дневном таймфрейме</b>"
        ),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.update_data(enhanced_mode=True)
    await state.set_state(AnalysisStates.waiting_for_symbol)


@router.message(F.text == "📊 Анализ токена")
@router.message(Command("analyze"))
async def start_analysis(message: Message, state: FSMContext, db: Database):
    """Начать процесс анализа (токеновая модель)."""
    user_id = message.from_user.id
    token_manager = TokenManager(db)
    balance = await token_manager.get_balance(user_id)

    await state.set_state(AnalysisStates.waiting_for_symbol)
    await message.answer(
        (
            "📊 <b>Анализ криптовалюты</b>\n\n"
            f"Стоимость: базовый — <b>{config.BASIC_ANALYSIS_COST}</b> ток., "
            f"расширенный — <b>{config.ENHANCED_ANALYSIS_COST}</b> ток.\n"
            f"Текущий баланс: <b>{balance}</b> ток.\n\n"
            "Введи символ (например: BTC, ETH, SOL, BNB).\n\n"
            "Или нажми \"Отмена\" для выхода"
        ),
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(AnalysisStates.waiting_for_symbol, F.text == "❌ Отмена")
async def cancel_analysis(message: Message, state: FSMContext):
    """Отменить анализ"""
    await state.clear()
    await message.answer(
        "❌ Анализ отменен",
        reply_markup=get_main_keyboard()
    )


@router.message(AnalysisStates.waiting_for_symbol)
async def process_symbol(message: Message, state: FSMContext, db: Database):
    """Обработать введенный символ и выполнить анализ"""
    import logging
    logger = logging.getLogger(__name__)
    
    symbol = message.text.strip().upper()
    user_id = message.from_user.id
    
    logger.info(f"Пользователь {user_id} запросил анализ {symbol}")
    
    # Проверяем, что пользователь действительно в состоянии ожидания символа
    current_state = await state.get_state()
    if current_state != AnalysisStates.waiting_for_symbol:
        logger.warning(f"Пользователь {user_id} не в состоянии ожидания символа. Текущее состояние: {current_state}")
        await message.answer(
            "❌ Неожиданное состояние. Пожалуйста, начни анализ заново.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    
    # Проверяем формат
    if len(symbol) > 10 or not symbol.isalnum():
        logger.warning(f"Неверный формат символа от пользователя {user_id}: {symbol}")
        await message.answer(
            "❌ Неверный формат символа.\n"
            "Введи корректный символ (например: BTC, ETH)"
        )
        return
    
    # Определяем режим и стоимость; списываем токены заранее
    data = await state.get_data()
    enhanced_mode_prefetched = data.get('enhanced_mode', False)
    cost = config.ENHANCED_ANALYSIS_COST if enhanced_mode_prefetched else config.BASIC_ANALYSIS_COST
    token_manager = TokenManager(db)
    user_balance = await token_manager.get_balance(user_id)
    if user_balance < cost:
        await message.answer(
            (
                "❌ Недостаточно токенов.\n\n"
                f"Требуется: <b>{cost}</b> ток., на счёте: <b>{user_balance}</b> ток.\n"
                "Пополнить баланс: /buy_tokens или через меню."
            ),
            parse_mode="HTML",
            reply_markup=get_main_keyboard(),
        )
        await state.clear()
        return

    debited = await token_manager.deduct_tokens(
        user_id=user_id,
        amount=cost,
        transaction_type=("enhanced_analysis" if enhanced_mode_prefetched else "basic_analysis"),
        description=f"Списание за анализ {symbol}",
    )
    if not debited:
        # Баланс мог измениться конкурентно
        latest_balance = await token_manager.get_balance(user_id)
        await message.answer(
            (
                "❌ Не удалось списать токены.\n\n"
                f"Требуется: <b>{cost}</b> ток., на счёте: <b>{latest_balance}</b> ток."
            ),
            parse_mode="HTML",
            reply_markup=get_main_keyboard(),
        )
        await state.clear()
        return

    # Отправляем сообщение о начале анализа только для обычного режима
    processing_msg = None
    if not enhanced_mode_prefetched:
        processing_msg = await message.answer(
            f"🔄 Анализирую {symbol}...\nЭто может занять несколько секунд",
            parse_mode="HTML",
        )
    
    # Этап 1: Сбор данных
    try:
        logger.info(f"Начинаем сбор данных для {symbol}")
        
        # Собираем данные
        collector = CryptoCollector(
            timeframe=config.DEFAULT_TIMEFRAME,
            period=config.DEFAULT_PERIOD
        )
        
        # Проверяем существование токена
        logger.info(f"Проверяем валидность символа {symbol}")
        if not collector.validate_symbol(symbol):
            logger.warning(f"Символ {symbol} не прошел валидацию")
            if processing_msg:
                await processing_msg.edit_text(
                    f"❌ Криптовалюта {symbol} не найдена.\n\n"
                    f"Проверь правильность символа и попробуй снова.\n"
                    f"Примеры: BTC, ETH, SOL, BNB"
                )
            else:
                await message.answer(
                    f"❌ Криптовалюта {symbol} не найдена.\n\n"
                    f"Проверь правильность символа и попробуй снова.\n"
                    f"Примеры: BTC, ETH, SOL, BNB"
                )
            return
        
        # Получаем данные
        logger.info(f"Получаем исторические данные для {symbol}")
        data = collector.get_crypto_data(symbol)
        if data is None or data.empty:
            logger.error(f"Не удалось получить данные для {symbol}")
            if processing_msg:
                await processing_msg.edit_text(
                    f"❌ Не удалось получить данные для {symbol}"
                )
            else:
                await message.answer(
                    f"❌ Не удалось получить данные для {symbol}"
                )
            return
        
        logger.info(f"Данные получены: {data.shape[0]} записей")
        
        current_price = collector.get_current_price(symbol)
        logger.info(f"Текущая цена {symbol}: {current_price}")
        
    except Exception as e:
        logger.error(f"Ошибка при сборе данных для {symbol}: {e}")
        # Возврат токенов при сбое
        try:
            await token_manager.add_tokens(
                user_id=user_id,
                amount=cost,
                transaction_type="refund",
                description=f"Возврат за ошибку данных {symbol}",
            )
        except Exception:
            pass
        if processing_msg:
            await processing_msg.edit_text(
                "❌ Ошибка при получении данных.\n"
                "Попробуй позже."
            )
        else:
            await message.answer(
                "❌ Ошибка при получении данных.\n"
                "Попробуй позже."
            )
        return
    
    # Этап 2: Форматирование данных
    try:
        logger.info("Форматируем данные для анализа")
        formatter = DataFormatter()
        formatted_data = formatter.format_for_analysis(data, symbol, current_price)
        logger.info(f"Данные отформатированы: {len(formatted_data)} символов")
    except Exception as e:
        logger.error(f"Ошибка при форматировании данных для {symbol}: {e}")
        try:
            await token_manager.add_tokens(
                user_id=user_id,
                amount=cost,
                transaction_type="refund",
                description=f"Возврат за ошибку форматирования {symbol}",
            )
        except Exception:
            pass
        if processing_msg:
            await processing_msg.edit_text(
                "❌ Ошибка при обработке данных.\n"
                "Попробуй позже."
            )
        else:
            await message.answer(
                "❌ Ошибка при обработке данных.\n"
                "Попробуй позже."
            )
        return
    
    # Проверяем режим анализа (обычный или расширенный)
    data = await state.get_data()
    enhanced_mode = data.get('enhanced_mode', False)
    
    if enhanced_mode:
        # Расширенный анализ с новостями
        try:
            logger.info(f"Запускаем расширенный анализ для {symbol}")
            from .enhanced_analysis import _run_enhanced
            
            # Выполняем расширенный анализ
            # Информационное сообщение на время выполнения
            temp_msg = await message.answer("🔄 Выполняю расширенный анализ... Это может занять до 30–60 секунд.")
            analysis_result, pdf_bytes, _, _ = await _run_enhanced(symbol, db)
            
            # Требование: отправлять только один месседж — PDF-отчет
            if pdf_bytes:
                pdf_caption = f"""
📊 <b>ПОДРОБНЫЙ PDF-ОТЧЕТ {symbol}</b>

📈 <b>Основные показатели:</b>
• Общий скор: {analysis_result.get('overall_score', 0):.2f}/1.0
• Уровень риска: {analysis_result.get('risk_level', 'N/A')}
• Рекомендация: {analysis_result.get('recommendation', 'N/A').upper()}

📰 <b>Анализ новостей:</b>
• Проанализировано статей: {len(analysis_result.get('sentiment', {}).get('articles', []))}
• Тональность: {analysis_result.get('sentiment', {}).get('overall', {}).get('label', 'N/A')}

📋 <b>Содержание PDF:</b>
• Executive Summary
• Технический анализ с таблицами
• Анализ настроений с новостями
• Графики и визуализации
• Ключевые моменты
• Источники данных

⚠️ <b>Важно:</b> Анализ основан на дневных данных (1d)
                """
                # Удаляем временное информационное сообщение
                try:
                    await temp_msg.delete()
                except Exception:
                    pass

                await message.answer_document(
                    document=BufferedInputFile(pdf_bytes, filename=f"{symbol}_detailed_analysis.pdf"),
                    caption=pdf_caption,
                    parse_mode="HTML"
                )
            
            # Очищаем состояние
            await state.clear()
            return
            
        except Exception as e:
            logger.error(f"Ошибка при расширенном анализе для {symbol}: {e}")
            # Пытаемся удалить временное сообщение, если оно было отправлено
            try:
                if 'temp_msg' in locals() and temp_msg is not None:
                    await temp_msg.delete()
            except Exception:
                pass
            # Сообщаем пользователю об ошибке единым сообщением
            await message.answer(
                "❌ Ошибка при выполнении расширенного анализа. Попробуй позже.",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
            return
    
    # Обычный AI анализ
    try:
        logger.info("Запускаем AI анализ")
        analyzer = AIAnalyzer(
            api_key=config.OPENROUTER_API_KEY,
            model=config.AI_MODEL
        )
        
        analysis_result = await analyzer.analyze_crypto(formatted_data, symbol)
        
        logger.info(f"AI анализ вернул результат: {type(analysis_result)}")
        if analysis_result:
            logger.info(f"Длина результата: {len(analysis_result)} символов")
            logger.info(f"Первые 100 символов: {analysis_result[:100]}")
        else:
            logger.warning("AI анализ вернул None или пустой результат")
        
        if analysis_result is None or not analysis_result.strip():
            logger.error(f"AI анализ не вернул результат для {symbol}")
            await processing_msg.edit_text(
                "❌ Ошибка при выполнении анализа.\n"
                "Попробуй позже."
            )
            return
        
        logger.info(f"AI анализ завершен: {len(analysis_result)} символов")
    except Exception as e:
        logger.error(f"Ошибка при AI анализе для {symbol}: {e}")
        try:
            await token_manager.add_tokens(
                user_id=user_id,
                amount=cost,
                transaction_type="refund",
                description=f"Возврат за ошибку AI {symbol}",
            )
        except Exception:
            pass
        await processing_msg.edit_text(
            "❌ Ошибка при выполнении анализа.\n"
            "Попробуй позже."
        )
        return
    
    # Этап 4: Сохранение и отправка результата
    try:
        logger.info(f"Начинаем этап 4 для {symbol}")
        logger.info(f"analysis_result тип: {type(analysis_result)}, длина: {len(analysis_result) if analysis_result else 'None'}")
        
        # Увеличиваем счетчик анализов
        logger.info("Увеличиваем счетчик анализов")
        await db.increment_analysis_count(user_id)
        
        # Сохраняем анализ в БД
        logger.info("Сохраняем анализ в базу данных")
        await db.save_analysis(user_id, symbol, analysis_result)
        logger.info("Анализ сохранен в БД")
        
        # Удаляем сообщение о процессе анализа
        try:
            await processing_msg.delete()
            logger.info("Сообщение о процессе анализа удалено")
        except Exception as delete_error:
            logger.warning(f"Не удалось удалить сообщение о процессе: {delete_error}")
        
        # Очищаем HTML теги из результата анализа
        import re
        import html
        
        # Убираем HTML теги и экранируем специальные символы
        clean_result = re.sub(r'<[^>]+>', '', analysis_result)
        clean_result = html.escape(clean_result)
        
        logger.info(f"Очищенный результат: {len(clean_result)} символов")
        
        # Разбиваем длинное сообщение, если нужно
        logger.info(f"Проверяем длину результата: {len(clean_result)} символов")
        if len(clean_result) > 4096:
            # Telegram ограничивает сообщения до 4096 символов
            logger.info(f"Разбиваем длинное сообщение на части")
            chunks = [clean_result[i:i+4096] for i in range(0, len(clean_result), 4096)]
            logger.info(f"Создано {len(chunks)} частей")
            for i, chunk in enumerate(chunks):
                logger.info(f"Отправляем часть {i+1}/{len(chunks)}")
                # Добавляем главное меню только к последней части
                if i == len(chunks) - 1:
                    await message.answer(f"📄 Часть {i+1}/{len(chunks)}\n\n{chunk}", reply_markup=get_main_keyboard())
                else:
                    await message.answer(f"📄 Часть {i+1}/{len(chunks)}\n\n{chunk}")
        else:
            logger.info("Отправляем результат целиком")
            await message.answer(clean_result, reply_markup=get_main_keyboard())
            logger.info("Результат отправлен")
        
        # Очищаем состояние
        logger.info("Очищаем состояние")
        await state.clear()
        
        logger.info(f"Анализ {symbol} успешно завершен для пользователя {user_id}")
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Ошибка при сохранении/отправке результата для {symbol}: {e}")
        logger.error(f"Полная ошибка: {error_details}")
        # Возврат токенов при сбое отправки/сохранения
        try:
            await token_manager.add_tokens(
                user_id=user_id,
                amount=cost,
                transaction_type="refund",
                description=f"Возврат за ошибку отправки {symbol}",
            )
        except Exception:
            pass
        
        # Даже если произошла ошибка при сохранении, показываем результат
        logger.info("Показываем результат несмотря на ошибку")
        
        # Удаляем сообщение о процессе анализа
        try:
            await processing_msg.delete()
        except Exception:
            pass
        
        # Очищаем HTML теги из результата анализа
        import re
        import html
        
        # Убираем HTML теги и экранируем специальные символы
        clean_result = re.sub(r'<[^>]+>', '', analysis_result)
        clean_result = html.escape(clean_result)
        
        if len(clean_result) > 4096:
            chunks = [clean_result[i:i+4096] for i in range(0, len(clean_result), 4096)]
            for i, chunk in enumerate(chunks):
                # Добавляем главное меню только к последней части
                if i == len(chunks) - 1:
                    await message.answer(f"📄 Часть {i+1}/{len(chunks)}\n\n{chunk}", reply_markup=get_main_keyboard())
                else:
                    await message.answer(f"📄 Часть {i+1}/{len(chunks)}\n\n{chunk}")
        else:
            await message.answer(clean_result, reply_markup=get_main_keyboard())
        
        await state.clear()


@router.callback_query(F.data.startswith("use_additional_analysis_"))
async def use_additional_analysis(callback: CallbackQuery, state: FSMContext, db: Database):
    """Использовать дополнительный анализ"""
    await callback.answer()
    
    user_id = callback.from_user.id
    
    # Проверяем, есть ли дополнительные анализы
    additional_analyses = await db.get_additional_analyses(user_id)
    if additional_analyses <= 0:
        # Удаляем inline-сообщение
        try:
            await callback.message.delete()
        except:
            pass
        # Отправляем новое сообщение с главным меню
        await callback.message.answer(
            "❌ У вас нет дополнительных анализов",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Используем дополнительный анализ
    success = await db.use_additional_analysis(user_id)
    if not success:
        # Удаляем inline-сообщение
        try:
            await callback.message.delete()
        except:
            pass
        # Отправляем новое сообщение с главным меню
        await callback.message.answer(
            "❌ Ошибка использования дополнительного анализа",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Переходим к анализу
    await state.set_state(AnalysisStates.waiting_for_symbol)
    # Удаляем inline-сообщение
    try:
        await callback.message.delete()
    except:
        pass
    # Отправляем новое сообщение с клавиатурой отмены
    await callback.message.answer(
        f"✅ <b>Дополнительный анализ использован!</b>\n\n"
        f"Осталось дополнительных анализов: <b>{additional_analyses - 1}</b>\n\n"
        f"Введи символ криптовалюты для анализа\n"
        f"(например: BTC, ETH, SOL, BNB)\n\n"
        f"Или нажми \"Отмена\" для выхода",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "cancel_analysis")
async def cancel_analysis_callback(callback: CallbackQuery, state: FSMContext):
    """Отменить анализ через callback"""
    await callback.answer()
    await state.clear()
    # Удаляем inline-сообщение
    try:
        await callback.message.delete()
    except:
        pass
    # Отправляем новое сообщение с главным меню
    await callback.message.answer(
        "❌ Анализ отменен",
        reply_markup=get_main_keyboard()
    )

