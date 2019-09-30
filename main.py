import os
import logging.config

from dotenv import load_dotenv

from tg_bot import start_bot

load_dotenv()
LOG_LEVEL = os.getenv('LOG_LEVEL')

log_config = {
        'version': 1,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'base_Formatter',
                'level': LOG_LEVEL,
            }
        },
        'loggers': {
            'tg_bot': {
                'handlers': ['console'],
                'level': LOG_LEVEL,
            },
            'fb_bot': {
                'handlers': ['console'],
                'level': LOG_LEVEL,
            },
            'moltin': {
                'handlers': ['console'],
                'level': LOG_LEVEL,
            },
            'pizza': {
                'handlers': ['console'],
                'level': LOG_LEVEL,
            },
            'database': {
                'handlers': ['console'],
                'level': LOG_LEVEL,
            },
            'JobQueue': {
                'handlers': ['console'],
                'level': LOG_LEVEL,
            },
            'redis': {
                'handlers': ['console'],
                'level': LOG_LEVEL,
            },
        },
        'formatters': {
            'base_Formatter': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s',
            },
        }
    }

logging.config.dictConfig(log_config)

if __name__ == '__main__':
    start_bot()
