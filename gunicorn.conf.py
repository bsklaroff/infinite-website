import asyncio
from src.server import init_app

bind = "0.0.0.0:8008"
capture_output = True
proc_name = "iw_server"
logconfig_dict = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[%(asctime)s | %(levelname)s | %(name)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S %z'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.FileHandler',
            'formatter': 'standard',
            'filename': 'iw.log',
            'mode': 'a'
        }
    },
    'loggers': {
        'gunicorn.access': {
            'level': 'INFO',
            'handlers': ['console', 'file']
        },
        'gunicorn.error': {
            'level': 'INFO',
            'handlers': ['console', 'file']
        }
    }
}

def post_worker_init(worker):
    asyncio.run(init_app())
