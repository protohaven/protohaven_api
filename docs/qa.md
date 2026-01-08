# Post-deploy QA process

## Cronicle jobs

The API key can be found at https://cron.protohaven.org/#Admin?sub=api_keys

```shell
python3 -m protohaven_api.scripts.cronicle_qa_tests --key=<cronicle API key>
```
* [x] runs successfully

*Note: on failure, can run --after=test_name to skip all tests up to and including `test_name`, or run --command=test_name to just run `test_name`.*

## Web services

After deployment, verify that:

* https://api.protohaven.org/
  * [ ] After login, page redirects to /member, loads and displays clearances + links
* https://api.protohaven.org/welcome
  * [ ] Member sign in fails with hello+testnonmember@protohaven.org
  * [ ] Member sign in with hello+testalert@protohaven.org sends the notice
  * [ ] Member sign in with hello+testmember@protohaven.org succeeds but sends "multiple accounts" validation alert to `#membership-automation` on Discord
  * [ ] Member sign in with hello+testampmake@protohaven.org succeeds, no validation alerts
  * [ ] Guest sign in presents waiver and completes - check the `Sign Ins` airtable.
* https://api.protohaven.org/events
  * [ ] Displays upcoming calendar events
  * [ ] Shows reservations
  * [ ] Shows classes including instructor and attendee data, both Neon and Eventbrite
* https://api.protohaven.org/techs
  * [ ] Cal loads, individual shifts can be clicked and overridden, highlights current day
  * [ ] Cal can change date range, highlights current day
  * [ ] Cal swap overrides send an alert to the #techs channel
  * [ ] Members tab shows today's sign-ins
  * [ ] Tool states load
  * [ ] Can view history for a tool by clicking the link
  * [ ] Tool guide and clearance documentation status are shown
  * [ ] Docs pages missing approvals can click to the wiki page
  * [ ] Can sort tools by name, urgency, time in state etc.
  * [ ] Can filter tools by area
  * [ ] Storage tab allows for looking up Neon ID by name/email
  * [ ] Areas have some leads assigned to them
  * [ ] Areas has populated "additional contacts" section at the bottom of the pane
  * [ ] Techs roster can set interest, expertise, shift and can view clearances and sort by name/clearances
  * [ ] Techs roster has some tech photos & bios shown
  * [ ] Events tab can create, register, unregister, and delete a techs-only class
  * [ ] Full name is visible only when logged in as a tech / tech lead
  * [ ] Members tab shows "access denied" when not logged in
  * [ ] Area leads only show first name when not signed in
  * [ ] Unauthenticated user only sees at most the first names on Roster
  * [ ] In incognito window (not logged in) cannot make edits to tech data, cal overrides
  * [ ] Non-tech (hello+testmember@protohavenorg) cannot make edits to tech data, cal overrides
* https://api.protohaven.org/instructor
  * [ ] Loads profile data for instructor
  * [ ] Loads classes for instructor, including attendance data
  * [ ] Adding a new class on a holiday triggers validation error
  * [ ] Adding a new class on a day with similar area reservations triggers validation error
  * [ ] Adding a new class too close to a recent run of that class triggers validation error
  * [ ] Can confirm/unconfirm a class
  * [ ] Log submission button works
* https://api.protohaven.org/event_ticker
  * [ ] Returns JSON of sample classes
* https://api.protohaven.org/staff
  * [ ] Can summarize one or more discord channels, and view photos
  * [ ] Access denied if logged in as hello+testmember@protohaven.org
  * [ ] Ops dashboard shows content with no errors

## Discord events

Login as workshop@ (i.e. `workshop_protohaven` discord user)

Send `TEST_MEMBER_JOIN` in a DM to the Protohaven discord bot; this will
run the `on_member_join` hook which is configured by `main.py` to run
`setup_discord_user` from `protohaven_api.automation.roles.roles`.

Go to https://protohaven.app.neoncrm.com/admin/accounts/1797 and remove association.

* [ ] When unregistered, `TEST_MEMBER_JOIN` directs to register with Neon

Override and register the user in Neon via the link.

* [ ] Discord association [form](https://staging.api.protohaven.org/member?discord_id=asdf) correctly sets discord ID on Neon account

Remove all roles from Discord user, and change its display name to something other than `Test Member`.

* [ ] When missing roles & nickname format, adds them & notifies (both of role and nick change)

Add an extra role to the user via Discord. (Does this actually work via TEST_MEMBER_JOIN? Isn't it just cron based?)

* [ ] When called with registered user with extra roles, notifies of pending removal

## Webhooks

Call these when SSH'd into the Cron server via ~/protohaven_api. Make sure to `source ./venv/bin/activate`

Membership creation webhook

```shell
python3 -m protohaven_api.scripts.webhook_qa_tests new_member
```
* [ ] runs successfully

Clearance webhook

```shell
python3 -m protohaven_api.scripts.webhook_qa_tests clearance
```
* [ ] runs successfully

Maintenance data webhook

```shell
python3 -m protohaven_api.scripts.webhook maintenance
```
* [ ] runs successfully
