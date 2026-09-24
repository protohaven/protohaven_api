# Cronicle QA Test Plan

Status: plan only. No QA code has been implemented yet.

## 1. Goals

Cronicle QA runs jobs with **prod credentials**. The tests must:

1. Modify prod data only when necessary, preferring temporary mock data.
2. Never spam public channels. All comms go to internal/private QA targets.
3. Warn internal channels before QA runs.
4. Verify real job behavior from Cronicle logs, not from the old
   `input("Confirm message was sent")` prompt.
5. Clean up mock data even when a job or assertion throws.
6. Fail loudly and notify `#cronicle-automation` when automatic cleanup fails.

## 2. QA package layout

All QA-specific code moves out of `protohaven_api/scripts/cronicle_qa_tests.py`
and into `protohaven_api/qa`, split into unit-testable modules:

```text
protohaven_api/qa/
  __init__.py
  plan.md
  base.py              # run IDs, context, cleanup stack, assertion helpers
  cronicle.py          # schedule fetch, run_event, job status/log fetch
  comms.py             # overrides, advance notice, send assertions
  cleanup.py           # cleanup failure collection + #cronicle-automation notice
  fixtures/
    neon.py            # mock Neon account/event/membership helpers
    airtable.py        # mock Airtable record helpers
    asana.py           # mock Asana task helpers
    booked.py          # mock Booked resource/user/reservation helpers
    drive.py           # QA Drive folder/file cleanup helpers
    discord.py         # dedicated QA Discord user/nickname/role helpers
  jobs/
    probers.py
    readonly.py
    asana_tasks.py
    additive.py
    destructive.py
  registry.py          # ordered, metadata-rich test registry
  verify.py            # final orphan/mock-data verification
  *_test.py            # unit tests for the QA harness itself
```

`protohaven_api/scripts/cronicle_qa_tests.py` becomes a thin CLI wrapper that
imports `protohaven_api.qa` and runs the registry.

## 3. Shared QA behavior

### 3.1 Communication overrides

```python
COVR = "#cronicle-automation"
EOVR = "hello+qa-testing@protohaven.org"
DOVR = "@workshop_protohaven"   # dedicated QA Discord user
```

- Discord channel messages are overridden to `COVR`.
- Email is overridden to `EOVR`.
- Discord DMs are overridden to `DOVR`.
- `@workshop_protohaven` is the dedicated QA Discord user.

For any job that should send comms:

```text
ARGS_CHAN_OVERRIDE=#cronicle-automation
ARGS_EMAIL_OVERRIDE=hello+qa-testing@protohaven.org
ARGS_DM_OVERRIDE=@workshop_protohaven   # where applicable
ARGS_SEND_COMMS=1
ARGS_YAML_OUT=/tmp/qa_<job>.yaml
```

For a job run intentionally dry/no-send:

```text
ARGS_SEND_COMMS=0
ARGS_YAML_OUT=
```

Assertions are made from the Cronicle job log:

- Discord sent: `Sent to Discord #cronicle-automation:`
- Email sent: `Sent msg` and `hello+qa-testing@protohaven.org`
- No action: generated empty YAML / `was empty, so nothing to do.` and no
  `Sent to Discord` or `Sent msg`
- Asana side effect: `marked complete:`

### 3.2 Advance notice

Before running any tests, send one message to `#cronicle-automation` and one
email to `hello+qa-testing@protohaven.org` containing:

- list of jobs about to run
- expected duration
- statement that all generated QA alerts are overridden to those destinations
- warning that mock prod data will be created and cleaned up

If failure-path tests are selected, also warn any channels that could receive
direct failure notifications. The operator must acknowledge before the run
proceeds.

### 3.3 Cleanup failure notification

Every mock resource is registered in a `CleanupStack`. Cleanup runs in
`finally`, even after exceptions. If any cleanup step fails:

1. Collect a structured description: resource type, identifier, cleanup error.
2. Send one Discord message to `#cronicle-automation`:
   `QA cleanup failed; manual cleanup required:` followed by the list.
3. Return a non-zero exit code at the end of the QA run.

### 3.4 Mock Neon account convention and final verification

Every QA-created Neon account uses a unique, searchable identity:

```text
email:    hello+qa-cronicle-<job>-<run_id>@protohaven.org
first:    QA Cronicle
last:     <Job> <run_id>
```

