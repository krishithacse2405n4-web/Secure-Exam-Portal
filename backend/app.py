
from flask import (
    Flask, render_template, jsonify, request,
    redirect, url_for, session, flash
)
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import os
import sys

# --------------------------------------------------
# PROJECT CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.database import get_db_connection, initialize_database

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "frontend" / "templates"),
    static_folder=str(BASE_DIR / "frontend" / "static")
)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "dev-only-change-this"
)

initialize_database()


# --------------------------------------------------
# DEMO USERS
# --------------------------------------------------

users = {
    "student@example.com": {
        "password": generate_password_hash("Student@123"),
        "role": "student"
    },
    "admin@example.com": {
        "password": generate_password_hash("Admin@123"),
        "role": "admin"
    }
}


# --------------------------------------------------
# TIMESTAMP HELPER
# SQLite CURRENT_TIMESTAMP is stored in UTC.
# --------------------------------------------------

def get_started_datetime(started_at):
    if isinstance(started_at, datetime):
        value = started_at
    else:
        raw_str = str(started_at).strip()
        try:
            value = datetime.fromisoformat(raw_str)
        except ValueError:
            try:
                value = datetime.strptime(raw_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                value = datetime.strptime(raw_str, "%Y-%m-%d %H:%M:%S.%f")

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.route("/")
def home():
    return render_template("login.html")


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.route("/health")
def health():
    db_status = "healthy"
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    code = 200 if db_status == "healthy" else 503
    return jsonify({
        "status": "success" if db_status == "healthy" else "degraded",
        "message": "Exam Portal Backend is running",
        "database": db_status
    }), code


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/api/login", methods=["POST"])
def login():

    data = request.get_json(silent=True) or {}

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    role = data.get("role", "")

    user = users.get(email)

    if not user or not check_password_hash(user["password"], password):
        return jsonify({"message": "Invalid email or password"}), 401

    if user["role"] != role:
        return jsonify({"message": "Incorrect account type"}), 403

    session.clear()
    session["email"] = email
    session["role"] = role

    destination = "/student" if role == "student" else "/admin"

    return jsonify({
        "message": "Login successful",
        "redirect": destination
    })


# --------------------------------------------------
# STUDENT DASHBOARD
# --------------------------------------------------

@app.route("/student")
def student_dashboard():

    if session.get("role") != "student":
        return redirect(url_for("home"))

    email = session.get("email")
    connection = get_db_connection()

    try:
        exams = connection.execute(
            """
            SELECT
                e.*,
                s.id AS submission_id,
                s.score AS student_score,
                s.submitted_at,
                ea.id AS attempt_id
            FROM exams e
            LEFT JOIN submissions s
                ON e.id = s.exam_id
                AND s.student_email = ?
            LEFT JOIN exam_attempts ea
                ON e.id = ea.exam_id
                AND ea.student_email = ?
            WHERE LOWER(TRIM(e.status)) = 'active'
            ORDER BY e.id DESC
            """,
            (email, email)
        ).fetchall()

        completed_count = sum(
            1 for exam in exams
            if exam["submission_id"] is not None
        )

        total_count = len(exams)
        pending_count = total_count - completed_count

        recent_results = connection.execute(
            """
            SELECT
                s.id AS submission_id,
                e.id AS exam_id,
                e.title,
                e.subject,
                s.score,
                (
                    SELECT COALESCE(SUM(q.marks), e.total_marks)
                    FROM questions q
                    WHERE q.exam_id = e.id
                ) AS total_marks,
                s.submitted_at
            FROM submissions s
            JOIN exams e ON e.id = s.exam_id
            WHERE s.student_email = ?
            ORDER BY s.submitted_at DESC
            LIMIT 5
            """,
            (email,)
        ).fetchall()

        average_score = 0

        if recent_results:
            percentages = [
                (result["score"] / result["total_marks"]) * 100
                for result in recent_results
                if result["total_marks"] > 0
            ]

            if percentages:
                average_score = round(
                    sum(percentages) / len(percentages)
                )

    finally:
        connection.close()

    return render_template(
        "student_dashboard.html",
        email=email,
        exams=exams,
        total_count=total_count,
        completed_count=completed_count,
        pending_count=pending_count,
        average_score=average_score,
        recent_results=recent_results
    )


# --------------------------------------------------
# STUDENT AVAILABLE EXAMINATIONS
# --------------------------------------------------

@app.route("/student/exams")
def student_exams():

    if session.get("role") != "student":
        return redirect(url_for("home"))

    email = session.get("email")
    connection = get_db_connection()

    try:
        exams = connection.execute(
            """
            SELECT
                exams.id,
                exams.title,
                exams.subject,
                exams.duration,
                exams.total_marks,
                exams.description,
                exams.status,
                exams.created_at,
                submissions.id AS submission_id,
                exam_attempts.id AS attempt_id
            FROM exams
            LEFT JOIN submissions
                ON exams.id = submissions.exam_id
                AND submissions.student_email = ?
            LEFT JOIN exam_attempts
                ON exams.id = exam_attempts.exam_id
                AND exam_attempts.student_email = ?
            WHERE LOWER(TRIM(exams.status)) = 'active'
            ORDER BY exams.id DESC
            """,
            (email, email)
        ).fetchall()

    finally:
        connection.close()

    return render_template(
        "available_exams.html",
        exams=exams,
        email=email
    )


# --------------------------------------------------
# EXAMINATION INSTRUCTIONS
# --------------------------------------------------

@app.route("/student/exam/<int:exam_id>/instructions")
def exam_instructions(exam_id):

    if session.get("role") != "student":
        return redirect(url_for("home"))

    email = session.get("email")
    connection = get_db_connection()

    try:
        exam = connection.execute(
            """
            SELECT * FROM exams
            WHERE id = ? AND LOWER(TRIM(status)) = 'active'
            """,
            (exam_id,)
        ).fetchone()

        if exam is None:
            flash("Examination not found or inactive.", "error")
            return redirect(url_for("student_exams"))

        # Check existing submission
        submission = connection.execute(
            """
            SELECT id, score, submitted_at FROM submissions
            WHERE student_email = ? AND exam_id = ?
            """,
            (email, exam_id)
        ).fetchone()

        # Check existing attempt
        attempt = connection.execute(
            """
            SELECT * FROM exam_attempts
            WHERE student_email = ? AND exam_id = ?
            """,
            (email, exam_id)
        ).fetchone()

        # Count questions and sum marks
        q_stats = connection.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(marks), 0)
            FROM questions WHERE exam_id = ?
            """,
            (exam_id,)
        ).fetchone()

        total_questions = q_stats[0]
        total_marks = q_stats[1] if q_stats[1] > 0 else exam["total_marks"]

        is_submitted = submission is not None
        submission_id = submission["id"] if is_submitted else None
        submission_time = submission["submitted_at"] if is_submitted else None

        is_in_progress = False
        remaining_minutes = 0
        remaining_seconds_mod = 0
        attempt_time = None

        if attempt and not is_submitted:
            started_at = get_started_datetime(attempt["started_at"])
            current_time = datetime.now(timezone.utc)
            elapsed_seconds = (current_time - started_at).total_seconds()
            duration_seconds = exam["duration"] * 60
            remaining_seconds = max(0, int(duration_seconds - elapsed_seconds))

            if remaining_seconds > 0:
                is_in_progress = True
                remaining_minutes = remaining_seconds // 60
                remaining_seconds_mod = remaining_seconds % 60
                attempt_time = started_at.strftime("%Y-%m-%d %H:%M:%S UTC")

    finally:
        connection.close()

    return render_template(
        "exam_instructions.html",
        exam=exam,
        total_questions=total_questions,
        total_marks=total_marks,
        is_submitted=is_submitted,
        submission_id=submission_id,
        submission_time=submission_time,
        is_in_progress=is_in_progress,
        remaining_minutes=remaining_minutes,
        remaining_seconds_mod=remaining_seconds_mod,
        attempt_time=attempt_time
    )


# --------------------------------------------------
# START, RESUME AND SUBMIT EXAMINATION
# --------------------------------------------------

@app.route("/student/exam/<int:exam_id>", methods=["GET", "POST"])
def take_exam(exam_id):

    if session.get("role") != "student":
        return redirect(url_for("home"))

    email = session.get("email")
    connection = get_db_connection()

    try:

        exam = connection.execute(
            """
            SELECT *
            FROM exams
            WHERE id = ?
            AND LOWER(TRIM(status)) = 'active'
            """,
            (exam_id,)
        ).fetchone()

        if exam is None:
            flash("Examination not found or inactive.", "error")
            return redirect(url_for("student_exams"))

        # Check whether the examination was already submitted.
        submission = connection.execute(
            """
            SELECT id
            FROM submissions
            WHERE student_email = ?
            AND exam_id = ?
            """,
            (email, exam_id)
        ).fetchone()

        if submission:
            return redirect(
                url_for(
                    "exam_result",
                    submission_id=submission["id"]
                )
            )

        # Fetch questions without exposing correct answers.
        questions = connection.execute(
            """
            SELECT
                id,
                question_text,
                option_a,
                option_b,
                option_c,
                option_d,
                marks
            FROM questions
            WHERE exam_id = ?
            ORDER BY id
            """,
            (exam_id,)
        ).fetchall()

        if not questions:
            flash(
                "This examination does not have any questions yet.",
                "error"
            )
            return redirect(url_for("student_exams"))

        # Find or create attempt
        attempt = connection.execute(
            """
            SELECT *
            FROM exam_attempts
            WHERE student_email = ?
            AND exam_id = ?
            """,
            (email, exam_id)
        ).fetchone()

        # Start or resume the examination
        if request.method == "GET":

            if attempt is None:

                connection.execute(
                    """
                    INSERT INTO exam_attempts
                    (student_email, exam_id)
                    VALUES (?, ?)
                    """,
                    (email, exam_id)
                )

                connection.commit()

                attempt = connection.execute(
                    """
                    SELECT *
                    FROM exam_attempts
                    WHERE student_email = ?
                    AND exam_id = ?
                    """,
                    (email, exam_id)
                ).fetchone()

            started_at = get_started_datetime(
                attempt["started_at"]
            )

            current_time = datetime.now(timezone.utc)

            elapsed_seconds = (
                current_time - started_at
            ).total_seconds()

            duration_seconds = exam["duration"] * 60

            remaining_seconds = max(
                0,
                int(duration_seconds - elapsed_seconds)
            )

            if remaining_seconds <= 0:
                cursor = connection.execute(
                    """
                    INSERT INTO submissions
                    (student_email, exam_id, score)
                    VALUES (?, ?, 0)
                    """,
                    (email, exam_id)
                )
                connection.commit()
                flash("Examination duration has expired.", "error")
                return redirect(url_for("exam_result", submission_id=cursor.lastrowid))

            maximum_score = sum(
                question["marks"] for question in questions
            )

            return render_template(
                "take_exam.html",
                exam=exam,
                questions=questions,
                remaining_seconds=remaining_seconds,
                maximum_score=maximum_score
            )

        # --------------------------------------------------
        # SUBMIT EXAMINATION (POST)
        # --------------------------------------------------

        if attempt is None:
            return "No examination attempt was found.", 400

        started_at = get_started_datetime(
            attempt["started_at"]
        )

        current_time = datetime.now(timezone.utc)

        elapsed_seconds = (
            current_time - started_at
        ).total_seconds()

        duration_seconds = exam["duration"] * 60
        is_timed_out = elapsed_seconds > (duration_seconds + 30)

        # Evaluate submitted answers on the server.
        answer_rows = connection.execute(
            """
            SELECT id, correct_answer, marks
            FROM questions
            WHERE exam_id = ?
            ORDER BY id
            """,
            (exam_id,)
        ).fetchall()

        score = 0
        answers_to_store = []

        for question in answer_rows:
            qid = question["id"]
            correct = question["correct_answer"].strip().upper()
            selected = request.form.get(
                f"answer_{qid}", ""
            ).strip().upper()

            if not is_timed_out and selected == correct:
                marks_awarded = question["marks"]
                is_correct = 1
                score += marks_awarded
            else:
                marks_awarded = 0
                is_correct = 0

            answers_to_store.append({
                "question_id": qid,
                "selected_option": selected if selected else None,
                "is_correct": is_correct,
                "marks_awarded": marks_awarded
            })

        if is_timed_out:
            score = 0

        cursor = connection.execute(
            """
            INSERT INTO submissions
            (student_email, exam_id, score)
            VALUES (?, ?, ?)
            """,
            (email, exam_id, score)
        )

        submission_id = cursor.lastrowid

        for ans in answers_to_store:
            connection.execute(
                """
                INSERT INTO submission_answers
                (submission_id, question_id, selected_option, is_correct, marks_awarded)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    submission_id,
                    ans["question_id"],
                    ans["selected_option"],
                    ans["is_correct"],
                    ans["marks_awarded"]
                )
            )

        connection.commit()

        return redirect(
            url_for(
                "exam_result",
                submission_id=submission_id
            )
        )

    except Exception:

        connection.rollback()

        app.logger.exception(
            "Error processing examination"
        )

        return "An error occurred while processing the examination.", 500

    finally:
        connection.close()


