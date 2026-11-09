-- ExamVault MySQL Database Initialization Script
-- Executed automatically by MySQL container entrypoint on first startup

CREATE DATABASE IF NOT EXISTS examvault CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE examvault;

-- 1. Examinations Table
CREATE TABLE IF NOT EXISTS exams (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    duration INT NOT NULL,
    total_marks INT NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. MCQ Questions Table
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Student Submissions Table
CREATE TABLE IF NOT EXISTS submissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_email VARCHAR(255) NOT NULL,
    exam_id INT NOT NULL,
    score INT DEFAULT 0,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    UNIQUE KEY uq_student_exam (student_email, exam_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Exam Attempts Table (Timer tracking)
CREATE TABLE IF NOT EXISTS exam_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_email VARCHAR(255) NOT NULL,
    exam_id INT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    UNIQUE KEY uq_attempt_student_exam (student_email, exam_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Question-by-Question Recorded Answers Table
CREATE TABLE IF NOT EXISTS submission_answers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    submission_id INT NOT NULL,
    question_id INT NOT NULL,
    selected_option VARCHAR(10),
    is_correct INT DEFAULT 0,
    marks_awarded INT DEFAULT 0,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------
-- Seed Initial Demonstrational Data
-- ----------------------------------------------------
INSERT INTO exams (id, title, subject, duration, total_marks, description, status)
VALUES
    (1, 'Python Programming Test', 'Python', 60, 100, 'Comprehensive Python assessment testing core syntax, data structures, and functions.', 'active'),
    (2, 'Data Structures Test 1', 'Data Structures', 45, 50, 'Standard assessment covering arrays, linked lists, stacks, and queues.', 'active'),
    (3, 'DevOps & Cloud Engineering Midterm', 'DevOps', 60, 50, 'Midterm evaluation on Docker containers, CI/CD pipelines, and configuration management.', 'active')
ON DUPLICATE KEY UPDATE title=VALUES(title);

INSERT INTO questions (id, exam_id, question_text, option_a, option_b, option_c, option_d, correct_answer, marks)
VALUES
    (1, 3, 'Which keyword is used to define a function in Python?', 'function', 'def', 'define', 'fun', 'B', 10),
    (2, 3, 'What is the primary command used to build a Docker image from a Dockerfile?', 'docker create', 'docker run', 'docker build', 'docker compose', 'C', 10),
    (3, 3, 'Which Ansible file maps hostnames and IP addresses into groups?', 'playbook.yml', 'inventory.ini', 'ansible.cfg', 'docker-compose.yml', 'B', 10),
    (4, 1, 'Which of the following data structures is immutable in Python?', 'List', 'Dictionary', 'Set', 'Tuple', 'D', 20),
    (5, 1, 'What will be the output of type([]) in Python 3?', '<class \'list\'>', '<type \'list\'>', '<list>', 'list', 'A', 20)
ON DUPLICATE KEY UPDATE question_text=VALUES(question_text);
