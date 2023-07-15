from telegram.ext import Application, ConversationHandler, CommandHandler, MessageHandler, filters, PicklePersistence, AIORateLimiter
import os

import helpers
from constants import MAIN_MENU, TASKS, TASK_SELECTED
from start import start
from tasks import tasks, task_selected
from error_handler import error_handler
from test_code import test_code

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    persistence = PicklePersistence(filepath='persistence.pickle')

    app = Application.builder().token(os.environ['TOKEN']).rate_limiter(
        AIORateLimiter()).persistence(persistence).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex("^Tasks$"), tasks),
            ],
            TASKS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, task_selected)
            ],
            TASK_SELECTED: [
                MessageHandler(filters.TEXT | filters.Document.PY &
                               ~filters.COMMAND, test_code)
            ]
        },
        fallbacks=[CommandHandler("start", start)],
        persistent=True,
        name='main_conversation'
    )

    app.add_handler(conv_handler)
    app.add_error_handler(error_handler)

    helpers.mongodb_task_init()

    app.run_polling()


if __name__ == "__main__":
    main()