# --------------------------------------------------
# STUDENT EXAMINATION RESULT
# --------------------------------------------------

@app.route("/student/result/<int:submission_id>")
def exam_result(submission_id):

    current_role = session.get("role")
    current_email = session.get("email")

    if not current_role:
        return redirect(url_for("home"))

    connection = get_db_connection()

    try:
        if current_role == "admin":
            result = connection.execute(
                """
                SELECT
                    s.id,
                    s.student_email,
                    s.score,
                    s.submitted_at,
                    e.id AS exam_id,
                    e.title,
                    e.subject,
                    e.total_marks,
                    (
                        SELECT COALESCE(SUM(q.marks), e.total_marks)
                        FROM questions q
                        WHERE q.exam_id = e.id
                    ) AS maximum_score
                FROM submissions s
                JOIN exams e ON e.id = s.exam_id
                WHERE s.id = ?
                """,
                (submission_id,)
            ).fetchone()
        else:
            result = connection.execute(
                """
                SELECT
                    s.id,
                    s.student_email,
                    s.score,
                    s.submitted_at,
                    e.id AS exam_id,
                    e.title,
                    e.subject,
                    e.total_marks,
                    (
                        SELECT COALESCE(SUM(q.marks), e.total_marks)
                        FROM questions q
                        WHERE q.exam_id = e.id
                    ) AS maximum_score
                FROM submissions s
                JOIN exams e ON e.id = s.exam_id
                WHERE s.id = ?
                AND s.student_email = ?
                """,
                (submission_id, current_email)
            ).fetchone()

        if result is None:
            return "Result not found.", 404

        answer_details = connection.execute(
            """
            SELECT
                q.id,
                q.question_text,
                q.option_a,
                q.option_b,
                q.option_c,
                q.option_d,
                q.correct_answer,
                q.marks,
                sa.selected_option,
                sa.is_correct,
                sa.marks_awarded
            FROM questions q
            LEFT JOIN submission_answers sa
                ON q.id = sa.question_id
                AND sa.submission_id = ?
            WHERE q.exam_id = ?
            ORDER BY q.id
            """,
            (result["id"], result["exam_id"])
        ).fetchall()

        # Calculate time taken from attempt to submission
        time_taken = "N/A"
        attempt = connection.execute(
            """
            SELECT started_at FROM exam_attempts
            WHERE student_email = ? AND exam_id = ?
            """,
            (result["student_email"], result["exam_id"])
        ).fetchone()

        if attempt and result["submitted_at"]:
            try:
                start_dt = get_started_datetime(attempt["started_at"])
                submit_dt = get_started_datetime(result["submitted_at"])
                diff = max(0, int((submit_dt - start_dt).total_seconds()))
                mins = diff // 60
                secs = diff % 60
                time_taken = f"{mins} min {secs} sec"
            except Exception:
                time_taken = "Recorded"

    finally:
        connection.close()

    maximum_score = result["maximum_score"] if result["maximum_score"] > 0 else 1
    percentage = round((result["score"] / maximum_score) * 100, 1)
    status = "PASS" if percentage >= 40 else "FAIL"

    total_questions = len(answer_details)
    correct_count = sum(1 for a in answer_details if a["is_correct"] == 1)
    attempted_count = sum(1 for a in answer_details if a["selected_option"])
    incorrect_count = attempted_count - correct_count

    return render_template(
        "exam_result.html",
        result=result,
        percentage=percentage,
        status=status,
        total_questions=total_questions,
        correct_count=correct_count,
        incorrect_count=incorrect_count,
        time_taken=time_taken,
        answer_details=answer_details
    )

