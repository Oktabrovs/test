from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from constants import MAIN_MENU


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    buttons = [
        ["Tasks", "blank"],
        ["blank", "blank"],
        ["blank"]
    ]
    keyboard = ReplyKeyboardMarkup(buttons, one_time_keyboard=True)

    await update.message.reply_text(text="Main menu:", reply_markup=keyboard)

    return MAIN_MENU
