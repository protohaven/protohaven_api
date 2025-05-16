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
  * [x] Page redirects to /member, loads and displays clearances + links
* https://api.protohaven.org/welcome
  * [x] Member sign in fails with hello+testnonmember@protohaven.org
  * [x] Member sign in with hello+testnoticeboard@protohaven.org sends the notice
  * [x] Member sign in with hello+testmember@protohaven.org succeeds but sends "multiple accounts" validation alert to `#membership-automation` on Discord
  * [] Member sign in with hello+testamp@protohaven.org succeeds but sends "invalid AMP member" validation alert to `#membership-automation` on Discord
  * [x] Guest sign in presents waiver and completes - check the `Sign Ins` airtable.
* https://api.protohaven.org/events
  * [x] Displays upcoming calendar events
  * [x] Shows reservations
  * [x] Shows classes including attendee data
* https://api.protohaven.org/techs
  * [ ] Cal loads, individual shifts can be clicked and overridden, highlights current day
  * [ ] Full name is visible when logged in as a tech / tech lead
  * [ ] Cal can change date range, highlights current day
  * [ ] Cal swap overrides send an alert to the #techs channel
  * [ ] Members tab shows today's sign-ins
  * [ ] Shift page shows the roster, highlights current day
  * [ ] Tool states load, clicking a tool shows info
  * [ ] Storage tab allows for looking up Neon ID by name/email
  * [ ] Areas have some leads assigned to them
  * [ ] Areas has populated "additional contacts" section at the bottom of the pane
  * [ ] Techs roster can set interest, expertise, shift and can view clearances and sort by name/clearances
  * [ ] Events tab can create, register, unregister, and delete a techs-only class
  * [ ] In incognito window (not logged in) cannot make edits to tech data, cal overrides
* https://api.protohaven.org/instructor
  * [x] Loads profile data for instructor
  * [x] Loads classes for instructor, including attendance data
  * [x] Adding, editing, and deleting availability in calendar works (watch the time zones / scheduled time!)
  * [x] Scheduler runs and proposes classes
  * [x] Can confirm/unconfirm a class
  * [x] Log submission button works
* https://api.protohaven.org/member
  * [ ] Discord association [form](https://staging.api.protohaven.org/member?discord_id=asdf) correctly sets discord ID on Neon account
* https://api.protohaven.org/event_ticker
  * [ ] Returns JSON of sample classes
* https://api.protohaven.org/staff
  * [x] Can summarize one or more discord channels, and view photos
  * [x] Access denied if logged in as hello+testmember@protohaven.org

## Discord events

Login as workshop@ (i.e. `workshop_protohaven` discord user)

Send `TEST_MEMBER_JOIN` in a DM to the Protohaven discord bot; this will
run the `on_member_join` hook which is configured by `main.py` to run
`setup_discord_user` from `protohaven_api.automation.roles.roles`.

Go to https://protohaven.app.neoncrm.com/admin/accounts/1797 and remove association.

* [ ] When unregistered, `TEST_MEMBER_JOIN` directs to register with Neon

Override and register the user in Neon. Remove all roles from Discord user, and change its display name to something other than `Test Member`.

* [ ] When missing roles & nickname format, adds them & notifies (both of role and nick change)

Add an extra role to the user via Discord.

* [ ] When called with registered user with extra roles, notifies of pending removal

## Webhooks

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
