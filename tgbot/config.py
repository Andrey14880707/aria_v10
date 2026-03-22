import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]

# Telegram user_id владельца/администратора (через запятую если несколько)
ADMIN_IDS: list[int] = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

# Часовой пояс (для отображения дат)
TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Berlin")

# Шаг слота в минутах
SLOT_STEP: int = int(os.getenv("SLOT_STEP", "30"))

# Сколько дней вперёд показывать для записи
DAYS_AHEAD: int = int(os.getenv("DAYS_AHEAD", "14"))
