import logging
import pymongo as pymongo
import warnings
from telegram.warnings import PTBDeprecationWarning

warnings.filterwarnings('error', category=PTBDeprecationWarning)

logging.basicConfig(
    # filename='syccbot.log',
    # format="[%(asctime)s %(levelname)s] %(message)s",
    format="[%(levelname)s] %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["code_checker"]
chats_col = mydb["chats"]
users_col = mydb["users"]
tasks_col = mydb["tasks"]


MAIN_MENU = 1
TASKS = 11
TASK_SELECTED = 111
TEST_CODE = 1111
