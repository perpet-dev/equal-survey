import logging
LOGGING_LEVEL = 'DEBUG'
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '{levelname}: {asctime} - {name}.{funcName} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        # 'file': {
        #     'level': LOGGING_LEVEL,
        #     'class': 'logging.handlers.RotatingFileHandler',
        #     'filename': '/app/logs/fastapi.log',
        #     'maxBytes': 1024*1024*5,  # 5 MB
        #     'backupCount': 3,
        #     'formatter': 'default',
        # },
        'console': {
            'level': LOGGING_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'default',
        },
    },
    'loggers': {
        'root': {  # root logger
            #'handlers': ['console', 'file'],
            'handlers': ['console'],
            'level': LOGGING_LEVEL,
            'propagate': True,
        },
        'uvicorn.access': {
            'handlers': ['console'],
            'level': LOGGING_LEVEL,
            'propagate': True,
        },
        'fastapi': {
            'handlers': ['console'],
            'level': LOGGING_LEVEL,
            'propagate': True,
        },
    },
}
# Set pymongo's OCSP support logger to INFO level
ocsp_logger = logging.getLogger('pymongo.ocsp_support')
ocsp_logger.setLevel(logging.INFO)

# MongoDB connection string
# MONGODB = "mongodb+srv://ivanberlocher:P4XZZRTkgbG6iRcX@perpet.uhcs1fw.mongodb.net/?retryWrites=true&w=majority"
#MONGODB = "mongodb+srv://ivanberlocher:P4XZZRTkgbG6iRcX@perpet.uhcs1fw.mongodb.net/?retryWrites=true&w=majority"
MONGODB = "mongodb+srv://perpetcloud:NsIgvcQ5E7OQ2JSW@equalpet.tt45urw.mongodb.net/"