# --------------------------------------------------
# ADMIN DASHBOARD
# --------------------------------------------------


@app.route("/admin")
def admin_dashboard():

    if session.get("role") != "admin":
        return redirect(url_for("home"))

    connection = get_db_connection()

    try:
        total_exams = connection.execute(
            "SELECT COUNT(*) FROM exams"
        ).fetchone()[0]

        active_exams = connection.execute(
            "SELECT COUNT(*) FROM exams WHERE LOWER(TRIM(status)) = 'active'"
        ).fetchone()[0]

        total_submissions = connection.execute(
            "SELECT COUNT(*) FROM submissions"
        ).fetchone()[0]

        total_students_res = connection.execute(
            """
            SELECT COUNT(DISTINCT student_email)
            FROM (
                SELECT student_email FROM submissions
                UNION
                SELECT student_email FROM exam_attempts
            ) AS unique_students
            """
        ).fetchone()[0]

        total_students = max(total_students_res, 1)

        pending_attempts = connection.execute(
            """
            SELECT COUNT(*) FROM exam_attempts ea
            LEFT JOIN submissions s
                ON ea.exam_id = s.exam_id
                AND ea.student_email = s.student_email
            WHERE s.id IS NULL
            """
        ).fetchone()[0]

        exams = connection.execute(
            """
            SELECT
                e.id,
                e.title,
                e.subject,
                e.duration,
                e.total_marks,
                e.status,
                e.created_at,
                (SELECT COUNT(*) FROM questions q
                 WHERE q.exam_id = e.id) AS question_count,
                (SELECT COUNT(*) FROM submissions s
                 WHERE s.exam_id = e.id) AS submission_count
            FROM exams e
            ORDER BY e.id DESC
            """
        ).fetchall()

    finally:
        connection.close()

    return render_template(
        "admin_dashboard.html",
        total_students=total_students,
        total_exams=total_exams,
        active_exams=active_exams,
        total_submissions=total_submissions,
        pending_attempts=pending_attempts,
        exams=exams
    )


