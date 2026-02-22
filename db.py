import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

def get_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", "sistema_delivery_db"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
    )