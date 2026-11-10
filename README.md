# Vibe Coding Exam Starter Workspace

A pre-configured, reusable full-stack development environment prepared for the 2-hour **Vibe Coding Exam**.

---

## 1. Environment & Tech Stack

| Tier | Primary Technology | Drivers & Libraries |
| :--- | :--- | :--- |
| **Frontend** | React (JavaScript) | Vite, HTML5, Vanilla CSS |
| **Backend** | Python 3.12, FastAPI | Uvicorn, SQLAlchemy, Pydantic v2 |
| **Option A (Database)** | Local MySQL Server 8.0 | PyMySQL |
| **Option B (Database)** | Supabase PostgreSQL | `psycopg2-binary`, `pg8000` |
| **API Protocol** | RESTful APIs | JSON, CORS Middleware, HTTPX |
| **Tooling** | Git, Node.js v24 (LTS), npm 11 | PowerShell, curl |

---

## 2. Modular Dual-Database Architecture

The backend database layer (`backend/database.py`) is designed to switch seamlessly between **Local MySQL** and **Supabase PostgreSQL** via a single environment variable `DATABASE_TYPE` in `.env`:

- **To use Local MySQL (Option A)**:
  ```env
  DATABASE_TYPE=mysql
  MYSQL_HOST=127.0.0.1
  MYSQL_PORT=3306
  MYSQL_USER=root
  MYSQL_PASSWORD=your_password
  MYSQL_DATABASE=exam_db
  ```

- **To use Supabase PostgreSQL (Option B)**:
  ```env
  DATABASE_TYPE=supabase
  SUPABASE_DB_HOST=db.your-project.supabase.co
  SUPABASE_DB_PORT=5432
  SUPABASE_DB_USER=postgres
  SUPABASE_DB_PASSWORD=your_supabase_password
  SUPABASE_DB_NAME=postgres
  ```

---

## 3. Project Folder Layout

```
vibe-coding-exam/
├── frontend/             # React + Vite application directory
├── backend/              # FastAPI application directory
│   ├── .venv/            # Python virtual environment (pre-installed dependencies)
│   ├── database.py       # Modular SQLAlchemy database switcher (MySQL & Supabase)
│   ├── .env.example      # Environment variables template
│   └── requirements.txt  # Pinned backend dependencies
├── database/             # Placeholders for SQL schemas and migrations
├── docs/                 # Exam requirement specs and architecture notes
├── tests/                # Automated API & unit tests
├── .gitignore            # Security ignore rules (.env, .venv, node_modules)
├── .env.example          # Root environment template
├── README.md             # Setup guide & exam cheatsheet
└── PROMPTS.md            # Exam AI prompt tracking log
```

---

## 4. Quick Start Commands for Tomorrow

### A. Frontend Setup & Run
```bash
cd frontend
# Scaffolding React + Vite app tomorrow:
npm create vite@latest . -- --template react
npm install
npm run dev
# Access UI at http://localhost:5173
```

### B. Backend Setup & Run
```bash
cd backend
# Virtual environment is ready at backend/.venv
# Activation:
# PowerShell:
.\.venv\Scripts\Activate.ps1
# CMD:
.\.venv\Scripts\activate.bat

# Start FastAPI server:
uvicorn main:app --reload --port 8000
# Access Swagger Interactive Docs at http://localhost:8000/docs
```

### C. Git Workflow
```bash
git add .
git commit -m "feat: complete exam task"
```

---

## 5. Security & Environment

- Never commit real passwords, API keys, or Supabase service role keys.
- Copy `.env.example` to `.env` inside `backend/` before starting development.
- `.gitignore` is pre-configured to exclude `.env`, `.venv`, `node_modules`, `dist`, and temporary IDE files.
