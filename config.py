import logging
import os
LOGGING_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG')
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

# Set environment variables
PORT = int(os.getenv('PORT', 8080))
PREFIXURL = os.getenv('PREFIXURL', '/backsurvey-service')
MONGODB = os.getenv('MONGODB', "mongodb+srv://perpetcloud:NsIgvcQ5E7OQ2JSW@equalpet.tt45urw.mongodb.net/")
DB_URI = os.getenv('DB_URI', "jdbc:mariadb://dev.promptinsight.ai:3306/perpet?allowPublicKeyRetrieval=true&useSSL=false&serverTimezone=Asia/Seoul")

DB_HOST = os.getenv('DB_HOST', 'dev.promptinsight.ai') #"dev.promptinsight.ai" # "127.0.0.1" # 
DB_USER = os.getenv('DB_USER', 'perpetdev') #"perpetdev" # "perpetapi" # 
DB_PASSWORD = os.getenv('DB_PASSWORD', "perpet1234!") #"perpet1234!" # "O7dOQFXQ1PYY" # 
DB_DATABASE = os.getenv('DB_DATABASE', 'perpet')
DB_PORT = int(os.getenv('DB_PORT', 3306))

#For production rdbs
#DB_URI=mysql+aiomysql://perpetapi:O7dOQFXQ1PYY@prod-perpet.coxtlbkqbiqx.ap-northeast-2.rds.amazonaws.com:3306/perpet?charset=utf8mb4 
#DB_HOST="prod-perpet.coxtlbkqbiqx.ap-northeast-2.rds.amazonaws.com"
#DB_USER="perpetapi"
#DB_PASSWORD="O7dOQFXQ1PYY"
#DB_DATABASE="perpet"
#DB_PORT=3306

APISERVER = os.getenv('APISERVER', "http://dev.promptinsight.ai:10002") # https://api2.equal.pet 
EUREKA = os.getenv('EUREKA_CLIENT_SERVICEURL_DEFAULTZONE', "http://dev.promptinsight.ai:10001/eureka") 