# --------------------------------------------------
# CREATE EXAMINATION
# --------------------------------------------------

@app.route("/admin/create-exam", methods=["GET", "POST"])
def create_exam():

    if session.get("role") != "admin":
        return redirect(url_for("home"))

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()

        try:
            duration = int(request.form.get("duration", 0))
            total_marks = int(request.form.get("total_marks", 0))

        except ValueError:
            flash("Please enter valid numbers.", "error")
            return redirect(url_for("create_exam"))

        if (
            not title
            or not subject
            or duration <= 0
            or total_marks <= 0
        ):
            flash(
                "Please enter all required details correctly.",
                "error"
            )
            return redirect(url_for("create_exam"))

        connection = get_db_connection()

        try:
            connection.execute(
                """
                INSERT INTO exams
                (title, subject, duration, total_marks, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    title,
                    subject,
                    duration,
                    total_marks,
                    description
                )
            )

            connection.commit()

            flash(
                "Examination created successfully!",
                "success"
            )

        except Exception:
            connection.rollback()
            flash("Unable to create examination.", "error")

        finally:
            connection.close()

        return redirect(url_for("create_exam"))

    return render_template("create_exam.html")


# --------------------------------------------------
# MANAGE EXAMINATIONS
# --------------------------------------------------

@app.route("/admin/exams")
def manage_exams():

    if session.get("role") != "admin":
        return redirect(url_for("home"))

    connection = get_db_connection()

    try:
        exams = connection.execute(
            """
            SELECT
                e.*,
                (SELECT COUNT(*) FROM questions q WHERE q.exam_id = e.id) AS question_count,
                (SELECT COUNT(*) FROM submissions s WHERE s.exam_id = e.id) AS submission_count
            FROM exams e
            ORDER BY e.created_at DESC
            """
        ).fetchall()

    finally:
        connection.close()

    return render_template(
        "manage_exams.html",
        exams=exams
    )


# --------------------------------------------------
# EDIT EXAMINATION
# --------------------------------------------------

@app.route("/admin/exams/<int:exam_id>/edit", methods=["GET", "POST"])
def edit_exam(exam_id):

    if session.get("role") != "admin":
        return redirect(url_for("home"))

    connection = get_db_connection()

    try:
        exam = connection.execute(
            "SELECT * FROM exams WHERE id = ?",
            (exam_id,)
        ).fetchone()

        if exam is None:
            flash("Examination not found.", "error")
            return redirect(url_for("manage_exams"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            subject = request.form.get("subject", "").strip()
            description = request.form.get("description", "").strip()
            status = request.form.get("status", "active").strip().lower()

            try:
                duration = int(request.form.get("duration", 0))
                total_marks = int(request.form.get("total_marks", 0))
            except ValueError:
                flash("Duration and Total Marks must be valid numbers.", "error")
                return redirect(url_for("edit_exam", exam_id=exam_id))

            if not title or not subject or duration <= 0 or total_marks <= 0:
                flash("Please complete all required fields with valid values.", "error")
                return redirect(url_for("edit_exam", exam_id=exam_id))

            if status not in ["active", "inactive"]:
                status = "active"

            connection.execute(
                """
                UPDATE exams
                SET title = ?, subject = ?, duration = ?, total_marks = ?, description = ?, status = ?
                WHERE id = ?
                """,
                (title, subject, duration, total_marks, description, status, exam_id)
            )
            connection.commit()
            flash(f"Examination '{title}' updated successfully!", "success")
            return redirect(url_for("manage_exams"))

    finally:
        connection.close()

    return render_template("edit_exam.html", exam=exam)


# --------------------------------------------------
# DELETE EXAMINATION
# --------------------------------------------------

@app.route("/admin/exams/<int:exam_id>/delete", methods=["POST"])
def delete_exam(exam_id):

    if session.get("role") != "admin":
        return redirect(url_for("home"))

    connection = get_db_connection()

    try:
        exam = connection.execute(
            "SELECT title FROM exams WHERE id = ?",
            (exam_id,)
        ).fetchone()

        if exam is None:
            flash("Examination not found.", "error")
            return redirect(url_for("manage_exams"))

        exam_title = exam["title"]

        # Cascade delete dependent rows
        connection.execute(
            """
            DELETE FROM submission_answers
            WHERE submission_id IN (SELECT id FROM submissions WHERE exam_id = ?)
            """,
            (exam_id,)
        )
        connection.execute("DELETE FROM submissions WHERE exam_id = ?", (exam_id,))
        connection.execute("DELETE FROM exam_attempts WHERE exam_id = ?", (exam_id,))
        connection.execute("DELETE FROM questions WHERE exam_id = ?", (exam_id,))
        connection.execute("DELETE FROM exams WHERE id = ?", (exam_id,))

        connection.commit()
        flash(f"Examination '{exam_title}' and all related records deleted successfully.", "success")

    except Exception:
        connection.rollback()
        app.logger.exception("Error deleting examination")
        flash("An error occurred while deleting the examination.", "error")

    finally:
        connection.close()

    return redirect(url_for("manage_exams"))


# --------------------------------------------------
# ADD QUESTIONS TO AN EXAMINATION
# --------------------------------------------------

@app.route(
    "/admin/exams/<int:exam_id>/questions",
    methods=["GET", "POST"]
)
def manage_questions(exam_id):

    if session.get("role") != "admin":
        return redirect(url_for("home"))

    connection = get_db_connection()

    exam = connection.execute(
        "SELECT * FROM exams WHERE id = ?",
        (exam_id,)
    ).fetchone()

    if exam is None:
        connection.close()
        return "Examination not found.", 404

    if request.method == "POST":

        question_text = request.form.get(
            "question_text", ""
        ).strip()

        option_a = request.form.get("option_a", "").strip()
        option_b = request.form.get("option_b", "").strip()
        option_c = request.form.get("option_c", "").strip()
        option_d = request.form.get("option_d", "").strip()

        correct_answer = request.form.get(
            "correct_answer", ""
        ).strip().upper()

        try:
            marks = int(request.form.get("marks", 1))

        except ValueError:
            marks = 0

        if (
            not all([
                question_text,
                option_a,
                option_b,
                option_c,
                option_d
            ])
            or correct_answer not in ["A", "B", "C", "D"]
            or marks <= 0
        ):

            flash(
                "Please complete all fields with valid values.",
                "error"
            )

        else:

            try:
                connection.execute(
                    """
                    INSERT INTO questions
                    (
                        exam_id,
                        question_text,
                        option_a,
                        option_b,
                        option_c,
                        option_d,
                        correct_answer,
                        marks
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        exam_id,
                        question_text,
                        option_a,
                        option_b,
                        option_c,
                        option_d,
                        correct_answer,
                        marks
                    )
                )

                connection.commit()

                flash(
                    "Question added successfully!",
                    "success"
                )

            except Exception:
                connection.rollback()
                flash(
                    "Unable to save the question.",
                    "error"
                )

    questions = connection.execute(
        """
        SELECT
            id,
            question_text,
            option_a,
            option_b,
            option_c,
            option_d,
            correct_answer,
            marks
        FROM questions
        WHERE exam_id = ?
        ORDER BY id
        """,
        (exam_id,)
    ).fetchall()

    connection.close()

    return render_template(
        "add_questions.html",
        exam=exam,
        questions=questions
    )


