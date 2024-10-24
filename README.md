# protohaven_api
API system for protohaven

## Architecture

This project contains a CLI and a web server for handling the various software needs of Protohaven.

* **integrations/** contains third-party integrations as python modules
* **automations/** use various integrations combined with problem-specific logic to do useful stuff
* **handlers/** provide Flask web handlers to perform actions and render content.
* **commands/** contains the various commands used as part of the CLI
* **main.py** is the entry point for the Flask web server
* **cli.py** is the entry point for command line usage

## Setup

### Configuration

This module has several config files:

* `.env.defaults` - default values to pass into `config.yaml`
* `.env.secret` - secret values which touch production and must not be checked in - you can request a copy from other Protohaven devs.
* `config.yaml` - provides structure and includes non-secret config info
* `credentials.json` - google session credentials for accessing sheets & calendar - you can request a copy from other Protohaven devs.

### pre-commit

This repo uses pre-commit to autoformat and lint code. Ensure it's set up by following the instructions at https://pre-commit.com/#installation.

**Note: you must activate the virtualenv for pylint to properly run on pre-commit**. This is because it does dynamic checking of modules and needs
those modules to be loaded or else it raises module import errors.

## Running server locally

```
# Set up the environment
source venv/bin/activate
pip install -e .

# Run the server (in dev mode)
# Be sure to download the mock_data.pkl file and place it in the root of the repository dir
# mock_data.pkl is found at https://drive.google.com/file/d/1_Fd0BoAkPqNjPmHUsWW27YXN7XFqZI20/view
LOG_LEVEL=debug CORS=true UNSAFE_NO_RBAC=true PH_SERVER_MODE=dev flask --app protohaven_api.main run

# In prod mode:
LOG_LEVEL=debug CORS=true UNSAFE_NO_RBAC=true PH_SERVER_MODE=prod flask --app protohaven_api.main run
```

In either mode, the server is available at http://localhost:5000.

## Running the CLI

```
# Set up the environment
source venv/bin/activate
pip install -e .


# Run the command
python3 -m protohaven_api.cli project_requests
```

## Running tests and full lint

# These commands are close copies of the ones run by GitHub workflows as pre-submission checks

Unit tests:

```
python -m pytest -v
```

Browser component tests:
```
cd svelte
npx cypress run --component
```

Linter check, all files:

```
pylint -rn -sn --generated-members=client.tasks,client.projects $(git ls-files '*.py') --disable=logging-fstring-interpolation,import-error
```

## Server installation

```
sudo apt install python3.10-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Create the static build file destination for frontend assets
mkdir -p protohaven_api/static/svelte
# Then follow the steps at "Pushing updates" below.

# Having a separate socket config allows us to bind to privileged ports (i.e. 80) without root access
sudo cp ./protohaven_api.service /lib/systemd/system/protohaven_api.service
sudo cp ./protohaven_api.socket /lib/systemd/system/protohaven_api.socket
sudo systemctl daemon-reload
sudo systemctl start protohaven_api.socket
sudo systemctl start protohaven_api.service
```

# Pushing updates

* Create a new release on Github so there's a known tag to refer to the release in case we need to roll back
* SSH into the IONOS server (username and password are in Bitwarden)

```
cd ~/staging_protohaven_api
git status
```

Make a note of the branch name, in case of rollback. If changes to `.env.secret` were made, move the old config to a separate name and `scp` the new one over into its place.

```
git fetch --all
git checkout <release_name>
```

Next, build the static pages. Due to resource limits on the server, it's best to build on the dev machine and `scp` them to the server:

```
source venv/bin/activate
cd svelte
npm run build
cp -r ./build ../protohaven_api/static/svelte
```

Run this on the server to blow away existing build files - **double check that this is the staging instance first!**
```
rm -r ./protohaven_api/static/svelte/*
```

And push the new files to the static svelte directory.
```
scp -r build <USER>@<ADDRESS>:/home/<USER>/staging_protohaven_api/protohaven_api/static/svelte/
```

Finally, restart the service and check its status
```
sudo systemctl restart staging_protohaven_api.service
sudo systemctl status staging_protohaven_api.service
```

Follow the QA check steps in the section at the end of this doc (testing at https://staging.protohaven.api), then turn the staging instance off again to conserve on host RAM:

```
sudo systemctl stop staging_protohaven_api.service
```

When staging is observed to work properly, do the same for prod (just remove all references to `staging_` in the above instructions). The SCP command can be replaced with
```
rm -r ~/protohaven_api/protohaven_api/static/svelte/* && \
cp -r ~/staging_protohaven_api/protohaven_api/static/svelte/* ~/protohaven_api/protohaven_api/static/svelte/
```

## Wordpress plugins

Our main page https://protohaven.org uses custom plugins located in the wordpress/ directory. These were built following the [first block tutorial](https://developer.wordpress.org/block-editor/getting-started/tutorial/).

To develop on them, open a local instance of wordpress:

```shell
cd wordpress/
docker compose up
```

Then run the builder in a separate terminal:

```
cd wordpress/protohaven-class-ticker
npm run start
```

When it's time to deploy, run

```
cd wordpress/protohaven-class-ticker
npm run plugin-zip
```

Then switch in the new plugin:

1. deactivate and uninstall the old plugin (via the [plugins page on the server](https://www.protohaven.org/wp-admin/plugins.php))
1. Use the Upload Plugin button on the [Add Plugins page on the server](https://www.protohaven.org/wp-admin/plugin-install.php) to upload the .zip file created with `npm run plugin-zip`.
1. Activate the plugin
1. Confirm everything looks as expected


# Common Actions

## Maintenance tasks

Maintenance tasks are hosted in Airtable (See 'Tools & Equipment' base, 'Recurring Tasks' sheet). When tasks come due, they are transfered
to the ['Shop & Maintenance Tasks' asana project](https://app.asana.com/0/1202469740885594/1204138662113052).

The following command picks up to three tasks that are due to be scheduled and schedules them in Asana, then generates a post to Discord's #techs-live
channel announcing the new tasks plus the three oldest tasks.

```
PH_SERVER_MODE=prod python3 -m protohaven_api.cli gen_maintenance_tasks > comms.yaml
```

## Forwarding project requests

Project requests are submitted by members and non-members via the Asana form: https://app.asana.com/0/1204107875202537/1204159014519513

These should be forwarded daily to the #help-wanted channel on discord, and can be done automatically via this command:

```
PH_SERVER_MODE=prod python3 -m protohaven_api.cli project_requests  --notify
```

## Managing classes

Class emails will need to be triggered daily. This sends reminders to instructors to check for class materials, reminds both instructors and students when a class is happening, sends post-class feedback requests, and notifies when classes are canceled due to low attendance.

Do so via the following command:

```
LOGLEVEL=info PH_SERVER_MODE=prod python3 -m protohaven_api.cli gen_class_emails > comms.yaml
```

You can then inspect `comms.yaml` to ensure that everything is in order, before sending the comms:

```
PH_SERVER_MODE=prod python3 -m protohaven_api.cli send_comms --path=comms.yaml
```

When classes are canceled, run the following command to remove them from the events page and prevent additional signups:

```
PH_SERVER_MODE=prod python3 -m protohaven_api.cli cancel_classes --id=<id1> --id=<id2>
```

# QA check

After deployment, verify that:

* https://api.protohaven.org/
  * [x] Page loads and displays clearances
* https://api.protohaven.org/welcome
  * [x] Member sign in fails with hello+testnonmember@protohaven.org
  * [x] Member sign in with notice to board/staff sends the notice
  * [x] Member sign in with hello+testmember@protohaven.org succeeds but sends "multiple accounts" validation alert to `#membership-automation` on Discord
  * [x] Guest sign in presents waiver and completes
* https://api.protohaven.org/events
  * [x] Displays upcoming calendar events
  * [x] Shows reservations
  * [x] Shows classes including attendee data
* https://api.protohaven.org/onboarding
  * [x] can check membership (e.g. hello+testmember@protohaven.org)
  * [x] can generate a coupon
  * [x] can setup a discord user
  * [x] can assign roles
  * [x] can view list of onboarding people (bottom of page)
* https://api.protohaven.org/techs
  * [x] Tool states load, clicking a tool shows info
  * [x] Tech shifts load
  * [x] Shift swaps load, individual shifts can be clicked and overridden
  * [x] Areas have some leads assigned to them
  * [x] Shop techs list can set interest, expertise, shift and can view clearances
  * [x] In incognito window (not logged in) cannot make edits to tech data, shift data
* https://api.protohaven.org/instructor/class
  * [x] Loads classes for instructor, including attendance data
  * [x] Adding, editing, and deleting availability in calendar works
  * [x] Scheduler runs and proposes classes
  * [x] Can confirm/unconfirm a class
  * [x] Log submission button works
* https://api.protohaven.org/member
  * [x] Discord association form correctly sets discord ID on Neon account
* https://api.protohaven.org/event_ticker
  * [x] Returns JSON of sample classes
* https://api.protohaven.org/staff
  * [x] Can summarize one or more discord channels, and view photos
* TODO script that sends POST requests to /admin/user_clearances, /admin/neon_membership_created_callback
* Ensure cronicle is running: su to root then use control.sh
