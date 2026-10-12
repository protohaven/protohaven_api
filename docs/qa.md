# Post-deploy QA process

## Cronicle jobs

Convert `protohaven_api/scripts/backup_cronicle_jobs.py` to a CLI command (e.g.
python3 -m protohaven_api.cli backup_cronicle --api_key=...

## Web services

If these test cases can be exercised in Cypress/python tests, implement tests.

If they require a production environment to test, add them to `qa/`.

- https://api.protohaven.org/
  - After login, page redirects to /member, loads and displays clearances
  - Can logout via top right link
  - Shop Status and Instructor Dashboard links are clickable if shown
  - Recert card is not visible unless opted in (hello+testmember@protohaven.org
    should not see the link)
  - Recert card shows link to wiki as well as some tools with recerts
    configured.
- https://api.protohaven.org/welcome
  - Cannot trigger login with empty or all-whitespace entries
  - Member sign in fails with hello+testnonmember@protohaven.org
  - Member sign in with hello+testalert@protohaven.org sends the notice
  - Member sign in at the wrong time presents a warning display
  - Member sign in with hello+testmember@protohaven.org succeeds but sends
    "multiple accounts" validation alert to `#membership-automation` on Discord
  - Displays the day's reservations when valid member logs in, including ones
    from earlier in the day
  - Member sign in with hello+testampmake@protohaven.org succeeds, no validation
    alerts
  - Guest sign in presents waiver (but not member agreement) and completes -
    check the `Sign Ins` airtable.
- https://api.protohaven.org/events
  - Displays upcoming calendar events
  - Shows reservations; can hover to see more details
  - Shows classes including instructor and attendee data, both Neon and
    Eventbrite
- https://api.protohaven.org/techs
  - Door lock state shown at top nav if logged in; matches Wyze state
  - Cal loads, individual shifts can be clicked, overridden, reverted
  - Cal can change date range, highlights current day
  - Cal swap overrides send an alert to the #techs channel
  - Nov 11 is NOT overriden to have zero techs (i.e. Veteran's Day not a
    Protohaven observed holiday)
  - Nov 27 IS overridden to have zero techs (Thanksgiving is a protohaven
    holiday)
  - Members tab shows today's sign-ins, different dates can be shown
  - Searching by member is possible; shows sign in day stats
  - Tool states load
  - Can view history for a tool by clicking the link
  - Tool guide and clearance documentation status are shown
  - Docs pages missing approvals can click to the wiki page
  - Can sort tools by name, urgency, time in state etc.
  - Can filter tools by area
  - Storage tab allows for looking up Neon ID by name/email
  - Storage subscriptions card shows active subscription state - but no unpaid
    invoices if not lead
  - Storage subscription data is not shown if not logged in
  - Storage subs have badges where unpaid invoices and can be clicked to show
    links
  - Storage sub type, ID, and note can all be edited and saved successfully
  - Airtable-based storage subs shown; help text link to Airtable works
  - Areas have some leads assigned to them
  - Areas has populated "additional contacts" section at the bottom of the pane
  - If a lead: techs roster can set interest, expertise, shift info
  - If logged in as Shop Tech: techs roster can set interest and expertise (but
    not other fields) for that user
  - Techs roster can view clearances and sort by name/clearances
  - Techs roster has some tech photos & bios shown
  - Techs roster not visible if not a tech (e.g. not logged in)
  - Techs roster can disenroll via button click and confirmation modal (use Shop
    Tech user)
  - Techs roster can enroll by search and submit (use Shop Tech user)
  - Techs roster can enroll and create a new member (delete in Neon CRM after)
  - Events tab can create, register, unregister, and delete a techs-only class
  - Attendance tab can run an attendance report over a time period
  - Attendance tab not shown when not logged in as a lead
  - Full tech name is visible on calendar only when logged in as a tech / tech
    lead
  - Members tab shows "access denied" when not logged in
  - Area leads only show first name when not signed in
  - Unauthenticated user cannot see tech roster
  - In incognito window (not logged in) cannot make edits to tech data, cal
    overrides
  - Non-tech (hello+testmember@protohavenorg) cannot make edits to tech data,
    cal overrides
- https://api.protohaven.org/instructor
  - Cannot access if not logged in/instructor
  - Loads profile data for instructor
  - Loads classes for instructor, including attendance data
  - Instructors missing the Instructor API Server Role in Neon are highlighted
    on the roster
  - Instructors missing a Neon account but present in Capabilities are
    highlighted on the roster
  - Adding a new class on a holiday triggers validation error
  - Adding a new class on a day with similar area reservations triggers
    validation error
  - Adding a new class too close to a recent run of that class triggers
    validation error
  - Scheduling sessions more than 10 days apart triggers validation error (check
    dates to ensure same days/times on validation step)
  - Instructor can override schedule validation error
  - Schedule overrides send alerts to #edu-leads discord
  - Can mark unavailable for a class that hasn't posted
  - Class timing is correct (i.e. 6pm on scheduler -> 6pm when scheduled)
  - Can set supplies needed / supplies OK; sends notice to #supply-automation
  - Can switch between volunteer and paid state for class
  - Log submission button works; log form is correctly populated (especially
    clearances)
  - Roster page shown for leads/admins; view page and Neon CRM links work.
  - Instructor creation / enrollment / disenrollment via roster.
  - Roster highlights missing paperwork on file (DD/Bio/W9)
- https://api.protohaven.org/event_ticker
- https://api.protohaven.org/staff

## Webhooks

Convert these scripts to run using the environment in `qa/`, including comms
redirects and operating on ephemeral testing data.

Membership creation webhook

```shell
PH_SERVER_MODE=prod python3 -m protohaven_api.scripts.webhook_qa_tests new_member
```

Clearance webhook

```shell
PH_SERVER_MODE=prod python3 -m protohaven_api.scripts.webhook_qa_tests clearance
```

Maintenance data webhook

```shell
PH_SERVER_MODE=prod python3 -m protohaven_api.scripts.webhook_qa_tests maintenance
```