# --------------------------------------------------
# EDIT QUESTION
# --------------------------------------------------

@app.route(
    "/admin/exams/<int:exam_id>/questions/<int:question_id>/edit",
    methods=["GET", "POST"]
)
def edit_question(exam_id, question_id):

    if session.get("role") != "admin":
        return redirect(url_for("home"))

    connection = get_db_connection()

    try:
        exam = connection.execute(
            "SELECT * FROM exams WHERE id = ?",
            (exam_id,)
        ).fetchone()

        question = connection.execute(
            "SELECT * FROM questions WHERE id = ? AND exam_id = ?",
            (question_id, exam_id)
        ).fetchone()

        if exam is None or question is None:
            flash("Question or Examination not found.", "error")
            return redirect(url_for("manage_questions", exam_id=exam_id))

        if request.method == "POST":
            question_text = request.form.get("question_text", "").strip()
            option_a = request.form.get("option_a", "").strip()
            option_b = request.form.get("option_b", "").strip()
            option_c = request.form.get("option_c", "").strip()
            option_d = request.form.get("option_d", "").strip()
            correct_answer = request.form.get("correct_answer", "").strip().upper()

            try:
                marks = int(request.form.get("marks", 1))
            except ValueError:
                marks = 0

            if (
                not all([question_text, option_a, option_b, option_c, option_d])
                or correct_answer not in ["A", "B", "C", "D"]
                or marks <= 0
            ):
                flash("Please fill in all options, select a valid answer key, and enter positive marks.", "error")
                return redirect(url_for("edit_question", exam_id=exam_id, question_id=question_id))

            connection.execute(
                """
                UPDATE questions
                SET question_text = ?, option_a = ?, option_b = ?, option_c = ?, option_d = ?, correct_answer = ?, marks = ?
                WHERE id = ? AND exam_id = ?
                """,
                (question_text, option_a, option_b, option_c, option_d, correct_answer, marks, question_id, exam_id)
            )
            connection.commit()
            flash("Question updated successfully!", "success")
            return redirect(url_for("manage_questions", exam_id=exam_id))

    finally:
        connection.close()

    return render_template("edit_question.html", exam=exam, question=question)


