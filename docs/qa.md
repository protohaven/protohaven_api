# Post-deploy QA process

## Web services

After deployment, verify that:

* https://api.protohaven.org/
  * [ ] Page loads and displays clearances
* https://api.protohaven.org/welcome
  * [ ] Member sign in fails with hello+testnonmember@protohaven.org
  * [ ] Member sign in with notice to board/staff sends the notice
  * [ ] Member sign in with hello+testmember@protohaven.org succeeds but sends "multiple accounts" validation alert to `#membership-automation` on Discord
  * [ ] Guest sign in presents waiver and completes
* https://api.protohaven.org/events
  * [ ] Displays upcoming calendar events
  * [ ] Shows reservations
  * [ ] Shows classes including attendee data
* https://api.protohaven.org/onboarding
  * [ ] can check membership (e.g. hello+testmember@protohaven.org)
  * [ ] can generate a coupon
  * [ ] can setup a discord user
  * [ ] can assign roles
  * [ ] can view list of onboarding people (bottom of page)
* https://api.protohaven.org/techs
  * [ ] Tool states load, clicking a tool shows info
  * [ ] Tech shifts load
  * [ ] Shift swaps load, individual shifts can be clicked and overridden
  * [ ] Areas have some leads assigned to them
  * [ ] Shop techs list can set interest, expertise, shift and can view clearances
  * [ ] In incognito window (not logged in) cannot make edits to tech data, shift data
* https://api.protohaven.org/instructor/class
  * [ ] Loads classes for instructor, including attendance data
  * [ ] Adding, editing, and deleting availability in calendar works
  * [ ] Scheduler runs and proposes classes
  * [ ] Can confirm/unconfirm a class
  * [ ] Log submission button works
* https://api.protohaven.org/member
  * [ ] Discord association form correctly sets discord ID on Neon account
* https://api.protohaven.org/event_ticker
  * [ ] Returns JSON of sample classes
* https://api.protohaven.org/staff
  * [ ] Can summarize one or more discord channels, and view photos

## Discord events

Send `TEST_MEMBER_JOIN` in a DM to the Protohaven discord bot; this will
run the `on_member_join` hook which is configured by `main.py` to run
`setup_discord_user` from `protohaven_api.automation.roles.roles`.

* [ ] When called with an unregistered Dicsord user, directs to register with Neon
* [ ] When called with registered user with missing roles, adds them & notifies
* [ ] When called with registered user with invalid nickname, changes & notifies
* [ ] When called with registered user with extra roles, notifies of pending removal

## Webhooks

Membership creation webhook

```shell
python3 -m protohaven_api.scripts.test_webhooks new_member
```
* [ ] runs successfully

Clearance webhook

```shell
python3 -m protohaven_api.scripts.test_webhooks clearance
```
* [ ] runs successfully

## CLI commands

* [ ] Ensure cronicle is running: `su root` then use `control.sh`

```shell
python3 -m protohaven_api.scripts.test_cronicle all
```
* [ ] runs successfully
