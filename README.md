# Driving School Management System

An offline-first, multi-location driving school operations platform covering enrollment, financial management, quality/reputation workflows, and administrative controls.

## Technology Stack

- **Backend:** Python 3 / Flask
- **Database:** SQLite (local file storage)
- **Frontend:** Server-rendered templates with HTMX for interactive updates, Bootstrap CSS
- **Authentication:** Flask-Login with session-based auth

## Prerequisites

- Python 3.9+
- pip

## Setup & Installation

```bash
# Clone the repository
git clone <repository-url>
cd driving-school-system

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Configuration is managed via environment variables and `config.py`.

### Required Environment Variables

| Variable     | Description                                  | Default (dev only)                     |
|-------------|----------------------------------------------|----------------------------------------|
| `SECRET_KEY` | Flask session secret key (**required in production**) | `dev-secret-key-change-in-production` |

### Application Settings (config.py)

| Setting                        | Default | Description                                   |
|-------------------------------|---------|-----------------------------------------------|
| `SESSION_TIMEOUT_MINUTES`     | 30      | Inactivity timeout before session expires     |
| `LOGIN_LOCKOUT_ATTEMPTS`      | 5       | Failed login attempts before account lockout  |
| `LOGIN_LOCKOUT_MINUTES`       | 15      | Duration of account lockout (minutes)         |
| `PASSWORD_MIN_LENGTH`         | 12      | Minimum password length                       |
| `NOTIFICATION_RATE_LIMIT`     | 5       | Max notifications per user per hour           |
| `REVIEW_RATE_LIMIT`           | 3       | Max reviews per user per hour                 |
| `DUPLICATE_SIMILARITY_THRESHOLD` | 0.92 | Fingerprint similarity threshold for dedup    |
| `MAX_CONTENT_LENGTH`          | 10 MB   | Maximum upload file size                      |
| `ALLOWED_EXTENSIONS`          | jpg, jpeg, png, pdf | Allowed upload file extensions     |

> **Important:** In production, set the `SECRET_KEY` environment variable to a strong random value. The application will refuse to start if the default dev key is used with `DEBUG=False`.

## Database Initialization & Seeding

```bash
# Seed the database with default roles, permissions, locations, and sample users
python seed.py
```

### Default Credentials (created by seed)

| Role          | Username    | Password        |
|--------------|-------------|-----------------|
| Administrator | `admin`     | `Admin123!@#$`  |
| Front Desk   | `frontdesk1`| `FDesk123!@#$`  |
| Coach        | `coach1`    | `Coach123!@#$`  |
| Auditor      | `auditor1`  | `Audit123!@#$`  |

> Change all default passwords immediately in production.

## Running the Application

```bash
# Development server
python run.py
# Server starts at http://0.0.0.0:5000

# Or with Flask CLI
flask run --host=0.0.0.0 --port=5000
```

### Docker

```bash
docker build -t driving-school .
docker run -p 5000:5000 -e SECRET_KEY=your-secret-key driving-school
```

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_auth.py

# Run with coverage
pytest --cov=app --cov-report=term-missing
```

## Roles & Permissions (RBAC)

The system uses role-based access control with four predefined roles:

- **Administrator** -- Full access to all features including user management, audit logs, configuration, and all operational modules.
- **Front Desk** -- Student enrollment, financial transactions (create/edit/import), basic review access, and report viewing.
- **Coach** -- View assigned students, add student notes, create/dispute reviews, and view reports. Coaches can only access students assigned to them.
- **Auditor** -- Read-only access to students, financial records, reviews, full report access including exports, and audit log viewing.

### Security Controls

- **Session Timeout:** Sessions expire after 30 minutes of inactivity.
- **Account Lockout:** Accounts lock after 5 failed login attempts for 15 minutes. Administrators can manually unlock accounts.
- **Password Policy:** Minimum 12 characters, must include at least one number and one symbol.
- **Forced Password Reset:** Administrators can force users to change their password on next login.
- **Location-based Isolation:** Financial records are scoped by user location for non-admin roles.
- **Supervisor Approval:** Void and reversal operations require a separate supervisor/admin approver (self-approval is not allowed).

## Modules

### Students
Enrollment management with status tracking (enrolled/active/completed/withdrawn), coach assignment, and session notes.

### Financial
Transaction lifecycle including create, edit, void, reverse, and monthly closeout. Features duplicate detection via fingerprint hashing, bulk CSV/Excel import with preview and row-level error/duplicate resolution, and full version history audit trail.

### Reviews & Reputation
Community reviews with multi-dimension ratings (professionalism, punctuality, vehicle condition, overall), likes, reports, disputes with evidence upload, and arbitration workflow.

### Moderation
Content moderation queue with automated flagging (sensitive word detection, rate limiting, user blacklist), manual approve/reject workflow with audit logging.

### Notifications
Subscription-based notification system with per-type opt-in/out, read tracking, rate limiting (5/hour), and digest mode support.

### Dashboard & Reports
KPI dashboards with drill-down views for approval turnaround, coach utilization, student retention, community activity, and financial summary. On-demand export to CSV/JSON. Scheduled report generation with configurable intervals.

### Administration
User management, location management, rating dimension configuration, audit event logs with anomaly detection (login spikes, dispute rate spikes), and application configuration key-value store.

## File Storage

Uploaded files (receipts, review images, dispute evidence) are stored locally in the `uploads/` directory organized by category. Files are stored with UUID filenames. Attachments include hash-based deduplication and version tracking.

## Project Structure

```
driving-school-system/
├── run.py                    # Application entry point
├── config.py                 # Configuration classes
├── seed.py                   # Database seeding script
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container build file
├── README.md                 # This file
├── app/
│   ├── __init__.py           # Flask app factory
│   ├── extensions.py         # Database, login, CSRF extensions
│   ├── blueprints/           # Route handlers by domain
│   │   ├── auth/             # Authentication (login/logout/password)
│   │   ├── students/         # Student enrollment & notes
│   │   ├── financial/        # Transactions, closeout, import
│   │   ├── reviews/          # Reviews, disputes, arbitration
│   │   ├── moderation/       # Content moderation queue
│   │   ├── notifications/    # Notification center & subscriptions
│   │   ├── dashboard/        # KPI dashboards & reports
│   │   └── admin/            # User/location/config management
│   ├── models/               # SQLAlchemy data models
│   ├── services/             # Business logic layer
│   ├── templates/            # Jinja2 HTML templates
│   └── utils/                # Helpers and file storage
├── tests/                    # Pytest test suite
└── uploads/                  # File storage (created at runtime)
```
