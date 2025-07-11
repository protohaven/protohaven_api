#!/usr/bin/env bash

echo "This script will:"
echo "  1. Stop NocoDB containers (if running) and delete any existing NocoDB data"
echo "  2. Load dev/snapshotted data (dump.sql and nc_data.tar in the current directory)"
echo "  3. Launch NocoDB as a docker container."

if ! command -v docker &> /dev/null; then
    echo "Error: 'docker' command not found. Please install Docker."
    exit 1
fi

# Check if 'docker-compose' is available
if ! command -v docker compose &> /dev/null; then
    echo "Error: 'docker-compose' command not found. Please install Docker Compose."
    exit 1
fi

read -p "Proceed? Enter to continue, Ctrl+C to cancel:"

HDR=" ====== "

# If you already have a running instance of Nocodb and wish to re-initialize,
# first we must stop the containers and delete the volumes:
echo -e "$HDR Stopping any existing Nocodb instance and deleting data (if any)... $HDR"
docker compose down
docker volume rm protohaven_api_pg_data protohaven_api_nc_data

# Start and load the postgres data, before Nocodb has a chance to initialize
echo -e "$HDR Loading postgres data from dump.sql... $HDR"
docker compose up -d nocodb_db
sleep 5 # Wait for container to be online
cat nocodb/dump.sql | docker exec -i nocodb_db psql -U postgres -d root_db

# Load the other nocodb data into the volume before nocodb inits it
echo -e "$HDR Unpacking Nocodb nc_data.tar... $HDR"
docker run --rm --volume protohaven_api_nc_data:/usr/app/data -v $(pwd)/nocodb:/backup ubuntu bash -c "cd /usr/app/data && tar xvf /backup/nc_data.tar --strip 1"

echo -e "\n\nDone! Run 'docker compose watch', then browse to http://localhost:9090 and login with:\n- username: admin@example.com\n- password: password"
