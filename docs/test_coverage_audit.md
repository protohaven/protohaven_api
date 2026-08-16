# Python Test Coverage Audit

This audit identifies the parts of the repository most at risk of regression due to missing or shallow automated tests.

## Method

- Test runner: `pytest` inside the existing project venv (`/root/protohaven_api/venv`).
- Coverage tooling: `coverage` + `pytest-cov`.
- Command run:

  ```bash
  python -m pytest -q --cov=protohaven_api --cov-report=term-missing --cov-report=json:coverage.json
  python -m pytest -q --cov=protohaven_api --cov-branch --cov-report=term-missing --cov-report=json:coverage_branch.json
  ```

- Test result: **917 passed, 1 skipped** in ~31 seconds.
- Production files are defined as non-test Python modules under `protohaven_api/` (excluding `*_test.py`, `__init__.py`, and the test helper `protohaven_api/testing.py`).

## Overall results

| Group | Files | Statements | Line coverage | Branch coverage |
| --- | ---: | ---: | ---: | ---: |
| Application core (`commands`, `handlers`, `automation`, server modules) | 39 | 5,090 | 76.8% | 64.9% |
| Production integrations | 24 | 3,302 | 63.7% | 44.8% |
| Dev-mode data fixtures (`integrations/data/dev_*`) | 8 | 520 | 43.5% | 17.7% |
| **All production non-test modules** | **74** | **8,912** | **70.0%** | **55.2%** |

Notes:

- Running plain `pytest --cov=protohaven_api` reports ~80% line coverage, but that number is inflated because test files inside `protohaven_api/` are counted as covered code.
- Branch coverage is substantially weaker than line coverage (55.2% vs 70.0%), meaning many conditional branches and error/exit paths are untested even when the happy path is covered.
- `protohaven_api/scripts/*.py` is not imported by the unit test suite, so it is effectively 0% covered and excluded from the statement table above.

## Highest-risk gaps

The following are ordered by risk to production. Risk is driven by combination of low coverage, write side effects, and sensitivity of the domain.

### Critical: business logic with destructive or financial side effects

| Module | Line / branch | Why it is risky |
| --- | ---: | --- |
| `commands/reservations.py` | 27.8% / 25.2% | Creates, updates, and deletes live Booked reservations. Only 4 tests exist and they mostly exercise `sync_reservable_tools`. `sync_booked_members` (~74 missing lines) and `cleanup_orphaned_class_reservations` (~73 missing lines) are effectively untested, so duplicate or mass-deletion bugs would reach production. |
| `integrations/sales.py` | 23.2% / 19.1% | Square payment/subscription/inventory integration. Only `get_unpaid_invoices_by_id` has a test. `get_subscriptions`, `get_purchases`, `get_inventory`, `get_customer_name_map`, `set_subscription_note`, and `subscription_tax_pct` are untested. |
| `integrations/neon_base.py` | 37.8% / 35.8% | Neon admin browser automation. Tests cover pagination and basic account fetch/patch only. `NeonOne.do_login`, `create_single_use_abs_event_discounts`, `_post_discount`, ticket group creation/assignment, and `delete_all_prices_and_groups` are untested. These are write paths against CRM financial/event data. |
| `integrations/airtable.py` | 55.4% / 50.4% | Central source of truth for classes, tools, clearances, violations, coupons, and recertifications. Large write surface remains untested: `ScheduledClass.prefill_form`, `get_instructor_neon_id_map`, `fetch_instructor_capabilities`, `set_forecast_override`, `get_latest_passing_quizzes_by_email_and_tool`, `close_violation`, and `update_pending_recertification`. |
| `automation/classes/scheduler.py` | 62.0% / 54.1% | `validate()` is mostly untested (33 missing lines). This is the scheduling conflict/validation logic that prevents double-booking classes. |
| `automation/policy/enforcer.py` | 65.6% / 58.2% | Fee generation and accrual updates are only partially tested. Incorrect fees directly affect member billing. |

### High: authentication, sign-in, and user-facing handler flows

| Module | Line / branch | Why it is risky |
| --- | ---: | --- |
| `handlers/auth.py` | 42.3% / 36.7% | Login, logout, and OAuth redirect flows are untested. A regression here locks everyone out or leaves sessions inconsistent. |
| `oauth.py` | 41.7% / 41.7% | Neon OAuth request/token retrieval is mostly untested. |
| `handlers/index.py` | 61.4% / 59.8% | `welcome_neon_ws` (42 missing lines) is the member/guest sign-in websocket flow. `welcome_sock`, `survey_response`, `acknowledge_announcements`, `events_dashboard_attendee_count`, and `get_shop_events` also have gaps. |
| `handlers/techs.py` | 73.4% / 70.0% | Overall decent, but `run_attendance_report` and its nested helpers are mostly untested (~70 missing lines). Tech attendance reporting is an admin/lead workflow. |
| `handlers/staff.py` | 48.3% / 42.4% | `summarizer_ws` and `ops_summary_ws` websocket flows are untested. |
| `handlers/member.py` | 70.3% / 65.9% | `set_discord_nick` and several member routes are untested. |
| `handlers/reservations.py` | 71.4% / 71.4% | Only `reservations_set_tool` exists, but it is not exercised. |

