# Design Document

## 1. System Architecture

### Layers

The application follows a **three-layer architecture** within a single Flask process:

```
┌─────────────────────────────────────────────────┐
│                  Presentation                    │
│   Jinja2 Templates + HTMX + Bootstrap CSS        │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│               Application Layer                  │
│   Flask Blueprints (routes) + WTForms            │
│   8 blueprints: auth, students, financial,       │
│   reviews, moderation, notifications,            │
│   dashboard, admin                               │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│              Service / Business Logic             │
│   auth_service, financial_service, import_service,│
│   moderation_service, notification_service,       │
│   audit_service, report_service, scheduler_service│
│   rbac (decorators)                              │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│                 Data Layer                        │
│   SQLAlchemy ORM Models + SQLite database         │
│   File storage: local uploads/ directory          │
└─────────────────────────────────────────────────┘
```

### Components and Responsibilities

| Component | Responsibility |
|---|---|
| **Blueprints (routes)** | HTTP request handling, form validation, template rendering, permission gating |
| **Services** | Business logic, data integrity rules, cross-cutting concerns (audit, notifications) |
| **Models** | Database schema, relationships, computed properties |
| **Utils** | File storage (with dedup/version tracking), pagination, HTMX detection |
| **Templates** | Server-rendered HTML with HTMX partial fragments for interactive updates |
| **Extensions** | Shared Flask extension instances (SQLAlchemy, LoginManager, CSRFProtect) |

### Request Flow

1. HTTP request arrives at a Blueprint route
2. `@login_required` checks session authentication via Flask-Login
3. `@permission_required` / `@role_required` checks RBAC authorization
4. Route calls service functions for business logic
5. Service functions interact with models/database
6. Route renders a Jinja2 template (full page or HTMX partial)
7. Audit events are logged via `audit_service.log_event()`

---

## 2. Database Schema

### Entity-Relationship Overview

```
roles ──< role_permissions >── permissions
  │
  └──< users >── locations
          │
          ├──< students
          ├──< transactions
          ├──< reviews
          ├──< notifications
          ├──< audit_events
          └──< moderation_queue
```

### Table Definitions

#### `roles`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| name | String(50) | UNIQUE, NOT NULL |
| description | String(200) | |
| created_at | DateTime | DEFAULT now() |

#### `permissions`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| codename | String(100) | UNIQUE, NOT NULL |
| description | String(200) | |

#### `role_permissions` (junction table)
| Column | Type | Constraints |
|---|---|---|
| role_id | Integer | PK, FK → roles.id |
| permission_id | Integer | PK, FK → permissions.id |

#### `users`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| username | String(80) | UNIQUE, NOT NULL |
| email | String(120) | UNIQUE, NOT NULL |
| password_hash | String(256) | NOT NULL |
| role_id | Integer | FK → roles.id, NOT NULL |
| location_id | Integer | FK → locations.id, NULLABLE |
| is_active | Boolean | DEFAULT True |
| failed_login_attempts | Integer | DEFAULT 0 |
| locked_until | DateTime | NULLABLE |
| password_changed_at | DateTime | NULLABLE |
| force_password_reset | Boolean | DEFAULT False |
| created_at | DateTime | DEFAULT now() |
| updated_at | DateTime | DEFAULT now(), ON UPDATE now() |

#### `locations`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| name | String(100) | UNIQUE, NOT NULL |
| address | String(300) | |
| phone | String(30) | |
| is_active | Boolean | DEFAULT True |
| created_at | DateTime | DEFAULT now() |

#### `students`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| first_name | String(80) | NOT NULL |
| last_name | String(80) | NOT NULL |
| email | String(120) | |
| phone | String(30) | |
| date_of_birth | Date | NULLABLE |
| address | String(300) | |
| license_number | String(50) | |
| enrollment_date | Date | DEFAULT today() |
| status | String(20) | DEFAULT 'enrolled' |
| location_id | Integer | FK → locations.id, NOT NULL |
| assigned_coach_id | Integer | FK → users.id, NULLABLE |
| handler_id | Integer | FK → users.id, NULLABLE |
| created_at | DateTime | DEFAULT now() |
| updated_at | DateTime | DEFAULT now(), ON UPDATE now() |