After all tests, `verify_no_qa_neon_accounts()` searches Neon for accounts
with email/name matching the QA prefix and fails if any remain. Remaining
accounts are included in the `#cronicle-automation` manual-cleanup notice.

### 3.5 Cronicle log verification

`run_cronicle_sync` returns job IDs and fetched logs, not just an exit code.
The QA harness uses:

- `assert_log_contains(log, substrings)`
- `assert_log_not_contains(log, substrings)`

The old `input("Confirm message was sent")` pass/fail gate is removed.

### 3.6 `run_command.sh` must apply side effects

Update `run_command.sh` so the send step is:

```bash
python3 -m protohaven_api.cli send_comms --path=$ARGS_YAML_OUT --confirm --side-effects
```

This is required so QA can exercise real side effects such as completing Asana
tasks and cancelling classes after successful notification delivery.

### 3.7 Failure-path notifications honor overrides

Several commands call `comms.send_discord_message` directly with hardcoded
channels such as `#tool-automation` or `#class-automation`. Update those paths
(or the central `send_discord_message` helper) so channel targets honor
`CHAN_OVERRIDE` when it is set. QA then routes failure-path messages to
`#cronicle-automation` just like normal generated comms.

### 3.8 Asana task filtering

Several jobs read open Asana tasks. There may be real pending tasks in the
same projects. Every such job must support a QA task filter so only the mock
task is processed:

- `project_requests`
- `phone_messages`
- `donation_requests`
- `shop_tech_applications`
- `instructor_applications`
- `private_instruction`

Add a `--filter_gid` (and, where useful, `--filter_name`) option to these
commands. When set, the command ignores every task except the matching mock
task. QA always passes the mock task GID. This prevents accidental completion
or swallowing of real pending tasks.

## 4. Test order and gates

Run order:

1. Probers and true read-only jobs.
2. Jobs with mock Asana/Airtable/Neon/Booked/Drive setup.
3. Destructive jobs.

CLI gates:

- `--command` and `--after` continue to work.
- `--include-destructive` is required for the destructive group.
- `--skip-advance-notice` is for local debugging only.
- The registry still verifies that every Cronicle event ID is covered.

## 5. Per-job plan

Legend: **Setup**, **Run**, **Assert/Cleanup**.

### 5.1 Probers

#### `probe_events` (`em3xcyglgdj`)

- **Setup:** none.
- **Run:** execute with `{}`; capture job log.
- **Assert:** exit code 0; log contains probe URL and expected success marker.
- **Cleanup:** none.

#### `probe_homepage` (`em403g0czew`)

- **Setup:** none.
- **Run:** execute with `{}`.
- **Assert:** exit code 0; log contains homepage probe success marker.
- **Cleanup:** none.

### 5.2 Readonly jobs

#### `sign_ins` (`elzn07uwhqg`) — `tech_sign_ins`

- **Setup:**
  - Use `forecast.generate(...)` to find a date/shift with a scheduled tech.
  - Insert a temporary Airtable sign-in for that tech at the selected time.
  - Select a zero-tech shift or no-override holiday shift for the alert case.
- **Run:**
  - Known sign-in: `--now=<chosen_iso>`, send_comms on, overrides on.
  - Missing sign-in: `--now=<empty_shift_iso>`, send_comms on, overrides on.
- **Assert:**
  - Known sign-in: no Discord/email send.
  - Missing sign-in: `shift_no_techs` and send to `COVR`.
- **Cleanup:** delete the temporary sign-in record in `finally`.

#### `check_doors` (`em5wzj6552l`) — `check_door_sensors`

- **Setup:** none.
- **Run:** configured door names, overrides, send_comms on.
- **Assert:** exit 0; expected door names are logged; assert a send only if
  warnings are actually generated. Otherwise assert no send.
- **Cleanup:** none.

#### `check_empty_shifts` (`emryv0nravu`) — `check_empty_shifts`

- **Setup:**
  - Scan `forecast.generate(...)` for a nearby empty shift.
  - If none exists, create a temporary `shop_tech_forecast_overrides` record
    that forces an empty shift.
- **Run:**
  `--start=<target_date> --days-ahead=1 --urgent-days=1 --planning-days=1 --no-dedupe`,
  overrides, send_comms on.
- **Assert:** exit 0; empty-shift alert is sent to `COVR`.
- **Cleanup:** delete the temporary override if created.

