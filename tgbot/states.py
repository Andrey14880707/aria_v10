from aiogram.dispatcher.filters.state import State, StatesGroup


class BookingFSM(StatesGroup):
    choose_service = State()
    choose_master  = State()
    choose_date    = State()
    choose_time    = State()
    enter_phone    = State()
    confirm        = State()