#### `student_notes`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| student_id | Integer | FK → students.id, NOT NULL |
| coach_id | Integer | FK → users.id, NOT NULL |
| content | Text | NOT NULL |
| created_at | DateTime | DEFAULT now() |

#### `transactions`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| type | String(20) | NOT NULL (income/expense) |
| amount | Float | NOT NULL |
| payee | String(200) | NOT NULL |
| description | Text | |
| category | String(100) | |
| payment_method | String(50) | |
| location_id | Integer | FK → locations.id, NOT NULL |
| handler_id | Integer | FK → users.id, NOT NULL |
| status | String(20) | DEFAULT 'active' |
| receipt_path | String(500) | |
| void_reason | Text | |
| void_approved_by | Integer | FK → users.id, NULLABLE |
| reversal_of_id | Integer | FK → transactions.id, NULLABLE |
| closeout_id | Integer | FK → monthly_closeouts.id, NULLABLE |
| fingerprint_hash | String(64) | |
| created_at | DateTime | DEFAULT now() |
| updated_at | DateTime | DEFAULT now(), ON UPDATE now() |

#### `transaction_versions`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| transaction_id | Integer | FK → transactions.id, NOT NULL |
| version_number | Integer | NOT NULL |
| field_changes | Text | JSON |
| changed_by | Integer | FK → users.id, NOT NULL |
| created_at | DateTime | DEFAULT now() |

#### `monthly_closeouts`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| location_id | Integer | FK → locations.id, NOT NULL |
| month | Integer | NOT NULL |
| year | Integer | NOT NULL |
| closed_by | Integer | FK → users.id, NOT NULL |
| closed_at | DateTime | DEFAULT now() |
| status | String(20) | DEFAULT 'closed' |
| | | UNIQUE(location_id, month, year) |

#### `bulk_import_batches`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| filename | String(255) | NOT NULL |
| uploaded_by | Integer | FK → users.id, NOT NULL |
| row_count | Integer | DEFAULT 0 |
| error_count | Integer | DEFAULT 0 |
| duplicate_count | Integer | DEFAULT 0 |
| status | String(20) | DEFAULT 'pending' |
| created_at | DateTime | DEFAULT now() |

#### `bulk_import_rows`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| batch_id | Integer | FK → bulk_import_batches.id, NOT NULL |
| row_number | Integer | NOT NULL |
| raw_data | Text | JSON |
| status | String(20) | DEFAULT 'pending' |
| error_message | Text | |
| matched_transaction_id | Integer | FK → transactions.id, NULLABLE |
| resolution | String(20) | (merge/keep/skip) |

#### `reviews`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| student_id | Integer | FK → students.id, NULLABLE |
| coach_id | Integer | FK → users.id, NULLABLE |
| location_id | Integer | FK → locations.id, NOT NULL |
| content | Text | NOT NULL |
| status | String(20) | DEFAULT 'pending' |
| moderation_note | Text | |
| created_by | Integer | FK → users.id, NOT NULL |
| created_at | DateTime | DEFAULT now() |
| updated_at | DateTime | DEFAULT now(), ON UPDATE now() |

#### `rating_dimensions`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| name | String(100) | UNIQUE, NOT NULL |
| label | String(200) | NOT NULL |
| sort_order | Integer | DEFAULT 0 |
| is_active | Boolean | DEFAULT True |

#### `rating_scores`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| review_id | Integer | FK → reviews.id, NOT NULL |
| dimension_id | Integer | FK → rating_dimensions.id, NOT NULL |
| score | Integer | NOT NULL, CHECK(1-5) |

#### `review_images`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| review_id | Integer | FK → reviews.id, NOT NULL |
| file_path | String(500) | NOT NULL |
| uploaded_at | DateTime | DEFAULT now() |

#### `review_likes`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| review_id | Integer | FK → reviews.id, NOT NULL |
| user_id | Integer | FK → users.id, NOT NULL |
| created_at | DateTime | DEFAULT now() |
| | | UNIQUE(review_id, user_id) |

