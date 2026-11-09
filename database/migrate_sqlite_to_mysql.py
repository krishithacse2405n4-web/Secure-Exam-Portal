#!/usr/bin/env python3
"""
ExamVault - SQLite to MySQL Migration Utility
Migrates all examinations, questions, student attempts, submissions, and answers
from the existing SQLite database into MySQL while preserving relational integrity.
"""

import os
import sys
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.database import (
    get_db_path, get_mysql_config,
    initialize_mysql_database, get_db_connection
)

try:
    import pymysql
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False


def migrate():
    print("=" * 60)
    print("ExamVault: SQLite -> MySQL Migration")
    print("=" * 60)

    if not HAS_PYMYSQL:
        print("[ERROR] PyMySQL is not installed. Run: pip install PyMySQL")
        sys.exit(1)

    sqlite_file = Path(get_db_path())
    if not sqlite_file.exists():
        print(f"[ERROR] SQLite database file not found at: {sqlite_file}")
        sys.exit(1)

    print(f"[1/4] Reading data from SQLite: {sqlite_file}")
    sqlite_conn = sqlite3.connect(sqlite_file)
    sqlite_conn.row_factory = sqlite3.Row
    s_cur = sqlite_conn.cursor()

    exams = s_cur.execute("SELECT * FROM exams ORDER BY id").fetchall()
    questions = s_cur.execute("SELECT * FROM questions ORDER BY id").fetchall()
    attempts = s_cur.execute("SELECT * FROM exam_attempts ORDER BY id").fetchall()
    submissions = s_cur.execute("SELECT * FROM submissions ORDER BY id").fetchall()
    answers = s_cur.execute("SELECT * FROM submission_answers ORDER BY id").fetchall()

    print(f"      - Found {len(exams)} examination(s)")
    print(f"      - Found {len(questions)} question(s)")
    print(f"      - Found {len(attempts)} attempt(s)")
    print(f"      - Found {len(submissions)} submission(s)")
    print(f"      - Found {len(answers)} recorded answer(s)")

    cfg = get_mysql_config()
    print(f"[2/4] Connecting to MySQL ({cfg['host']}:{cfg['port']}/{cfg['database']}) as '{cfg['user']}'...")
    try:
        mysql_conn = pymysql.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            charset="utf8mb4",
            autocommit=False
        )
    except Exception as e:
        print(f"[ERROR] Could not connect to MySQL: {e}")
        print("Please check your environment variables: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME")
        sys.exit(1)

    m_cur = mysql_conn.cursor()

    print("[3/4] Ensuring MySQL schema exists...")
    os.environ["DB_TYPE"] = "mysql"
    initialize_mysql_database()

    print("[4/4] Inserting data into MySQL...")
    try:
        # Disable foreign key checks during migration
        m_cur.execute("SET FOREIGN_KEY_CHECKS = 0;")

        # Migrate exams
        for exam in exams:
            m_cur.execute("""
                INSERT INTO exams (id, title, subject, duration, total_marks, description, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title=VALUES(title), subject=VALUES(subject), duration=VALUES(duration),
                    total_marks=VALUES(total_marks), description=VALUES(description), status=VALUES(status);
            """, (
                exam["id"], exam["title"], exam["subject"], exam["duration"],
                exam["total_marks"], exam["description"], exam["status"], exam["created_at"]
            ))

        # Migrate questions
        for q in questions:
            m_cur.execute("""
                INSERT INTO questions (id, exam_id, question_text, option_a, option_b, option_c, option_d, correct_answer, marks)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    question_text=VALUES(question_text), option_a=VALUES(option_a), option_b=VALUES(option_b),
                    option_c=VALUES(option_c), option_d=VALUES(option_d), correct_answer=VALUES(correct_answer),
                    marks=VALUES(marks);
            """, (
                q["id"], q["exam_id"], q["question_text"], q["option_a"],
                q["option_b"], q["option_c"], q["option_d"], q["correct_answer"], q["marks"]
            ))

        # Migrate attempts
        for a in attempts:
            m_cur.execute("""
                INSERT INTO exam_attempts (id, student_email, exam_id, started_at)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE started_at=VALUES(started_at);
            """, (a["id"], a["student_email"], a["exam_id"], a["started_at"]))

        # Migrate submissions
        for s in submissions:
            m_cur.execute("""
                INSERT INTO submissions (id, student_email, exam_id, score, submitted_at)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE score=VALUES(score), submitted_at=VALUES(submitted_at);
            """, (s["id"], s["student_email"], s["exam_id"], s["score"], s["submitted_at"]))

        # Migrate answers
        for ans in answers:
            m_cur.execute("""
                INSERT INTO submission_answers (id, submission_id, question_id, selected_option, is_correct, marks_awarded)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    selected_option=VALUES(selected_option), is_correct=VALUES(is_correct), marks_awarded=VALUES(marks_awarded);
            """, (
                ans["id"], ans["submission_id"], ans["question_id"],
                ans["selected_option"], ans["is_correct"], ans["marks_awarded"]
            ))

        m_cur.execute("SET FOREIGN_KEY_CHECKS = 1;")
        mysql_conn.commit()

        print("=" * 60)
        print("MIGRATION COMPLETED SUCCESSFULLY!")
        print("All exams, questions, and student submission data transferred to MySQL.")
        print("=" * 60)

    except Exception as e:
        mysql_conn.rollback()
        print(f"[ERROR] Migration failed: {e}")
        sys.exit(1)
    finally:
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    migrate()
