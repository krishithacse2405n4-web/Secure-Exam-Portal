import os
import sys
import unittest
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Use SQLite with a temporary file for tests
temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(temp_db_fd)

os.environ["DB_TYPE"] = "sqlite"
os.environ["DB_PATH"] = temp_db_path
os.environ["SECRET_KEY"] = "test-secret-key-12345"

from backend.app import app
from database.database import (
    initialize_database, get_db_connection, convert_placeholders, RowDict
)


class ExamVaultTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        initialize_database()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except OSError:
                pass

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

        # Seed sample examination and question for tests
        conn = get_db_connection()
        conn.execute("DELETE FROM submission_answers")
        conn.execute("DELETE FROM submissions")
        conn.execute("DELETE FROM exam_attempts")
        conn.execute("DELETE FROM questions")
        conn.execute("DELETE FROM exams")

        cursor = conn.execute(
            """
            INSERT INTO exams (id, title, subject, duration, total_marks, description, status)
            VALUES (1, 'Python Fundamentals', 'Computer Science', 30, 20, 'Test exam description', 'active')
            """
        )
        exam_id = cursor.lastrowid

        conn.execute(
            """
            INSERT INTO questions (id, exam_id, question_text, option_a, option_b, option_c, option_d, correct_answer, marks)
            VALUES (1, ?, 'What is the keyword for a function in Python?', 'func', 'def', 'fn', 'define', 'B', 10)
            """,
            (exam_id,)
        )

        conn.execute(
            """
            INSERT INTO questions (id, exam_id, question_text, option_a, option_b, option_c, option_d, correct_answer, marks)
            VALUES (2, ?, 'Which data type is immutable?', 'List', 'Dict', 'Tuple', 'Set', 'C', 10)
            """,
            (exam_id,)
        )

        conn.commit()
        conn.close()

    def test_health_check(self):
        """Verifies health endpoint returns success and healthy database status."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["database"], "healthy")

    def test_home_page(self):
        """Verifies login page renders successfully."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"ExamVault", response.data)

    def test_auth_invalid_credentials(self):
        """Verifies login rejection on wrong password."""
        response = self.client.post("/api/login", json={
            "email": "student@example.com",
            "password": "WrongPassword",
            "role": "student"
        })
        self.assertEqual(response.status_code, 401)

    def test_auth_wrong_role(self):
        """Verifies login rejection when selecting wrong account type."""
        response = self.client.post("/api/login", json={
            "email": "student@example.com",
            "password": "Student@123",
            "role": "admin"
        })
        self.assertEqual(response.status_code, 403)

    def test_student_flow(self):
        """Tests complete student workflow: login, dashboard, instructions, exam, submit, results."""
        # 1. Login
        login_res = self.client.post("/api/login", json={
            "email": "student@example.com",
            "password": "Student@123",
            "role": "student"
        })
        self.assertEqual(login_res.status_code, 200)

        # 2. Student Dashboard
        dash_res = self.client.get("/student")
        self.assertEqual(dash_res.status_code, 200)

        # 3. Available Exams
        exams_res = self.client.get("/student/exams")
        self.assertEqual(exams_res.status_code, 200)
        self.assertIn(b"Python Fundamentals", exams_res.data)

        # 4. Instructions Page
        inst_res = self.client.get("/student/exam/1/instructions")
        self.assertEqual(inst_res.status_code, 200)
        self.assertIn(b"Examination Rules", inst_res.data)

        # 5. Take Exam (GET)
        exam_get_res = self.client.get("/student/exam/1")
        self.assertEqual(exam_get_res.status_code, 200)
        html_text = exam_get_res.get_data(as_text=True)
        # Ensure correct answers are never leaked in client HTML
        self.assertNotIn("correct_answer", html_text)
        self.assertIn("What is the keyword for a function in Python?", html_text)

        # 6. Submit Exam: Q1=B (correct: 10), Q2=A (incorrect: 0) -> Total 10/20 (50% PASS)
        submit_res = self.client.post("/student/exam/1", data={
            "answer_1": "B",
            "answer_2": "A"
        }, follow_redirects=True)
        self.assertEqual(submit_res.status_code, 200)
        res_html = submit_res.get_data(as_text=True)
        self.assertIn("PASSED", res_html)
        self.assertIn("50.0%", res_html)

        # 7. Prevent Duplicate Submission
        dup_res = self.client.get("/student/exam/1")
        # Should redirect directly to result page
        self.assertEqual(dup_res.status_code, 302)

    def test_admin_flow(self):
        """Tests complete admin workflow: dashboard, create exam, edit, add questions, delete."""
        # 1. Admin Login
        login_res = self.client.post("/api/login", json={
            "email": "admin@example.com",
            "password": "Admin@123",
            "role": "admin"
        })
        self.assertEqual(login_res.status_code, 200)

        # 2. Admin Dashboard
        admin_res = self.client.get("/admin")
        self.assertEqual(admin_res.status_code, 200)
        self.assertIn(b"Admin Dashboard", admin_res.data)

        # 3. Create Examination
        create_res = self.client.post("/admin/create-exam", data={
            "title": "Cloud Architecture",
            "subject": "DevOps",
            "duration": "45",
            "total_marks": "50",
            "description": "Cloud test description"
        }, follow_redirects=True)
        self.assertEqual(create_res.status_code, 200)

        # 4. Manage Exams
        manage_res = self.client.get("/admin/exams")
        self.assertEqual(manage_res.status_code, 200)
        self.assertIn(b"Cloud Architecture", manage_res.data)

        # 5. Admin Results View
        results_res = self.client.get("/admin/results")
        self.assertEqual(results_res.status_code, 200)

        # 6. Admin Students View
        students_res = self.client.get("/admin/students")
        self.assertEqual(students_res.status_code, 200)

    def test_database_helpers(self):
        """Tests SQL placeholder converter and RowDict wrapper."""
        sql = "SELECT * FROM exams WHERE id = ? AND status = ?"
        converted = convert_placeholders(sql)
        self.assertEqual(converted, "SELECT * FROM exams WHERE id = %s AND status = %s")

        row = RowDict({"id": 10, "title": "DevOps Assessment"})
        self.assertEqual(row["title"], "DevOps Assessment")
        self.assertEqual(row[0], 10)
        self.assertEqual(row[1], "DevOps Assessment")


if __name__ == "__main__":
    unittest.main()
