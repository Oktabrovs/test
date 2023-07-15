from telegram.ext import Application, ConversationHandler, CommandHandler, MessageHandler, filters
import os

import helpers
from constants import MAIN_MENU, TASKS, TASK_SELECTED
from start import start
from tasks import tasks, task_selected
from test_code import test_code

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    app = Application.builder().token(os.environ['TOKEN']).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start, block=False)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex("^Tasks$"), tasks, block=False),
            ],
            TASKS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, task_selected)
            ],
            TASK_SELECTED: [
                MessageHandler(filters.TEXT | filters.Document.PY &
                               ~filters.COMMAND, test_code)
            ]
        },
        fallbacks=[]
    )
    app.add_handler(conv_handler)

    helpers.mongodb_task_init()

    app.run_polling()


if __name__ == "__main__":
    main()
