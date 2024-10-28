#!/usr/bin/env bash

source ./venv/bin/activate
# python3 -m protohaven_api.cli $CMD $ARGS > $OUTFILE
cat $OUTFILE
if [ "$SEND_COMMS" = "1" ]; then
  python3 -m protohaven_api.cli send_comms --path=$OUTFILE --confirm
fi
