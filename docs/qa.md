# Post-deploy QA process

## Cronicle jobs

The API key can be found at https://cron.protohaven.org/#Admin?sub=api_keys

```shell
python3 -m protohaven_api.scripts.cronicle_qa_tests --key=<cronicle API key>
```

- [x] runs successfully

_Note: on failure, can run --after=test_name to skip all tests up to and
including `test_name`, or run --command=test_name to just run `test_name`._

## Web services

After deployment, verify that:

- https://api.protohaven.org/
  - [x] After login, page redirects to /member, loads and displays clearances
  - [x] Can logout via top right link
  - [x] Shop Status and Instructor Dashboard links are clickable if shown
  - [ ] Recert card is not visible unless opted in
        (hello+testmember@protohaven.org should not see the link)
  - [x] Recert card shows link to wiki as well as some tools with recerts
        configured.
- https://api.protohaven.org/welcome
  - [ ] Cannot trigger login with empty or all-whitespace entries
  - [ ] Member sign in fails with hello+testnonmember@protohaven.org
  - [ ] Member sign in with hello+testalert@protohaven.org sends the notice
  - [ ] Member sign in with hello+testmember@protohaven.org succeeds but sends
        "multiple accounts" validation alert to `#membership-automation` on
        Discord
  - [ ] Member sign in with hello+testampmake@protohaven.org succeeds, no
        validation alerts
  - [ ] Guest sign in presents waiver and completes - check the `Sign Ins`
        airtable.
- https://api.protohaven.org/events
  - [ ] Displays upcoming calendar events
  - [ ] Shows reservations
  - [ ] Shows classes including instructor and attendee data, both Neon and
        Eventbrite
- https://api.protohaven.org/techs
  - [ ] Cal loads, individual shifts can be clicked and overridden
  - [ ] Cal can change date range, highlights current day
  - [ ] Cal swap overrides send an alert to the #techs channel
  - [ ] Generic shop tech account is not permitted to modify the calendar
  - [ ] Nov 11 is NOT overriden to have zero techs (i.e. Veteran's Day not a
        Protohaven observed holiday)
  - [ ] Members tab shows today's sign-ins, different dates can be shown
  - [ ] Tool states load
  - [ ] Can view history for a tool by clicking the link
  - [ ] Tool guide and clearance documentation status are shown
  - [ ] Docs pages missing approvals can click to the wiki page
  - [ ] Can sort tools by name, urgency, time in state etc.
  - [ ] Can filter tools by area
  - [ ] Storage tab allows for looking up Neon ID by name/email
  - [ ] Storage subscriptions card shows active subscription state - but no
        unpaid invoices if not lead
  - [ ] Storage subscription data is not shown if not logged in
  - [ ] Storage subs have badges where unpaid invoices and can be clicked to
        show links
  - [ ] Storage sub type, ID, and note can all be edited and saved successfully
  - [ ] Areas have some leads assigned to them
  - [ ] Areas has populated "additional contacts" section at the bottom of the
        pane
  - [ ] If a lead: techs roster can set interest, expertise, shift info
  - [ ] If logged in as Shop Tech: techs roster can set interest and expertise
        (but not other fields) for that user
  - [ ] Techs roster can view clearances and sort by name/clearances
  - [ ] Techs roster has some tech photos & bios shown
  - [ ] Techs roster not visible if not a tech (e.g. not logged in)
  - [ ] Techs roster can enroll by search and submit
  - [ ] Techs roster can disenroll via button click and confirmation modal
  - [ ] Techs roster can enroll and create a new member
  - [ ] Events tab can create, register, unregister, and delete a techs-only
        class
  - [ ] Events tab shows registrant name, email, and phone if admin
  - [ ] Events tab can deregister any registrant if admin
  - [ ] Generic shop tech account is not permitted to register for a tech-only
        class
  - [ ] Full tech name is visible on calendar only when logged in as a tech /
        tech lead
  - [ ] Members tab shows "access denied" when not logged in
  - [ ] Area leads only show first name when not signed in
  - [ ] Unauthenticated user cannot see tech roster
  - [ ] In incognito window (not logged in) cannot make edits to tech data, cal
        overrides
  - [ ] Non-tech (hello+testmember@protohavenorg) cannot make edits to tech
        data, cal overrides
- https://api.protohaven.org/instructor
  - [ ] Loads profile data for instructor
  - [ ] Loads classes for instructor, including attendance data
  - [ ] Indicates log submission status for class
  - [ ] Adding a new class on a holiday triggers validation error
  - [ ] Adding a new class on a day with similar area reservations triggers
        validation error
  - [ ] Adding a new class too close to a recent run of that class triggers
        validation error
  - [ ] Can confirm/unconfirm a class
  - [ ] Can set supplies needed / supplies OK
  - [ ] Can switch between volunteer and paid state for class
  - [ ] Log submission button works
- https://api.protohaven.org/event_ticker
  - [ ] Returns JSON of sample classes
- https://api.protohaven.org/staff
  - [ ] Can summarize one or more discord channels, and view photos
  - [ ] Access denied if logged in as hello+testmember@protohaven.org
  - [ ] Ops dashboard shows content with no errors

## Discord events

Login as workshop@ (i.e. `workshop_protohaven` discord user)

Send `TEST_MEMBER_JOIN` in a DM to the Protohaven discord bot; this will run the
`on_member_join` hook which is configured by `main.py` to run
`setup_discord_user` from `protohaven_api.automation.roles.roles`.

Go to https://protohaven.app.neoncrm.com/admin/accounts/1797 and remove
association.

- [ ] When unregistered, `TEST_MEMBER_JOIN` directs to register with Neon

Override and register the user in Neon via the link.

- [ ] Discord association
      [form](https://staging.api.protohaven.org/member?discord_id=asdf)
      correctly sets discord ID on Neon account

Remove all roles from Discord user, and change its display name to something
other than `Test Member`.

- [ ] When missing roles & nickname format, adds them & notifies (both of role
      and nick change)

Add an extra role to the user via Discord. (Does this actually work via
TEST_MEMBER_JOIN? Isn't it just cron based?)

- [ ] When called with registered user with extra roles, notifies of pending
      removal

## Webhooks

Call these when SSH'd into the Cron server via ~/protohaven_api. Make sure to
`source ./venv/bin/activate`

Membership creation webhook

```shell
PH_SERVER_MODE=prod python3 -m protohaven_api.scripts.webhook_qa_tests new_member
```

- [ ] runs successfully

Clearance webhook

```shell
PH_SERVER_MODE=prod python3 -m protohaven_api.scripts.webhook_qa_tests clearance
```

- [ ] runs successfully

Maintenance data webhook

```shell
PH_SERVER_MODE=prod python3 -m protohaven_api.scripts.webhook maintenance
```

- [ ] runs successfully