#### `donations_summary` (`em78dbzj04f`) — `donation_requests`

- **Setup:** create a mock Asana donation-request task; record its GID.
- **Run:** `--filter_gid=<mock_gid>`, overrides, send_comms on.
- **Assert:** exit 0; only the mock task is processed; send to `COVR`.
- **Cleanup:** complete the mock task in `finally`.

#### `check_cameras` (`em5d0rdob1l`) — `check_cameras`

Same pattern as `check_doors`:

- **Setup:** none.
- **Run:** configured camera names, overrides, send_comms on.
- **Assert:** exit 0; expected camera names logged; assert send only if
  warnings are actually generated.
- **Cleanup:** none.

#### `class_emails` (`elwnkuoqf8g`) — `gen_class_emails`

Expanded from one low-attendance case to explicit scenarios. Each scenario
creates a temporary unpublished event and Airtable schedule row.

- **Setup per scenario:**
  - `LOW_ATTENDANCE_7DAYS`: event 5 days out, 0 attendees.
  - `SUPPLY_CHECK_NEEDED`: event 8 days out, supply state `Supply Check Needed`.
  - `CONFIRM`: event 1 day out, 1 registered attendee.
  - `CANCEL`: event 1 day out, 0 attendees.
  - `FOR_TECHS`: event 1 day out, occupancy >10% and <90%.
  - `POST_RUN_SURVEY`: only if `fetch_upcoming_events` can see a recent past
    event; otherwise mark as a unit-test-covered gap.
- **Run:** `--filter=<event_id> --no-published_only`, overrides, send_comms on.
- **Assert:** correct templates in the send_comms log:
  - `instructor_low_attendance`
  - `instructor_check_supplies`
  - `instructor_class_confirmed`
  - `instructor_class_canceled`
  - `registrant_class_confirmed` / `registrant_class_canceled`
  - `tech_openings` / class summary to `COVR`
- **Cleanup:** delete Airtable schedule row, event, registrations, and mock
  accounts in `finally`. Because `run_command.sh` now passes `--side-effects`,
  the `CANCEL` scenario also exercises the class-cancel side effect.

#### `instructor_apps` (`elwnqdz2o8j`) — `instructor_applications`

- **Setup:** create a mock Asana instructor-applicant task; record its GID.
- **Run:** `--filter_gid=<mock_gid>`, overrides, send_comms on.
- **Assert:** exit 0; only the mock task is processed; send to `COVR`.
- **Cleanup:** complete the mock task.

#### `private_instruction` (`elzadpyaqmj`) — `private_instruction`

- **Setup:** create a mock Asana private-instruction request task with form
  notes; record its GID.
- **Run:** `--filter_gid=<mock_gid>`, overrides, send_comms on.
- **Assert:** exit 0; email to `EOVR` and Discord send to `COVR`.
- **Cleanup:** complete the mock task.

#### `private_instruction_daily` (`elziy4cxkp4`) — `private_instruction --daily`

- **Setup:** create a mock Asana private-instruction task created within the
  last 24h; record its GID.
- **Run:** `--filter_gid=<mock_gid> --daily`, overrides, send_comms on.
- **Assert:** exit 0; daily instruction message is sent to `COVR`.
- **Cleanup:** complete the mock task.

#### `shop_tech_apps` (`elw7tf3bg4s`) — `shop_tech_applications`

- **Setup:** create a mock Asana shop-tech-applicant task; record its GID.
- **Run:** `--filter_gid=<mock_gid>`, overrides, send_comms on.
- **Assert:** exit 0; only the mock task is processed; send to `COVR`.
- **Cleanup:** complete the mock task.

#### `square_txns` (`elw7tp2fs4x`) — `transaction_alerts`

- **Setup:** none. Do not create fake Square data in prod Square.
- **Run:** overrides, send_comms on.
- **Assert:**
  - exit 0.
  - Log shows customer, plan, subscription, and unpaid invoice counts fetched.
  - If a real problem exists, assert `square_validation_action_needed` send.
  - If not, assert no send.
- **Cleanup:** none.
- **Coverage note:** alert content is unit-tested with `fake_square`.

#### `membership_val` (`elxbtcrmq3d`) — `validate_memberships`

- **Setup:** create mock Neon accounts with deliberately invalid states:
  - active membership with no end date
  - Shop Tech membership without the Shop Tech API server role
  - AMP membership whose income-based rate does not match the term
