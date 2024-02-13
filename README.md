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

**There is currently no staging instance for integrations - actions taken on a local server will affect production.**

```
# Set up the environment
source venv/bin/activate
pip install -e .

# Run the server
python3 -m protohaven_api.main
```

## Running the CLI

```
# Set up the environment
source venv/bin/activate
pip install -e .


# Run the command
python3 -m protohaven_api.cli project_requests
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
