# protohaven_api
API system for protohaven

## Setup

### Configuration

This module requires a `config.yaml` file to run - chat with other protohaven devs to receive a copy.

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
PH_CONFIG=test_config.yaml python -m pytest -v
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

Various routes are set up in Flask to remap to static assets in ./protohaven_api/static/svelte.

* Create a new release on Github so there's a known tag to refer to the release in case we need to roll back
* SSH into the IONOS server (username and password in Bitwarden)

```
cd ~/protohaven_api
git status
```

Make a note of the branch name, again in case of rollback. If changes to `config.yaml` were made, move the old config to a separate name and `scp` the new one over into its place.

```
git fetch --all
git checkout <release_name>
```


Next, build the static pages (Note: you may likely have to build on your dev machine and scp them to the server):

```
cd svelte
npm run build
rm -r ../protohaven_api/static/svelte
cp -r ./build ../protohaven_api/static/svelte

# To push to the server
scp -r build <USER>@<ADDRESS>:/home/<USER>/staging_protohaven_api/svelte/build

# You may also need to push the config file
scp config.yaml <USER>@<ADDRESS>:/home/<USER>/staging_protohaven_api/config_new.yaml

```

Then SSH into the server and copy over the build files, leaving a copy of the old config just in case

```
cd path/to/staging_protohaven_api
rm -r ./protohaven_api/static/svelte/* && cp -r ./svelte/build ./protohaven_api/static/svelte
cp config.yaml config_old_v0_XX_XX.yaml
mv config_new.yaml config.yaml
```

Finally, restart the service and check its status

```
# For prod; staging TODO
sudo systemctl restart protohaven_api.service
sudo systemctl status protohaven_api.service
```

When staging is observed to work properly, do the same for prod.

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

Class emails will need to be triggered daily. This sends reminders to instructors to check for class materials, reminds both instructors and students when a class is happening, sends post-class feedback requests, and notifies when classes are cancelled due to low attendance.

Do so via the following command:

```
LOGLEVEL=info PH_SERVER_MODE=prod python3 -m protohaven_api.cli gen_class_emails > comms.yaml
```

You can then inspect `comms.yaml` to ensure that everything is in order, before sending the comms:

```
PH_SERVER_MODE=prod python3 -m protohaven_api.cli send_comms --path=comms.yaml
```

When classes are cancelled, run the following command to remove them from the events page and prevent additional signups:

```
PH_SERVER_MODE=prod python3 -m protohaven_api.cli cancel_classes --id=<id1> --id=<id2>
```

# QA check

After deployment, verify that:

* https://api.protohaven.org/welcome
  * Member sign in fails with hello+testnonmember@protohaven.org
  * Member sign in with hello+testmember@protohaven.org succeeds but sends "multiple accounts" validation alert to `#membership-automation` on Discord
  * Guest sign in presents waiver and completes
* https://api.protohaven.org/events
  * Displays upcoming calendar events
  * Shows reservations
  * Shows classes including attendee data
* https://api.protohaven.org/onboarding
  * can check membership
  * can generate a coupon
  * can setup a discord user
* https://api.protohaven.org/techs
  * Tool states load, clicking a tool shows info
  * Tech shifts load
  * Shift swaps load, individual shifts can be clicked and overridden
  * Areas have some leads assigned to them
  * Shop techs list can set interest, expertise, shift and can view clearances
  * In incognito window (not logged in) cannot make edits to tech data, shift data
* https://api.protohaven.org/instructor/class
  * Loads classes for instructor, including attendance data
  * Adding, editing, and deleting availability in calendar works
  * Scheduler runs and proposes classes
  * Can confirm/unconfirm a class
  * Log submission button works
* https://api.protohaven.org/member
  * Discord association form correctly sets discord ID on Neon account
* Ensure cronicle is running, su to root then use control.sh
