import os
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))


def get_db_connection():
    required_settings = ("DB_HOST", "DB_USER", "DB_NAME")
    missing_settings = [
        setting for setting in required_settings if not os.getenv(setting)
    ]

    if missing_settings:
        missing = ", ".join(missing_settings)
        raise mysql.connector.InterfaceError(
            f"Missing required database setting(s): {missing}"
        )

    try:
        port = int(os.getenv("DB_PORT", "3306"))
    except ValueError as error:
        raise mysql.connector.InterfaceError(
            "DB_PORT must be a whole number."
        ) from error
    if not 1 <= port <= 65535:
        raise mysql.connector.InterfaceError(
            "DB_PORT must be between 1 and 65535."
        )

    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        port=port,
        user=os.environ["DB_USER"],
        password=os.getenv("DB_PASSWORD", ""),
        database=os.environ["DB_NAME"],
        connection_timeout=5,
    )
