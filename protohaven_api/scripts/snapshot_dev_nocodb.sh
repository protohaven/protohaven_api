#!/usr/bin/env bash
set -e

echo "Snapshotting nocodb uploads..."
docker run --rm --volumes-from 2_pg-nocodb-1 -v $(pwd):/backup ubuntu tar cvf /backup/nc_data.tar /usr/app/data
echo "Snapshot complete"

echo "Snapshotting nocodb postgres DB..."
docker exec -it 2_pg-root_db-1 pg_dump -U postgres -d root_db > dump.sql
echo "Snapshot complete"