#### `review_reports`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| review_id | Integer | FK → reviews.id, NOT NULL |
| reported_by | Integer | FK → users.id, NOT NULL |
| reason | Text | NOT NULL |
| status | String(20) | DEFAULT 'pending' |
| reviewed_by | Integer | FK → users.id, NULLABLE |
| reviewed_at | DateTime | NULLABLE |
| created_at | DateTime | DEFAULT now() |

#### `disputes`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| review_id | Integer | FK → reviews.id, NOT NULL |
| initiated_by | Integer | FK → users.id, NOT NULL |
| statement | Text | NOT NULL |
| status | String(20) | DEFAULT 'open' |
| arbitration_outcome | Text | |
| arbitrated_by | Integer | FK → users.id, NULLABLE |
| resolved_at | DateTime | NULLABLE |
| created_at | DateTime | DEFAULT now() |

#### `dispute_evidence`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| dispute_id | Integer | FK → disputes.id, NOT NULL |
| uploaded_by | Integer | FK → users.id, NOT NULL |
| file_path | String(500) | NOT NULL |
| description | Text | |
| created_at | DateTime | DEFAULT now() |

#### `moderation_queue`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| content_type | String(50) | NOT NULL |
| content_id | Integer | NOT NULL |
| reason | String(100) | NOT NULL |
| flagged_words | Text | |
| status | String(20) | DEFAULT 'held' |
| handled_by | Integer | FK → users.id, NULLABLE |
| handled_at | DateTime | NULLABLE |
| created_at | DateTime | DEFAULT now() |

#### `moderation_logs`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| queue_id | Integer | FK → moderation_queue.id, NOT NULL |
| action | String(50) | NOT NULL |
| performed_by | Integer | FK → users.id, NOT NULL |
| notes | Text | |
| created_at | DateTime | DEFAULT now() |

#### `sensitive_words`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| word | String(100) | NOT NULL |
| category | String(50) | |
| is_active | Boolean | DEFAULT True |
| created_at | DateTime | DEFAULT now() |

#### `user_blacklist`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| user_id | Integer | FK → users.id, NOT NULL |
| reason | Text | |
| blacklisted_by | Integer | FK → users.id, NOT NULL |
| created_at | DateTime | DEFAULT now() |
| expires_at | DateTime | NULLABLE |

#### `notification_types`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| codename | String(100) | UNIQUE, NOT NULL |
| label | String(200) | NOT NULL |
| description | Text | |

#### `notification_subscriptions`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| user_id | Integer | FK → users.id, NOT NULL |
| notification_type_id | Integer | FK → notification_types.id, NOT NULL |
| is_active | Boolean | DEFAULT True |
| digest_mode | Boolean | DEFAULT False |
| | | UNIQUE(user_id, notification_type_id) |

#### `notifications`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| user_id | Integer | FK → users.id, NOT NULL |
| notification_type_id | Integer | FK → notification_types.id, NULLABLE |
| title | String(200) | NOT NULL |
| body | Text | |
| link | String(500) | |
| is_read | Boolean | DEFAULT False |
| is_digest | Boolean | DEFAULT False |
| digest_count | Integer | DEFAULT 0 |
| created_at | DateTime | DEFAULT now() |
| read_at | DateTime | NULLABLE |

#### `notification_rate_log`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| user_id | Integer | FK → users.id, NOT NULL |
| sent_at | DateTime | DEFAULT now() |

#### `audit_events`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| event_type | String(100) | NOT NULL |
| user_id | Integer | FK → users.id, NULLABLE |
| ip_address | String(50) | |
| resource_type | String(100) | |
| resource_id | Integer | |
| detail | Text | JSON |
| created_at | DateTime | DEFAULT now() |

#### `anomaly_flags`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| flag_type | String(100) | NOT NULL |
| description | Text | |
| metric_value | Float | |
| threshold_value | Float | |
| acknowledged | Boolean | DEFAULT False |
| created_at | DateTime | DEFAULT now() |

