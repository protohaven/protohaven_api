#!/usr/bin/env bash

# https://stackoverflow.com/a/821419
set -Eeuo pipefail

source ./venv/bin/activate
echo "DM_OVERRIDE=$DM_OVERRIDE"
echo "CHAN_OVERRIDE=$CHAN_OVERRIDE"
echo "EMAIL_OVERRIDE=$EMAIL_OVERRIDE"
echo "DISCORD_BOT=$DISCORD_BOT"
echo "YAML_OUT=$YAML_OUT"
full_cmd="python3 -m protohaven_api.cli $CMD $ARGS"
echo "> $full_cmd"
eval "$full_cmd"
if [ "$SEND_COMMS" = "1" ]; then
  echo "> python3 -m protohaven_api.cli send_comms --path=$YAML_OUT --confirm"
  python3 -m protohaven_api.cli send_comms --path=$YAML_OUT --confirm
fi
echo '{ "complete": 1, "code": 0 }'
