import os
import json
import logging

import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = os.getenv('REDIS_PORT')
REDIS_PASWORD = os.getenv('REDIS_PASWORD')

_database = None
logger = logging.getLogger('database')


def get_database_connection():
    global _database
    if _database is None:
        database_password = REDIS_PASWORD
        database_host = REDIS_HOST
        database_port = REDIS_PORT
        _database = redis.Redis(host=database_host, port=database_port, password=database_password)
    return _database


def get_user_state(user_id):
    db = get_database_connection()
    user_state = db.get(user_id)
    if user_state:
        return user_state.decode("utf-8")


def set_user_state(user_id, state):
    db = get_database_connection()
    db.set(user_id, state)


def load_menu_to_db(menu):
    db = get_database_connection()
    db.set('menu', json.dumps(menu))


def get_menu_from_db():
    db = get_database_connection()
    menu = db.get('menu')
    return json.loads(menu)


def main():
    pass


if __name__ == '__main__':
    main()