- **Run:** `--member_ids=<csv of mock ids>`, overrides, send_comms on.
- **Assert:** exit 0; `membership_validation_problems` lists the expected
  problems and is sent to `COVR`.
- **Cleanup:** delete mock Neon accounts/memberships in `finally`.

#### `instructor_sched` (`em1zpa3989p`) — `gen_instructor_schedule_reminder`

- **Setup:**
  - Create a mock Neon instructor account.
  - Add a temporary Airtable Capabilities row with `Neon ID`, `Email`,
    `Active` checked, and a linked teachable class.
  - Ensure no schedule rows exist for that instructor in the target window.
- **Run:**
  `--start=<target_start> --end=<target_end> --no-require_active --no-require_teachable --filter=<mock_email>`,
  overrides, send_comms on.
- **Assert:** exit 0; email to `EOVR`; `class_automation_summary` to `COVR`.
- **Cleanup:** delete the Capabilities row and mock Neon account.

#### `recertification` (`emitg0mgfzf`) — `recertification`

- **Setup:**
  - Create a mock Neon account.
  - Insert a temporary Airtable pending-recertification record for that mock
    account with a tool code from `get_tool_recert_configs_by_code()`,
    `notified=True`, `suspended=False`, and a past deadline.
- **Run:**
  `--apply --filter_users=<mock_neon_id> --filter_tool_codes=<tool_code> --max_users_affected=1`,
  overrides, send_comms on.
- **Assert:** exit 0; suspension staged/applied for the mock account;
  `member_recert_update` email to `EOVR`; `recertification_summary` to `COVR`.
- **Cleanup:** delete the pending-recertification record and mock Neon account.

### 5.3 Asana task-completing jobs

#### `phone_msgs` (`elw7tkk5n4v`) — `phone_messages`

- **Setup:** create a mock Asana phone-message task; record its GID.
- **Run:** `--filter_gid=<mock_gid> --apply`, overrides, send_comms on.
- **Assert:** exit 0; email to `EOVR`; log contains `marked complete:` for the
  mock task.
- **Cleanup:** ensure the mock task is completed in `finally`.

#### `project_requests` (`elth9zp5g01`) — `project_requests`

- **Setup:** create a mock Asana project-request task with valid notes and a
  future deadline; record its GID.
- **Run:** `--filter_gid=<mock_gid> --apply`, overrides, send_comms on.
- **Assert:** exit 0; Discord send to `COVR`; log contains `marked complete:`
  for the mock task.
- **Cleanup:** ensure the mock task is completed in `finally`.

### 5.4 Additive jobs

#### `sync_tools` (`elvv9mdlx2j`) — `sync_reservable_tools`

- **Setup:**
  - Create a mock Booked resource.
  - Create a temporary Airtable tool record with `Reservable` true,
    `BookedResourceId` pointing at the mock resource, and stale metadata so a
    change is guaranteed.
  - Preflight with `--no-apply --exclude_areas=...`; abort if there are missing
    resources or resource-group mismatches that would affect real tools.
- **Run:**
  - Dry run: `--no-apply --filter=<test_tool_code> --exclude_areas=...`.
  - Apply: same filter without `--no-apply`, overrides, send_comms on.
- **Assert:** exit 0; log shows `Change ...`; `tool_sync_summary` sent to `COVR`.
- **Cleanup:** delete the mock Booked resource and mock Airtable tool record.
- **Note:** placeholder creation is not exercised in prod because the current
  command creates placeholders for all missing reservable tools before applying
  the filter. That path remains unit-tested.

#### `post_classes` (`elzk399t7ph`) — `post_classes_to_neon`

Use the **Eventbrite class creation path**, not Neon.

- **Setup:** create a temporary Airtable schedule row with future sessions,
  confirmed, no event ID, `use_eventbrite` true.
- **Run:**
  `--apply --ovr=<schedule_id> --no-publish --no-registration --no-reserve --no-discounts`,
  overrides, send_comms on.
- **Assert:** exit 0; log shows an Eventbrite event ID created; Airtable row
  receives that event ID; class-scheduled email to `EOVR`; summary to `COVR`.
- **Cleanup:** delete the Eventbrite event, Airtable schedule row, and any
  reservations if the reserve path is enabled.

#### `maint_tasks` (`eltiobjj002`) — `gen_maintenance_tasks`

