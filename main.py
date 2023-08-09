from os import environ

from telegram import Update
from telegram.ext import Application, PicklePersistence, ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Welcome to the code checker bot!')


def main() -> None:
    persistence = PicklePersistence(filepath='persistence.pickle')

    app = Application.builder().token(environ['TOKEN']).persistence(persistence).build()

    app.run_polling()


if __name__ == '__main__':
    main()
