from dotenv import load_dotenv
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# Carga las variables del archivo .env
load_dotenv()


DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

# Convertir el diccionario en una URL para SQLAlchemy
SQLALCHEMY_DATABASE_URL = (
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
    f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
)




# Obtener el valor de DEBUG
DEBUG = bool(os.getenv('DEBUG'))

if DEBUG:
    allow_origins=["*"]

else:
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