- **Required command change:** add a `--filter` argument to
  `gen_maintenance_tasks` that restricts processing to a CSV of Airtable
  maintenance record IDs/names.
- **Setup:** create a temporary Airtable recurring-maintenance record due now.
- **Run:** `--filter=<mock_record_id> --apply --num=1`, overrides, send_comms on.
- **Assert:** exit 0; only the mock maintenance task is scheduled; Asana task is
  created; `tech_daily_tasks` is sent to `COVR`.
- **Cleanup:** complete/delete the created Asana task and delete the mock
  Airtable record.

#### `policy_enforcement` (`elzd1jx39n8`) — `enforce_policies`

- **Setup:**
  - Create a mock Neon account.
  - Create a temporary Airtable violation with `Neon ID` set to the mock
    account, recent onset, daily fee > 0, and valid section links.
- **Run:** `--apply`, overrides, send_comms on.
- **Assert:** exit 0; fee created; `violation_started` email to `EOVR`;
  `enforcement_summary` to `COVR`.
- **Cleanup:** delete created fees, the violation record, and the mock account.

#### Backup jobs

`backup_wiki` (`em4u369ldgl`), `backup_neon_accounts` (`emssampvlg3`),
`backup_neon_events` (`emssb5u1vg9`), `backup_sheets` (`emss9yewlg0`)

- **Setup:** use a dedicated QA Drive folder ID.
- **Run:** `--apply --parent_id=<QA_FOLDER_ID>`, overrides, send_comms on.
- **Assert:** exit 0; log contains `Uploaded, id <file_id>`; summary to `COVR`.
- **Cleanup:** delete each uploaded Drive file by file ID in `finally`.

#### `sync_booked_members` (`em5ahun5604`) — `sync_booked_members`

- **Required command change:** make `--include` safe for scoped runs. When
  `--include` is set, the command must only sync the requested Neon accounts
  and must not rewrite the whole Booked Members group from that subset.
- **Setup:** create a mock Neon account that can reserve tools, with no Booked
  ID.
- **Run:** `--include=<mock_email> --apply`, overrides, send_comms on.
- **Assert:** exit 0; Booked user created for the mock account; Neon `Booked
  User ID` is set; `booked_member_sync_summary` sent to `COVR`.
- **Cleanup:** delete the mock Booked user, then the mock Neon account.

#### `restock_discounts` (`em6fgimj413`) — `restock_discounts`

- **Setup:** query current valid unassigned coupon count.
- **Run:**
  `--no-apply --limit=2 --target_qty=<current_count + 2>`, overrides,
  send_comms on.
- **Assert:** exit 0; generated codes logged and pushed to Airtable; summary to
  `COVR`.
- **Cleanup:** delete the Airtable coupon records created by the run.
- **Note:** avoid creating Neon coupon codes in QA because they are
  browser-created and not safely deletable.

#### `refresh_volunteer_memberships` (`em8x5gxfp4t`) — `refresh_volunteer_memberships`

- **Setup:** create a mock Neon account with the Shop Tech role and a
  membership expiring within the command threshold.
- **Run:** `--apply --filter=<mock_neon_id> --limit=1`, overrides, send_comms on.
- **Assert:** exit 0; replacement membership created; summary to `COVR`.
- **Cleanup:** delete the mock Neon account/membership.

#### `sync_clearances` (`em8x5c0o24r`) — `sync_clearances`

- **Constraint:** do **not** modify the instructor-hours sheet.
- **Setup:** none.
- **Run:** `--no-apply --filter_users=<existing_test_email>`, overrides,
  send_comms on or off as appropriate.
- **Assert:** exit 0; command reads the sheet and logs any clearances it would
  change for the filtered user; no Neon or Airtable mutation occurs.
- **Cleanup:** none.
- **Coverage note:** actual Neon clearance apply behavior remains unit-tested;
  Cronicle QA verifies read-path wiring and safe no-apply execution.

### 5.5 Destructive jobs

These require `--include-destructive`.

#### `discord_nick` (`elzx3nvdvu4`) — `enforce_discord_nicknames`

- **Setup:** use `@workshop_protohaven` as the dedicated QA Discord user.
  Create a mock Neon account associated with that Discord ID whose expected
  name differs from the current nickname. Record the original nickname.
