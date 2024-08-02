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

# Having a separate socket config allows us to bind to privileged ports (i.e. 80) without root access
sudo cp ./protohaven_api.service /lib/systemd/system/protohaven_api.service
sudo cp ./protohaven_api.socket /lib/systemd/system/protohaven_api.socket
sudo systemctl daemon-reload
sudo systemctl start protohaven_api.socket
sudo systemctl start protohaven_api.service
```

# Pushing updates

## Building svelte static pages

```
cd svelte
npm run build
rm -r ../protohaven_api/static/svelte
cp -r ./build ../protohaven_api/static/svelte
cd ../ && git add ./protohaven_api/static/svelte/*
```

Various routes are set up in Flask to remap to static assets in ./protohaven_api/static/svelte.

* Commit and push the static build changes to main.
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
sudo systemctl restart protohaven_api.service
```

You can view the status of the restart with:

```
sudo systemctl status protohaven_api.service
```

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

* https://api.protohaven.org/onboarding loads and can check membership
* https://api.protohaven.org/tech_lead loads
* https://api.protohaven.org/instructor/class loads, can run scheduler, and can confirm/unconfirm a class
