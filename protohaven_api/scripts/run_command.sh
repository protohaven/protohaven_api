#!/usr/bin/env bash

# https://stackoverflow.com/a/821419
set -Eeuo pipefail

source ./venv/bin/activate
echo "DM override: $DM_OVERRIDE"
echo "Channel override: $CHAN_OVERRIDE"
echo "Email override: $EMAIL_OVERRIDE"
python3 -m protohaven_api.cli $CMD $ARGS > $OUTFILE
cat $OUTFILE
if [ "$SEND_COMMS" = "1" ]; then
  python3 -m protohaven_api.cli send_comms --path=$OUTFILE --confirm
fi
echo '{ "complete": 1, "code": 0 }'
