import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from urllib.request import urlopen
import requests
from constants import TEST_CODE
from dotenv import load_dotenv


load_dotenv()

url = os.environ['GLOT_URL']

headers = {
    'Authorization': os.environ['GLOT_AUTHORIZATION'],
    'Content-type': 'application/json'
}


async def test_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    main_str = ''

    if update.message.text:
        msg_text = update.message.text
        main_str = msg_text

    if update.message.document:
        file_tg = await context.bot.get_file(update.message.document.file_id)
        file = urlopen(file_tg.file_path)
        for line in file:
            main_str += line.decode('utf-8')

    unit_test_str = ''
    with open('test_files/{}.py'.format(context.chat_data['task_id']), "r") as test_f:
        unit_test_str += test_f.read()

    print(f'--- code from user\n{main_str}\n---')
    print(f'--- unit tests\n{unit_test_str}\n---')

    data = {
        "files": [
            {"name": "unit_tests.py", "content": unit_test_str},
            {"name": "user_code.py", "content": main_str}
        ]
    }

    x = requests.post(url, json=data, headers=headers)

    print(x.json())

    text = x.json()

    await update.message.reply_text(text=text)

    return TEST_CODE
