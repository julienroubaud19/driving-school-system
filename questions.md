# Business Ambiguities

## Question 1: Student enrollment status transitions
**Problem**: The prompt does not specify the allowed transitions between student statuses (enrolled, active, completed, withdrawn), nor whether withdrawn students can be re-enrolled.
**My understanding**: Any status can transition to any other status via the edit form, and there is no restriction on re-enrollment.
**Implemented solution**: The `StudentForm` allows free-form status selection from the predefined choices. There is no state-machine guard on transitions (`app/blueprints/students/routes.py:116-118`). A student can be changed from `withdrawn` back to `active` at any time.

## Question 2: Financial transaction location isolation scope
**Problem**: The prompt requires location-based data isolation but does not clarify whether Auditors should see all locations or only their assigned location.
**My understanding**: Auditors have a read-only, cross-location view similar to Administrators, since their purpose is oversight.
**Implemented solution**: Both `Administrator` and `Auditor` roles bypass the location filter on financial transaction lists and detail views (`app/blueprints/financial/routes.py:28-29`, `app/blueprints/financial/routes.py:123-126`).

## Question 3: Self-approval scope for void and reversal
**Problem**: The prompt requires supervisor approval for void/reverse but does not define whether the approver must hold a specific role or simply be a different user with the `financial.void` permission.
**My understanding**: Any other user with the `financial.void` permission can act as supervisor. The only hard rule is that a user cannot approve their own void or reversal request.
**Implemented solution**: The `void_transaction` and `create_reversal` functions check `approved_by_id == user_id` and verify the approver has `financial.void` permission, but do not require a specific role (`app/services/financial_service.py:62-68`, `app/services/financial_service.py:87-93`).

## Question 4: Duplicate detection threshold semantics
**Problem**: The prompt mentions deduplication via fingerprinting but does not specify whether "similarity" means exact hash match or fuzzy comparison, nor what the 0.92 threshold applies to.
**My understanding**: The system uses SHA-256 fingerprint hashes and compares them via `SequenceMatcher` ratio, treating the threshold as a minimum similarity score between hex digest strings.
**Implemented solution**: `find_duplicates` in `app/services/financial_service.py:24-38` computes pairwise similarity of fingerprint hash strings. An exact duplicate yields ratio 1.0; near-matches above 0.92 are flagged. This is conservative -- two truly identical transactions produce identical hashes (ratio 1.0), while minor field differences produce lower ratios.

## Question 5: Import merge vs. keep behavior
**Problem**: The prompt requires a merge/keep decision for duplicate rows during bulk import but does not define which fields are merged or whether merge creates a new version.
**My understanding**: "Merge" means update the matched existing transaction's supplementary fields (description, category) from the import row, preserving the original core financial fields (amount, payee, type). "Keep" means import the row as an entirely new transaction alongside the existing one.
**Implemented solution**: `execute_import` in `app/services/import_service.py:101-160` handles merge by updating description/category on the matched transaction with a version record, and keep by inserting a new transaction. Skip leaves the row unprocessed.

## Question 6: Review moderation auto-approval fallback
**Problem**: The prompt does not specify whether reviews that pass all moderation checks (no sensitive words, not rate-limited, author not blacklisted) should be auto-approved or queued for manual review.
**My understanding**: Reviews that pass all automated checks are auto-approved and immediately visible. Only flagged reviews enter the moderation queue.
**Implemented solution**: In `app/blueprints/reviews/routes.py:90-96`, if `check_content` returns `None` (no flags), the review status is set directly to `approved`. Otherwise it stays `pending` and a moderation queue item is created.

## Question 7: Notification rate limiting vs. digest mode interaction
**Problem**: The prompt mentions both rate limiting (5/hour) and digest mode but does not specify whether digest-mode notifications bypass the rate limit or are still subject to it.
**My understanding**: Digest-mode notifications bypass the per-hour rate limit because they aggregate into a single notification entry rather than creating many. Rate limiting only applies to non-digest (immediate) notifications.
**Implemented solution**: In `app/services/notification_service.py:22-50`, when `digest_mode` is True, the function either aggregates into an existing unread digest or creates a new one, returning early before the rate-limit check. Non-digest notifications go through the standard rate-limit gate.

## Question 8: Monthly closeout idempotency
**Problem**: The prompt does not specify what happens if an administrator attempts to close the same month/location twice, or if new transactions arrive after a closeout.
**My understanding**: A closeout is a one-time operation per location/month. Attempting to close an already-closed month returns an error. Transactions created after a closeout for that month remain `active` (they would be included in the next period's closeout).
**Implemented solution**: A `UniqueConstraint` on `(location_id, month, year)` in `app/models/financial.py:88-90` enforces uniqueness. `close_month` checks for an existing closeout first (`app/services/financial_service.py:122-126`). Only transactions with `status='active'` matching the month/year are updated to `closed`.

## Question 9: Coach visibility scope for students
**Problem**: The prompt says coaches can view assigned students but does not define whether coaches should also see students with no coach assigned, or students at their location.
**My understanding**: Coaches can only see students explicitly assigned to them via `assigned_coach_id`. Unassigned students and students assigned to other coaches are hidden.
**Implemented solution**: `app/blueprints/students/routes.py:22-23` filters the student list by `assigned_coach_id=current_user.id` when the role is Coach. The detail view also denies access if the student's coach does not match (`app/blueprints/students/routes.py:100-102`).

## Question 10: Dispute lifecycle and review status after arbitration
**Problem**: The prompt does not specify whether a resolved dispute should revert the review's status (e.g., back to `approved` or to `rejected`), or if the review remains in `disputed` state.
**My understanding**: Arbitration records the outcome and resolves the dispute, but the review's status is not automatically changed. The moderator must separately approve or reject the review through the moderation queue if needed.
**Implemented solution**: `app/blueprints/reviews/routes.py:212-217` sets `dispute.status = 'resolved'` and records the arbitration outcome, but does not modify `review.status`. The review remains in its current state until explicitly moderated.

## Question 11: Attachment deduplication scope
**Problem**: The prompt mentions attachment dedup and version tracking but does not specify whether deduplication is scoped per-resource (per transaction/review) or globally across all resources.
**My understanding**: Deduplication detection is scoped by `resource_type` (e.g., all transaction receipts are checked against each other, but not against review images). Version tracking is scoped per `resource_type + resource_id`.
**Implemented solution**: `Attachment.find_by_hash` in `app/models/attachment.py:34-39` filters by `file_hash` and optionally by `resource_type`. `save_file_with_tracking` in `app/utils/file_storage.py:33-81` checks for duplicates within the same `resource_type` and tracks versions per `resource_type + resource_id`.

## Question 12: Report schedule execution timing
**Problem**: The prompt requires scheduled reports but does not specify how schedules are triggered (cron, background worker, manual trigger), given the offline-first SQLite architecture with no background job system.
**My understanding**: Since the system runs on SQLite without a background job queue, scheduled reports are executed on-demand when an admin visits the schedules page or explicitly triggers the "Run Due Schedules" action. There is no automatic cron or background worker.
**Implemented solution**: `app/services/scheduler_service.py:51-62` provides `run_due_schedules()` which queries for overdue schedules and executes them synchronously. It is triggered via the `/dashboard/schedules/run` POST endpoint (`app/blueprints/dashboard/routes.py:162-168`). `next_run_at` is computed but only checked when the endpoint is called.
