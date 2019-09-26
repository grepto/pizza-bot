import os
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


def main():
    set_user_state('asdfasdfads', 'odin')
    print(get_user_state('asdfasdfads1'))


if __name__ == '__main__':
    main()