# --------------------------------------------------
# DELETE QUESTION
# --------------------------------------------------

@app.route(
    "/admin/exams/<int:exam_id>/questions/<int:question_id>/delete",
    methods=["POST"]
)
def delete_question(exam_id, question_id):

    if session.get("role") != "admin":
        return redirect(url_for("home"))

    connection = get_db_connection()

    try:
        connection.execute(
            "DELETE FROM submission_answers WHERE question_id = ?",
            (question_id,)
        )
        connection.execute(
            "DELETE FROM questions WHERE id = ? AND exam_id = ?",
            (question_id, exam_id)
        )
        connection.commit()
        flash("Question deleted successfully.", "success")

    except Exception:
        connection.rollback()
        flash("Unable to delete question.", "error")

    finally:
        connection.close()

    return redirect(url_for("manage_questions", exam_id=exam_id))


# --------------------------------------------------
# ADMIN RESULTS VIEW
# --------------------------------------------------

@app.route("/admin/results")
def admin_results():

    if session.get("role") != "admin":
        return redirect(url_for("home"))

    selected_exam_id = request.args.get("exam_id", type=int)
    connection = get_db_connection()

    try:
        exams = connection.execute(
            "SELECT id, title, subject FROM exams ORDER BY title ASC"
        ).fetchall()

        base_sql = """
            SELECT
                s.id,
                s.student_email,
                s.score,
                s.submitted_at,
                e.id AS exam_id,
                e.title AS exam_title,
                e.subject,
                (
                    SELECT COALESCE(SUM(q.marks), e.total_marks)
                    FROM questions q WHERE q.exam_id = e.id
                ) AS maximum_score
            FROM submissions s
            JOIN exams e ON e.id = s.exam_id
        """

        if selected_exam_id:
            raw_subs = connection.execute(
                base_sql + " WHERE s.exam_id = ? ORDER BY s.submitted_at DESC",
                (selected_exam_id,)
            ).fetchall()
        else:
            raw_subs = connection.execute(
                base_sql + " ORDER BY s.submitted_at DESC"
            ).fetchall()

        submissions = []
        passed_count = 0
        total_percent_sum = 0

        for r in raw_subs:
            max_sc = r["maximum_score"] if r["maximum_score"] > 0 else 1
            pct = round((r["score"] / max_sc) * 100, 1)
            if pct >= 40:
                passed_count += 1
            total_percent_sum += pct

            submissions.append({
                "id": r["id"],
                "student_email": r["student_email"],
                "score": r["score"],
                "maximum_score": max_sc,
                "percentage": pct,
                "submitted_at": r["submitted_at"],
                "exam_id": r["exam_id"],
                "exam_title": r["exam_title"],
                "subject": r["subject"]
            })

        avg_percent = round(total_percent_sum / len(submissions), 1) if submissions else 0

    finally:
        connection.close()

    return render_template(
        "admin_results.html",
        submissions=submissions,
        exams=exams,
        selected_exam_id=selected_exam_id,
        passed_count=passed_count,
        avg_percent=avg_percent
    )


