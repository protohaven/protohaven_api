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

Alternatively if you're using NixOS, create a `.envrc` file with the text `use nix`, then execute `direnv allow`
in the `protohaven_api` directory to automatically load the environment specified in `shell.nix`. This requires
the `direnv` utility to be installed.

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

## Bare server installation (deprecated)

Set server to EST; otherwise some date math will break

```
sudo timedatectl set-timezone America/New_York
```

Install venv if you're running via Cronicle, otherwise the docker container will include all deps

```
sudo apt install python3.10-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Create the static build file destination for frontend assets

```
mkdir -p protohaven_api/static/svelte
```

Then follow the steps at "Pushing updates" below.

## Docker container setup

`cd` to `protohaven_api`, then `docker compose build`. You may need to ensure the `ARG release` is set to the current release of `protohaven_api` for the cronicle docker container.

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
cd path/to/docker-compose-yaml-file
docker compose restart
docker compose logs -t --follow --tail 50
```

Follow the [QA check steps](docs/qa.md) (testing with https://staging.protohaven.api), then turn the staging instance off again to conserve on host RAM:

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

See [docs/qa.md](docs/qa.md)

## Contributors

Scott Martin
