from telegram import Update
from telegram.ext import ContextTypes

from constants import chats_col, users_col
from main_menu import main_menu


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    chat = update.message.chat

    print(f'\n/start command from {chat.first_name} {chat.last_name}\n')

    chat_found = chats_col.find_one({"id": chat.id})
    if not chat_found:
        chat_dict = {
            "id": chat.id,
            "type": chat.type,
            "last_name": chat.last_name,
            "first_name": chat.first_name
        }
        chats_col.insert_one(chat_dict)
        print("added new chat: " + str(chat_dict))

    user = update.message.from_user
    user_found = users_col.find_one({"id": user.id})
    if not user_found:
        user_dict = {
            "is_bot": user.is_bot,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "id": user.id,
            "language_code": user.language_code
        }
        users_col.insert_one(user_dict)
        print("added new user: " + str(user_dict))

    await update.message.reply_text("Welcome to the code checker bot!")

    return await main_menu(update, context)