#### `report_schedules`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| report_name | String(100) | NOT NULL |
| frequency | String(20) | NOT NULL |
| location_id | Integer | FK → locations.id, NULLABLE |
| format | String(10) | DEFAULT 'csv' |
| created_by | Integer | FK → users.id, NOT NULL |
| is_active | Boolean | DEFAULT True |
| last_run_at | DateTime | NULLABLE |
| next_run_at | DateTime | NULLABLE |
| created_at | DateTime | DEFAULT now() |

#### `report_executions`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| schedule_id | Integer | FK → report_schedules.id, NOT NULL |
| file_path | String(500) | |
| status | String(20) | DEFAULT 'success' |
| error_message | Text | NULLABLE |
| executed_at | DateTime | DEFAULT now() |

#### `app_config`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| key | String(100) | UNIQUE, NOT NULL |
| value | Text | JSON |
| updated_by | Integer | FK → users.id, NULLABLE |
| updated_at | DateTime | DEFAULT now(), ON UPDATE now() |

#### `attachments`
| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| filename | String(255) | NOT NULL |
| file_path | String(500) | NOT NULL |
| file_hash | String(64) | NOT NULL |
| file_size | Integer | NOT NULL |
| content_type | String(100) | |
| resource_type | String(100) | |
| resource_id | Integer | |
| version | Integer | DEFAULT 1 |
| parent_id | Integer | FK → attachments.id, NULLABLE |
| uploaded_by | Integer | FK → users.id, NOT NULL |
| is_duplicate | Boolean | DEFAULT False |
| duplicate_of_id | Integer | FK → attachments.id, NULLABLE |
| created_at | DateTime | DEFAULT now() |

---

## 3. API Specification

All endpoints are server-rendered HTML (not JSON REST). HTMX requests receive partial HTML fragments.

### Auth (`/auth`)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET/POST | `/auth/login` | Public | Login form and authentication |
| GET | `/auth/logout` | Authenticated | End session |
| GET/POST | `/auth/change-password` | Authenticated | Change own password |

### Students (`/students`)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/students/` | student.view | List students (Coach sees only assigned) |
| GET/POST | `/students/new` | student.create | Create student |
| GET | `/students/<id>` | student.view | Student detail |
| GET/POST | `/students/<id>/edit` | student.edit | Edit student |
| POST | `/students/<id>/notes` | student.add_note | Add session note (HTMX) |

### Financial (`/financial`)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/financial/` | financial.view | List transactions (location-scoped) |
| GET/POST | `/financial/new` | financial.create | Create transaction |
| GET | `/financial/<id>` | financial.view | Transaction detail + version history |
| GET/POST | `/financial/<id>/edit` | financial.edit | Edit transaction |
| GET/POST | `/financial/<id>/void` | financial.void | Void with supervisor approval |
| POST | `/financial/<id>/reverse` | financial.void | Create reversal transaction |
| GET/POST | `/financial/closeout` | financial.closeout | Monthly financial closeout |
| GET/POST | `/financial/import` | financial.import | Upload CSV/Excel for bulk import |
| GET | `/financial/import/<batch_id>/preview` | financial.import | Preview import batch (owner-gated) |
| POST | `/financial/import/<batch_id>/resolve/<row_id>` | financial.import | Resolve duplicate row (owner-gated) |
| POST | `/financial/import/<batch_id>/execute` | financial.import | Execute import batch (owner-gated) |
| GET | `/financial/uploads/<filepath>` | financial.view | Authenticated file download |

### Reviews (`/reviews`)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/reviews/` | review.view | List reviews (filterable) |
| GET/POST | `/reviews/new` | review.create | Create review with ratings |
| GET | `/reviews/<id>` | review.view | Review detail |
| POST | `/reviews/<id>/like` | review.view | Toggle like (HTMX) |
| POST | `/reviews/<id>/report` | review.view | Report review |
| GET/POST | `/reviews/<id>/dispute` | review.dispute | Create dispute with evidence |
| GET/POST | `/reviews/dispute/<id>/arbitrate` | review.moderate | Arbitrate dispute |

