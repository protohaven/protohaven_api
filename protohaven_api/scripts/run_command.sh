#!/usr/bin/env bash

# https://stackoverflow.com/a/821419
set -Eeuo pipefail

source ./venv/bin/activate
echo "DM_OVERRIDE=$DM_OVERRIDE"
echo "CHAN_OVERRIDE=$CHAN_OVERRIDE"
echo "EMAIL_OVERRIDE=$EMAIL_OVERRIDE"
echo "DISCORD_BOT=$DISCORD_BOT"
python3 -m protohaven_api.cli $CMD $ARGS > $OUTFILE
cat $OUTFILE
if [ "$SEND_COMMS" = "1" ]; then
  python3 -m protohaven_api.cli send_comms --path=$OUTFILE --confirm
fi
echo '{ "complete": 1, "code": 0 }'
