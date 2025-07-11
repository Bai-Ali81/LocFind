from operator import length_hint

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import sqlite3
from bs4 import BeautifulSoup
import aiohttp
import datetime
from transliterate import translit

from bd.db import save_to_db, save_rating, get_favorites_by_user  # адаптируй путь
from gevent.libev.corecext import callback
from gpt.gptt import ask_gpt

router = Router()

class MoodSurvey(StatesGroup):
    weather = State()
    mood = State()
    time = State()
    company = State()
    city = State()



@router.message(CommandStart())
async def start(message: Message):

    await message.answer(f'Привет {message.from_user.first_name}, для начала опроса введите /start_survey\n'
                         f'для просмотра своих активностей введите /favorites')



@router.message(Command('favorites'))
async def show_favorites(message: Message):
    user_id = message.from_user.id
    favorites = get_favorites_by_user(user_id)

    if not favorites:
        await message.answer("У тебя пока нет избранных идей 🥲")
        return

    response = "🌟 Твои избранные идеи:\n\n"
    for idx, row in enumerate(favorites, 1):
        # допустим, в row[1] лежит текст идеи (замени на нужный индекс)
        response += f"{idx}. {row[2]}\n"
        # suggestion = row[2]
        # response += f'{idx}. {suggestion}\n'

    await message.answer(response)

    @router.message(Command('cancel'))
    async def state_clear(message: Message, state: FSMContext):
        await state.clear()
        await message.answer('Вы приостоновили опрос для того чтобы перезапустить опрос напишите /start')



@router.message(Command('start_survey'))
async def start_survey(message: Message, state: FSMContext):
        await message.answer("Какой у тебя город. Для определения погоды")
        await state.set_state(MoodSurvey.city)

@router.message(MoodSurvey.city)
async def city(message: Message, state: FSMContext):
    text = message.text
    translated_text = translit(text, 'ru', reversed=True)
    url = (f'https://yandex.ru/pogoda/ru/makhachkala')
    await state.update_data(url=url)
    await message.answer('Спасибо за информанцию сейчас мы попробуем вывыести твою погоду')
    await message.answer('Подтвердите действие Yes, или же /cancel')
    await state.set_state(MoodSurvey.weather)

@router.message(MoodSurvey.weather)
async def weather(message: Message, state: FSMContext):
    async with aiohttp.ClientSession() as session:
        data = await state.get_data()
        async with session.get(data.get('url')) as response:
            data = await response.text()

            soup = BeautifulSoup(data, 'html.parser')
            sign = soup.find('span', class_='AppFactTemperature_sign__1MeN4').text
            value = soup.find('span', class_='AppFactTemperature_value__2qhsG').text
            degree = soup.find('span', class_='AppFactTemperature_degree__LL_2v').text
            # opisanie = soup.find('span', class_='AppFact_feels_IJoel AppFact_feels_withYesterday_yE440').text
            await message.answer(f'Погода: {value}{degree}')
        now = datetime.datetime.now().strftime("%H:%M:%S")
        await message.answer(now)
        await state.update_data(time=now)
        await state.update_data(weather=f'{sign,value,degree}')
        await message.answer("Как у тебя настроение?(веселое, грустное, спокойное)выбери одно из списка")
        await state.set_state(MoodSurvey.mood)

@router.message(MoodSurvey.mood)
async def get_mood(message: Message, state: FSMContext):
    await state.update_data(mood=message.text)
    await message.answer("Сколько у тебя свободного времени? (например: 30 минут, 2 часа, весь день)")
    await state.set_state(MoodSurvey.time)

@router.message(MoodSurvey.time)
async def get_time(message: Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer("С кем ты хотел бы провести время? (Один, с друзьями, с семьёй и т.д.)")
    await state.set_state(MoodSurvey.company)

@router.message(MoodSurvey.company)
async def get_company(message: Message, state: FSMContext):
    await state.update_data(company=message.text)
    data = await state.get_data()

    await message.answer("Думаю над идеей... 🤔")

    gpt_reply = await ask_gpt(
        mood=data["mood"],
        time=data["time"],
        company=data["company"],
        weather=data["weather"]
    )

    user_id = message.from_user.id
    save_to_db(user_id, data["mood"], data["time"], data["company"]) # адаптируй параметры, если нужно

    await state.update_data(suggestion=gpt_reply)

    rate_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👍 Да", callback_data="rate_yes")],
        [InlineKeyboardButton(text="👎 Нет", callback_data="rate_no")]
    ])

    await message.edit_text(f"🧠 Вот идея:\n👉 {gpt_reply}\n\nХочешь занести идею в таблицу избранное?", reply_markup=rate_kb)


@router.callback_query(F.data == "rate_yes")
async def on_rate_yes(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    suggestion = data.get("suggestion")

    rating_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data="rating_1"),
         InlineKeyboardButton(text="2", callback_data="rating_2"),
         InlineKeyboardButton(text="3", callback_data="rating_3"),
         InlineKeyboardButton(text="4", callback_data="rating_4"),
         InlineKeyboardButton(text="5", callback_data="rating_5")]
    ])

    await callback.message.edit_text(
        f"🧠 Вот идея:\n👉 {suggestion}\n\nОцени от 1 до 5:",
        reply_markup=rating_kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rating_"))
async def on_rating(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[1])
    data = await state.get_data()
    suggestion = data.get("suggestion")
    user_id = callback.from_user.id

    save_rating(user_id, suggestion, rating)

    await callback.message.edit_text(f"Спасибо! Ваша оценка: {rating} ⭐")
    await callback.answer()
    await state.clear()


@router.callback_query(F.data == "rate_no")
async def on_rate_no(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Как пожелаете 🙌")
    await callback.answer()
    await state.clear()






