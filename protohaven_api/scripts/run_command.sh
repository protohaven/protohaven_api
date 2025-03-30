#!/usr/bin/env sh

# https://stackoverflow.com/a/821419
set -Eeuo pipefail

export DM_OVERRIDE="${ARGS_DM_OVERRIDE}"
export CHAN_OVERRIDE="${ARGS_CHAN_OVERRIDE}"
export EMAIL_OVERRIDE="${ARGS_EMAIL_OVERRIDE}"
export PH_SERVER_MODE="${ARGS_PH_SERVER_MODE}"
export DISCORD_BOT="${ARGS_DISCORD_BOT}"
echo "DM_OVERRIDE=$DM_OVERRIDE"
echo "CHAN_OVERRIDE=$CHAN_OVERRIDE"
echo "EMAIL_OVERRIDE=$EMAIL_OVERRIDE"
echo "PH_SERVER_MODE=$PH_SERVER_MODE"
echo "DISCORD_BOT=$DISCORD_BOT"

cd /protohaven_api
source ./venv/bin/activate
full_cmd="YAML_OUT=$ARGS_YAML_OUT python3 -m protohaven_api.cli $ARGS_CMD $ARGS"
echo "> $full_cmd"
eval "$full_cmd"
if [ "$ARGS_SEND_COMMS" = "1" ]; then
  comms_cmd="python3 -m protohaven_api.cli send_comms --path=$ARGS_YAML_OUT --confirm"
  echo "> $comms_cmd"
  eval "$comms_cmd"
fi
echo '{ "complete": 1, "code": 0 }'
