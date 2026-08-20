import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "meetings.db"


def get_connection():
    """
    Create a connection to the SQLite database.
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():
    """
    Create the meetings table if it doesn't already exist.
    """

    connection = get_connection()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS meetings (
            id TEXT PRIMARY KEY,

            title TEXT NOT NULL,

            original_filename TEXT NOT NULL,

            audio_path TEXT,

            transcript_path TEXT,

            summary_path TEXT,

            status TEXT NOT NULL,

            duration REAL,

            language TEXT,

            created_at TEXT NOT NULL,

            updated_at TEXT NOT NULL
        )
        """
    )

    connection.commit()
    connection.close()


if __name__ == "__main__":
    initialize_database()

    print(
        f"Database initialized at:\n{DATABASE_PATH}"
    )