# --------------------------------------------------
# ADMIN STUDENTS VIEW
# --------------------------------------------------


@app.route("/admin/students")
def admin_students():

    if session.get("role") != "admin":
        return redirect(url_for("home"))

    connection = get_db_connection()

    try:
        student_rows = connection.execute(
            """
            SELECT DISTINCT student_email
            FROM (
                SELECT student_email FROM submissions
                UNION
                SELECT student_email FROM exam_attempts
            ) AS unique_students
            """
        ).fetchall()

        emails = [r["student_email"] for r in student_rows]

        if "student@example.com" not in emails:
            emails.append("student@example.com")

        students = []
        total_completed_tests = 0
        all_percentages = []

        for email in emails:

            attempts_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM exam_attempts
                WHERE student_email = ?
                """,
                (email,)
            ).fetchone()[0]

            subs = connection.execute(
                """
                SELECT
                    s.score,
                    (
                        SELECT COALESCE(SUM(q.marks), e.total_marks)
                        FROM questions q
                        WHERE q.exam_id = e.id
                    ) AS maximum_score,
                    s.submitted_at
                FROM submissions s
                JOIN exams e ON e.id = s.exam_id
                WHERE s.student_email = ?
                ORDER BY s.submitted_at DESC
                """,
                (email,)
            ).fetchall()

            completed_count = len(subs)
            total_completed_tests += completed_count

            last_active = subs[0]["submitted_at"] if subs else None

            if not last_active:
                att = connection.execute(
                    """
                    SELECT started_at
                    FROM exam_attempts
                    WHERE student_email = ?
                    ORDER BY started_at DESC
                    LIMIT 1
                    """,
                    (email,)
                ).fetchone()

                if att:
                    last_active = att["started_at"]

            student_percentages = [
                (s["score"] / s["maximum_score"]) * 100
                for s in subs
                if s["maximum_score"] > 0
            ]

            avg_pct = (
                round(sum(student_percentages) / len(student_percentages), 1)
                if student_percentages else 0
            )

            all_percentages.extend(student_percentages)

            students.append({
                "email": email,
                "attempts_count": max(attempts_count, completed_count),
                "completed_count": completed_count,
                "average_percentage": avg_pct,
                "last_active": last_active
            })

        overall_avg = (
            round(sum(all_percentages) / len(all_percentages), 1)
            if all_percentages else 0
        )

    finally:
        connection.close()

    return render_template(
        "admin_students.html",
        students=students,
        total_completed_tests=total_completed_tests,
        overall_avg=overall_avg
    )


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5003,
        debug=True
    )