### Moderation (`/moderation`)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/moderation/` | review.moderate | Moderation queue |
| POST | `/moderation/<id>/approve` | review.moderate | Approve content |
| POST | `/moderation/<id>/reject` | review.moderate | Reject content |
| GET | `/moderation/<id>/detail` | review.moderate | View moderation item |
| GET | `/moderation/words` | review.moderate | Sensitive word list |
| POST | `/moderation/words/add` | review.moderate | Add sensitive word |
| POST | `/moderation/words/<id>/toggle` | review.moderate | Toggle word active/inactive |
| GET | `/moderation/blacklist` | review.moderate | User blacklist |
| POST | `/moderation/blacklist/add` | review.moderate | Add user to blacklist |

### Notifications (`/notifications`)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/notifications/` | Authenticated | Notification center |
| POST | `/notifications/<id>/read` | Authenticated | Mark notification read |
| POST | `/notifications/read-all` | Authenticated | Mark all notifications read |
| GET | `/notifications/count` | Authenticated | Unread count (HTMX/JSON) |
| GET/POST | `/notifications/subscriptions` | Authenticated | Manage subscriptions |

### Dashboard (`/dashboard`)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/dashboard/` | report.view | KPI dashboard with filters |
| GET | `/dashboard/drilldown/<kpi>` | report.view | Record-level drill-down |
| POST | `/dashboard/export/<report>` | report.export | Export report CSV/JSON |
| GET | `/dashboard/schedules` | report.export | View report schedules |
| POST | `/dashboard/schedules/new` | report.export | Create schedule |
| POST | `/dashboard/schedules/<id>/toggle` | report.export | Toggle schedule active |
| POST | `/dashboard/schedules/run` | report.export | Execute due schedules |

### Admin (`/admin`)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/admin/users` | Role: Administrator | User list |
| GET/POST | `/admin/users/new` | Role: Administrator | Create user |
| GET/POST | `/admin/users/<id>/edit` | Role: Administrator | Edit user |
| POST | `/admin/users/<id>/force-reset` | Role: Administrator | Force password reset |
| POST | `/admin/users/<id>/unlock` | Role: Administrator | Unlock locked account |
| GET | `/admin/locations` | Role: Administrator | Location list |
| GET/POST | `/admin/locations/new` | Role: Administrator | Create location |
| GET/POST | `/admin/locations/<id>/edit` | Role: Administrator | Edit location |
| GET | `/admin/dimensions` | Role: Administrator | Rating dimensions |
| GET/POST | `/admin/dimensions/new` | Role: Administrator | Create dimension |
| GET/POST | `/admin/dimensions/<id>/edit` | Role: Administrator | Edit dimension |
| GET | `/admin/audit` | Role: Administrator | Audit event log |
| GET | `/admin/anomalies` | Role: Administrator | Anomaly flags |
| POST | `/admin/anomalies/<id>/ack` | Role: Administrator | Acknowledge anomaly |
| GET/POST | `/admin/config` | Role: Administrator | App configuration |

---

## 4. Key Business Rules

### Authentication & Security

- **Account lockout**: After 5 consecutive failed login attempts, the account is locked for 15 minutes. Administrators can manually unlock accounts.
- **Password policy**: Minimum 12 characters, must contain at least one digit and one symbol.
- **Session timeout**: Sessions expire after 30 minutes of inactivity. Checked on every request via `before_request` hook.
- **Forced password reset**: Administrators can flag users to require password change on next login. The `before_request` hook redirects flagged users to the change-password page.
- **Open redirect prevention**: The `next` parameter on login is validated to reject external URLs (no scheme or netloc allowed).

### Financial Lifecycle

- **Transaction statuses**: `draft` → `active` → `closed` (via closeout) or `voided`/`reversed`.
- **Fingerprint deduplication**: Each transaction computes a SHA-256 fingerprint from `payee|amount|date|location|payment_method`. New transactions with similar fingerprints (>= 0.92 similarity ratio) are saved as `draft` with a warning.
- **Void/reversal dual-control**: Both operations require a different user with `financial.void` permission to approve. Self-approval is explicitly rejected.
- **Monthly closeout**: One-time per location/month (enforced by unique constraint). Updates all matching `active` transactions to `closed` and links them to the closeout record.
- **Bulk import workflow**: Upload → Preview (validate, detect duplicates) → Resolve duplicates (merge/keep/skip per row) → Execute. Merge updates the matched transaction's supplementary fields with version tracking. Keep imports as a new distinct transaction.
- **Import batch ownership**: Only the uploader (or Administrator/Auditor) can preview, resolve, or execute a batch.

