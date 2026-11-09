import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def get_db_path():
    return os.environ.get("DB_PATH", str(BASE_DIR / "database" / "examvault.db"))

def get_db_type():
    return os.environ.get("DB_TYPE", "sqlite").strip().lower()

def get_mysql_config():
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", 3306)),
        "user": os.environ.get("DB_USER", "examvault_user"),
        "password": os.environ.get("DB_PASSWORD", "examvault_pass"),
        "database": os.environ.get("DB_NAME", "examvault")
    }

# Backwards-compatible constants
DB_PATH = get_db_path()
DB_TYPE = get_db_type()
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_USER = os.environ.get("DB_USER", "examvault_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "examvault_pass")
DB_NAME = os.environ.get("DB_NAME", "examvault")

try:
    import pymysql
    import pymysql.cursors
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False


def convert_placeholders(sql):
    """Converts SQLite '?' parameter placeholders to MySQL '%s' placeholders."""
    parts = []
    in_quote = False
    quote_char = None
    for char in sql:
        if char in ("'", '"'):
            if not in_quote:
                in_quote = True
                quote_char = char
            elif quote_char == char:
                in_quote = False
                quote_char = None
            parts.append(char)
        elif char == '?' and not in_quote:
            parts.append('%s')
        else:
            parts.append(char)
    return ''.join(parts)


class RowDict(dict):
    """Row wrapper allowing both dictionary (row['id']) and tuple (row[0]) access."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._keys = list(self.keys())

    def __getitem__(self, item):
        if isinstance(item, int):
            return self[self._keys[item]]
        return super().__getitem__(item)


class MySQLCursorWrapper:
    """Wraps a PyMySQL cursor to provide RowDict results and lastrowid compatibility."""
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def execute(self, sql, params=None):
        converted_sql = convert_placeholders(sql)
        if params is not None:
            self._cursor.execute(converted_sql, params)
        else:
            self._cursor.execute(converted_sql)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        return RowDict(row) if row is not None else None

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [RowDict(r) for r in rows] if rows else []

    def close(self):
        self._cursor.close()

    def __iter__(self):
        return iter(self.fetchall())


class MySQLConnectionWrapper:
    """Wraps a PyMySQL connection to mirror sqlite3 connection API."""
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, sql, params=None):
        cursor = self._conn.cursor(pymysql.cursors.DictCursor)
        wrapper = MySQLCursorWrapper(cursor)
        wrapper.execute(sql, params)
        return wrapper

    def cursor(self):
        raw_cursor = self._conn.cursor(pymysql.cursors.DictCursor)
        return MySQLCursorWrapper(raw_cursor)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_db_connection():
    """Returns an active database connection depending on DB_TYPE environment variable."""
    db_type = get_db_type()
    if db_type == "mysql":
        if not HAS_PYMYSQL:
            raise ImportError(
                "PyMySQL is required for MySQL database connections. "
                "Install PyMySQL or configure DB_TYPE=sqlite."
            )
        cfg = get_mysql_config()
        raw_conn = pymysql.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            charset="utf8mb4",
            autocommit=False
        )
        return MySQLConnectionWrapper(raw_conn)
    else:
        # Default: SQLite
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def initialize_database():
    """Initializes tables for either SQLite or MySQL."""
    if get_db_type() == "mysql":
        initialize_mysql_database()
    else:
        initialize_sqlite_database()


def initialize_sqlite_database():
    db_path = get_db_path()
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    cursor = connection.cursor()

    # Examinations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            duration INTEGER NOT NULL,
            total_marks INTEGER NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Questions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            marks INTEGER DEFAULT 1,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
        )
    """)

    # Student submissions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_email TEXT NOT NULL,
            exam_id INTEGER NOT NULL,
            score INTEGER DEFAULT 0,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
            UNIQUE(student_email, exam_id)
        )
    """)

    # Track when a student starts an examination
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exam_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_email TEXT NOT NULL,
            exam_id INTEGER NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
            UNIQUE(student_email, exam_id)
        )
    """)

    # Student question-by-question answers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submission_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            selected_option TEXT,
            is_correct INTEGER DEFAULT 0,
            marks_awarded INTEGER DEFAULT 0,
            FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
        )
    """)

    connection.commit()
    connection.close()


def initialize_mysql_database():
    if not HAS_PYMYSQL:
        raise ImportError("PyMySQL is required for MySQL initialization.")

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            subject VARCHAR(255) NOT NULL,
            duration INT NOT NULL,
            total_marks INT NOT NULL,
            description TEXT,
            status VARCHAR(50) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            exam_id INT NOT NULL,
            question_text TEXT NOT NULL,
            option_a VARCHAR(255) NOT NULL,
            option_b VARCHAR(255) NOT NULL,
            option_c VARCHAR(255) NOT NULL,
            option_d VARCHAR(255) NOT NULL,
            correct_answer VARCHAR(10) NOT NULL,
            marks INT DEFAULT 1,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_email VARCHAR(255) NOT NULL,
            exam_id INT NOT NULL,
            score INT DEFAULT 0,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
            UNIQUE KEY uq_student_exam (student_email, exam_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exam_attempts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_email VARCHAR(255) NOT NULL,
            exam_id INT NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
            UNIQUE KEY uq_attempt_student_exam (student_email, exam_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submission_answers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            submission_id INT NOT NULL,
            question_id INT NOT NULL,
            selected_option VARCHAR(10),
            is_correct INT DEFAULT 0,
            marks_awarded INT DEFAULT 0,
            FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    connection.commit()
    connection.close()


def get_db_info():
    """Returns database connection metadata (sanitized)."""
    if get_db_type() == "mysql":
        cfg = get_mysql_config()
        return {
            "type": "MySQL",
            "host": cfg["host"],
            "port": cfg["port"],
            "user": cfg["user"],
            "database": cfg["database"]
        }
    return {
        "type": "SQLite",
        "path": get_db_path()
    }


if __name__ == "__main__":
    initialize_database()
    print(f"ExamVault {get_db_type().upper()} database initialized successfully!")