### High: integration clients with external side effects

| Module | Line / branch | Why it is risky |
| --- | ---: | --- |
| `integrations/discord_bot.py` | 41.7% / 36.6% | `on_ready`, `on_member_join`, `set_nickname`, `get_channel_history`, `on_message`, and `run` are untested. This drives member role/nickname automation and Discord notifications. |
| `integrations/booked.py` | 59.9% / 53.6% | Resource area/group mapping, member permissions, `get_reservations_for_areas`, and `ReservationCache` refresh/lookup are untested. |
| `integrations/tasks.py` | 63.8% / 57.3% | Asana `get_project_tracker`, `add_tool_report_task`, and several project-request getters are untested. |
| `integrations/eventbrite.py` | 58.0% / 52.5% | Event publishing paths (`create_event`, `set_structured_content`, `set_event_scheduled_state`, `upload_logo_image`, `fetch_attendees`) are untested. |
| `integrations/neon.py` | 66.2% / 62.8% | `create_member` (21 missing lines), several search variants, and cached lookup fallbacks are untested. |
| `integrations/mqtt.py` | 68.5% / 63.8% | Socket connect/run/notify methods are untested; failures in these paths affect shop hardware messaging. |
| `integrations/data/connector.py` | 67.6% / 69.4% | Core request/retry layer. Several `Connector` methods (`email`, Google/Wyze/Asana requests) are untested. |

### Entrypoints and scripts

| File | Coverage | Risk |
| --- | ---: | --- |
| `main.py` | 0.0% (0/64 statements) | Server bootstrap, blueprint registration, Discord bot startup, and connector selection run at import time and are not tested. |
| `cli.py` | 0.0% (0/35 statements) | CLI bootstrap and command wiring run at import time and are not tested. |
| `scripts/cronicle_qa_tests.py` | not measured | Post-deploy QA script, 503 source lines. |
| `scripts/webhook_qa_tests.py` | not measured | Post-deploy webhook QA script, 278 source lines. |
| `scripts/patch_user_clearance.py` | not measured | Maintenance script, 17 source lines. |
| `compare_coverage.py` | not measured | CI-only coverage comparison helper. |
| `setup.py` | not measured | Packaging helper. |

## Lower-risk gaps

These are less urgent but still worth addressing:

- `integrations/models.py` (80.3% line / 76.3% branch) is generally well tested, but the missing lines concentrate in `Member` and `Event.sessions` edge cases.
- `integrations/data/dev_*` (43.5% line / 17.7% branch) are dev-only fixtures. Low coverage here is acceptable, but because dev mode is the default local experience, bugs in these fixtures can waste development time or mask production integration bugs.
- `commands/finances.py` (72.8% / 70.0%) has good breadth but `restock_discounts` (~21 missing lines) and several membership-validation branches are untested.
- `commands/classes.py`, `commands/roles.py`, `automation/roles/roles.py`, and `automation/membership/clearances.py` are in the 83-90% line range; their remaining gaps are mostly error paths and optional branches.

## Recommendations

1. Add tests first for write/destructive paths:
   - `commands/reservations.py::sync_booked_members` and `cleanup_orphaned_class_reservations`
   - `integrations/neon_base.py::NeonOne` discount/ticket-group writes
   - `integrations/airtable.py` schedule, violation, recertification, and forecast-override writes
   - `integrations/sales.py` subscription/inventory methods
2. Add Flask test coverage for auth endpoints (`handlers/auth.py`, `oauth.py`) and websocket flows (`handlers/index.py`, `handlers/staff.py`, `handlers/techs.py::run_attendance_report`).
3. Split `main.py` and `cli.py` so bootstrap logic is importable without side effects, then test both entrypoints. Even a smoke test that asserts blueprints are registered and connectors are selected would catch deployment-breaking regressions.
4. Cover integration client error/exit branches, not just mocked happy paths. Branch coverage of production integrations is only 44.8%.
5. Decide whether `scripts/*` should be covered or explicitly marked as manual/QA-only in coverage config.
6. Fix the existing CI coverage workflow, which currently runs `--cov=my_package` instead of `--cov=protohaven_api`; as written, `compare_coverage.py` cannot compare actual project coverage.