### Reviews & Reputation

- **Moderation pipeline**: Reviews pass through automated checks (sensitive word matching, rate limiting at 3/hour, user blacklist). Flagged reviews enter the moderation queue as `held`; clean reviews are auto-approved.
- **Rating dimensions**: Configurable multi-dimension scoring (1-5 per dimension). Dimensions are managed by administrators.
- **Dispute workflow**: Any user with `review.dispute` can challenge a review by submitting a statement and evidence files. Moderators arbitrate disputes. The dispute resolution is recorded but does not automatically change the review's status.

### Notifications

- **Subscription-based**: Notifications are only delivered if the user has an active subscription for that notification type.
- **Rate limiting**: Maximum 5 immediate notifications per user per hour (configurable). Excess notifications are silently dropped.
- **Digest mode**: When enabled per subscription, notifications of the same type are aggregated into a single unread entry with a running count, rather than creating individual notifications. Digest notifications bypass the rate limit.

### Data Isolation

- **Location scoping**: FrontDesk and Coach users only see financial transactions from their assigned location. Administrators and Auditors see all locations.
- **Coach scoping**: Coaches only see students explicitly assigned to them via `assigned_coach_id`.

### Audit & Anomaly Detection

- **Audit trail**: All significant actions (login, CRUD, void, import, moderation) are logged to `audit_events` with user, IP, resource reference, and JSON detail.
- **Anomaly detection**: Triggered on admin audit page visits. Checks for: login lockout spikes (>=10 in 1 hour) and dispute rate spikes (>=5 in 1 hour). Anomalies are deduplicated within the detection window.

---

## 5. Technical Choices and Justifications

### Stack

| Choice | Justification |
|---|---|
| **Flask** | Lightweight, well-suited for server-rendered applications. Blueprint system provides clean domain separation. |
| **SQLite** | Matches the offline-first, single-node deployment requirement. Zero-config, file-based, no external database server needed. |
| **SQLAlchemy ORM** | Provides model abstraction, relationship management, and query building without raw SQL. Compatible with SQLite. |
| **Jinja2 + HTMX** | Server-rendered templates with HTMX enable interactive partial updates without a JavaScript SPA framework. Reduces frontend complexity. |
| **Bootstrap 5** | Rapid UI development with responsive layout, consistent styling, and accessible components. |
| **Flask-Login** | Session-based authentication with cookie management, user loader, and `login_required` decorator. |
| **Flask-WTF** | CSRF protection and form validation integrated with WTForms. |
| **Werkzeug** | Password hashing via `generate_password_hash` / `check_password_hash` (PBKDF2). |

### Architectural Decisions

| Decision | Trade-off |
|---|---|
| **Blueprints per domain** | Clean separation of concerns at the cost of cross-module imports for shared data. Each blueprint handles its own routes, forms, and templates. |
| **Service layer** | Business logic is extracted from routes into service functions, enabling unit testing without HTTP overhead. |
| **RBAC via decorators** | Permission checks are declarative (`@permission_required('financial.view')`) rather than inline. Simple to audit but requires correct decorator stacking. |
| **Role-permission M2M** | Flexible permission assignment via junction table. Roles can be reconfigured without code changes. |
| **Fingerprint-based dedup** | SHA-256 hash of normalized fields enables fast duplicate detection. SequenceMatcher ratio comparison allows near-match detection for typo variants. |
| **File storage with tracking** | `save_file_with_tracking()` creates an `Attachment` record with hash, version, and dedup metadata alongside the file save. Enables audit trail for uploads. |
| **No background worker** | Scheduled reports rely on manual trigger rather than cron/Celery. Appropriate for the offline-first SQLite context where a persistent worker would add operational complexity. |
| **HTMX partials** | Each page has a corresponding `partials/` template. Routes detect `HX-Request` header and return the partial instead of the full page, enabling in-place updates. |
| **Audit-first design** | Every state change logs to `audit_events`. This adds write overhead but provides full traceability required for a financial/operational platform. |