- **Run:**
  `--apply --filter=<discord_id> --limit=1 --no-warn_not_associated`,
  overrides with `ARGS_DM_OVERRIDE=DOVR`, send_comms on.
- **Assert:** exit 0; nickname change logged; DM to `DOVR`; summary to `COVR`.
- **Cleanup:** restore the original nickname in `finally`; delete the mock Neon
  account.

#### `discord_role` (`elzsp1fmpsk`) — `update_role_intents`

- **Setup:** use `@workshop_protohaven` and a mock Neon account. Configure Neon
  with a role the QA Discord user currently lacks.
- **Run:**
  `--apply_records --apply_discord --destructive --filter=<discord_id> --max_users_added=1 --max_users_removed=1`,
  overrides with `ARGS_DM_OVERRIDE=DOVR`, send_comms on.
- **Assert:** exit 0; role addition logged; role-change DM/summary sent to QA
  targets.
- **Cleanup:** remove the added Discord role, delete any Airtable intent records
  created for this user, and delete the mock Neon account.

#### `init_memberships` (`em1zpg3sc9r`) — `init_new_memberships`

- **Setup:** create a mock Neon account that satisfies
  `search_new_members_needing_setup`:
  - recent first membership enrollment date
  - membership cost > 10
  - blank `Account Automation Ran`
- **Run:** `--apply --filter=<mock_neon_id> --limit=1`, overrides, send_comms on.
- **Assert:** exit 0; membership start date deferred; `init_membership` email to
  `EOVR`; summary to `COVR`.
- **Cleanup:**
  - Delete the mock Neon account/membership.
  - If a cached Airtable coupon was assigned, clear `Assigned`/`Assignee` on
    that coupon record.

#### `cleanup_orphaned_class_reservations` (`emmtkylp1m7`)

- **Setup:**
  - Create a mock published class with Airtable schedule data.
  - Create one matching automation reservation.
  - Create one orphan automation reservation in the same area at a
    non-matching time.
- **Preflight:** run `--no-apply` and verify the only orphan identified is the
  mock orphan. Abort if real orphans are present.
- **Run:** `--apply --max=1`, overrides, send_comms on.
- **Assert:** exit 0; mock orphan deleted; matching reservation untouched;
  summary to `COVR`.
- **Cleanup:** delete the mock event, Airtable schedule row, matching
  reservation, and any orphan that failed to delete.

## 6. Required supporting command changes

These changes are outside the QA harness but needed for safe, meaningful QA:

1. `run_command.sh`: pass `--side-effects` to `send_comms`.
2. `comms.send_discord_message` or direct failure-path call sites: honor
   `CHAN_OVERRIDE` when set.
3. Add Asana task filtering (`--filter_gid`/`--filter_name`) to:
   - `project_requests`
   - `phone_messages`
   - `donation_requests`
   - `shop_tech_applications`
   - `instructor_applications`
   - `private_instruction`
4. Add `--filter` to `gen_maintenance_tasks`.
5. Make `sync_booked_members --include` safe for scoped runs without rewriting
   the full Members group.
6. Ensure QA mock Neon accounts use the `hello+qa-cronicle-*` convention and
   final verification can search for them.

## 7. Unit-test strategy for the QA harness

- `cronicle.py`: mock `requests` and assert schedule/run/status/log polling.
- `base.py` / `cleanup.py`: assert cleanup runs on exceptions and failed
  cleanups produce the `#cronicle-automation` notice.
- `fixtures/*`: assert factories create the right payloads and register
  cleanup steps.
- `jobs/*`: use `mkcli` from `protohaven_api.testing` where command-level
  behavior is involved; otherwise test job functions with mocker.
- `registry.py`: assert every Cronicle event ID has a descriptor and every
  comm-producing descriptor has override params.
- `verify.py`: assert final Neon search fails when QA accounts remain.

## 8. Definition of done for this QA rework

- No `test_simple` remains.
- Every Cronicle event ID is mapped to a job-specific setup/run/assert/cleanup
  plan.
- All comms are overridden to `#cronicle-automation`,
  `hello+qa-testing@protohaven.org`, and `@workshop_protohaven`.
- Cronicle logs, not manual “Confirm message was sent”, determine pass/fail.
- Cleanup is exception-safe and reports manual cleanup needs to
  `#cronicle-automation`.
- Final Neon search proves no QA mock accounts persist.
- QA harness code lives under `protohaven_api/qa` with unit tests.
