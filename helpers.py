from constants import mydb, tasks_col


def mongodb_task_init() -> None:
    list_of_cols = mydb.list_collection_names()
    if "tasks" not in list_of_cols:
        task_dict = {
            '_id': 1,
            'level': 1,
            'title': 'Multiply',
            'description': 'Write function to multiply two numbers and return result',
            'tags': ['*'],
            'test_file': '1.py'
        }
        tasks_col.insert_one(task_dict)
        # logger.info("added task to db")
        print("added task to db")
