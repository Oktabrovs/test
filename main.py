from os import environ

from telegram import Update
from telegram.ext import Application, PicklePersistence, ContextTypes, CommandHandler, MessageHandler, filters


async def start(update: Update, _) -> None:
    await update.message.reply_text('Welcome to the code checker bot!')


async def code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    main_code_string: str = ''

    print(update)


def main() -> None:
    persistence = PicklePersistence(filepath='persistence.pickle')

    app = Application.builder().token(environ['TOKEN']).persistence(persistence).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler((filters.TEXT | filters.Document.PY) & ~filters.COMMAND, code_handler))

    app.run_polling()


if __name__ == '__main__':
    main()
