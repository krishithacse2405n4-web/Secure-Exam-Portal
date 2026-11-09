# ExamVault – Secure Online Examination Portal

> **Secure Online Exam Portal with Dockerized Containers and Continuous Deployment via Ansible**

[![ExamVault CI Pipeline](https://github.com/narendarraju/Secure-Exam-Portal/actions/workflows/ci.yml/badge.svg)](https://github.com/narendarraju/Secure-Exam-Portal/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask: 3.x](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/Docker-20.10+-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

---

## Architecture Overview

```
                      ┌─────────────────────────────────────────┐
                      │          Client Browser (User)          │
                      │    Semantic HTML5 / CSS3 / JavaScript   │
                      └───────────────────▲─────────────────────┘
                                          │ HTTP / JSON
                                          ▼
                      ┌─────────────────────────────────────────┐
                      │     Flask Application (Port 5003)       │
                      │    Auth, Timer, Evaluation Engine       │
                      └───────────────────▲─────────────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
      ┌─────────────────────────┐                     ┌─────────────────────────┐
      │   SQLite 3 (Local DB)   │                     │    MySQL 8.0 (Docker)   │
      │  database/examvault.db  │                     │   Persistent DB Volume  │
      └─────────────────────────┘                     └─────────────────────────┘
```

---

## Features

### Student Experience (Phase 1)
* **Pre-Exam Instructions Page**: Detailed exam rules, timing guidelines, and explicit candidate consent.
* **Synchronized Server-Side Timer**: Start time is anchored in UTC on the server and preserved across page refreshes.
* **Server Time Expiry Enforcement**: Automatic submission upon countdown reaching `00:00` with strict server deadline validation.
* **Answer Privacy**: Examination questions are rendered without correct answer keys.
* **Automatic Evaluation**: Instant server-side calculation of marks and percentages.
* **Comprehensive Results Breakdown**: Question-by-question review highlighting selected choices, correct keys, and marks awarded.
* **Duplicate Submission Prevention**: Restricts each student to a single verified attempt per examination.

### Administrator Experience (Phase 2)
* **Dynamic Administrator Dashboard**: Real-time counts of total examinations, active tests, candidates, and submissions.
* **Full Examination Lifecycle Management**: Create, edit, and safely cascade-delete examinations.
* **Question Management**: Add, modify, and delete MCQ questions with four choices and custom mark values.
* **Submissions & Results Portal**: Filter examination attempts by title and review candidate performance.
* **Student Candidate Directory**: Overview of enrolled students, completed test counts, and average percentages.

### Database Modernization (Phase 3)
* **Dual-Engine Architecture**: Seamless support for both SQLite (local development) and MySQL (production/containers).
* **Environment-Variable Driven**: Credentials configured via standard `DB_TYPE`, `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`.
* **Migration Utility**: Automated script (`database/migrate_sqlite_to_mysql.py`) to port SQLite data to MySQL.

### Containerization (Phase 4)
* **Production Dockerfile**: Lightweight multi-stage Python 3.11 image running as a non-privileged `appuser`.
* **Docker Compose Orchestration**: Single-command startup of Flask and MySQL with health checks and persistent volume storage.

### CI/CD & Automated Deployment (Phases 5 & 6)
* **GitHub Actions Workflows**: Automated test execution, Docker build verification, and deployment pipelines.
* **Ansible Automation**: Playbooks to install Docker, configure production `.env` files with `0600` permissions, and launch containers.

---

## Demo Credentials (Development Only)

| Role | Email | Password |
|---|---|---|
| **Student** | `student@example.com` | `Student@123` |
| **Administrator** | `admin@example.com` | `Admin@123` |

---

## Getting Started

### Method 1: Local Development (SQLite)

```bash
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Initialize database
python database/database.py

# 3. Run Flask application
python backend/app.py
```
Open [http://localhost:5003](http://localhost:5003) in your browser.

---

### Method 2: Docker Compose (MySQL)

```bash
# 1. Configure environment (optional, defaults provided)
cp .env.example .env

# 2. Build and start containers
docker compose up -d --build

# 3. View status and logs
docker compose ps
docker compose logs -f web
```
The application will be live at [http://localhost:5003](http://localhost:5003).

---

## Running the Automated Test Suite

```bash
# Run unit and integration tests
python -m unittest tests/test_app.py -v
```

---

## SQLite to MySQL Migration

To migrate your local SQLite data to a running MySQL instance:

```bash
export DB_TYPE=mysql
export DB_HOST=localhost
export DB_USER=examvault_user
export DB_PASSWORD=examvault_pass
export DB_NAME=examvault

python database/migrate_sqlite_to_mysql.py
```

---

## Ansible Server Deployment

To deploy ExamVault to a remote Linux server:

```bash
# 1. Configure target server IP in inventory
vim ansible/inventory.ini

# 2. Verify syntax
ansible-playbook -i ansible/inventory.ini ansible/deploy.yml --syntax-check

# 3. Execute deployment
ansible-playbook -i ansible/inventory.ini ansible/deploy.yml
```

---

## License

This project is licensed under the MIT License.
