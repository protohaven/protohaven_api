#!/usr/bin/env bash

echo "Snapshotting Nocodb server container data to nc_data.tar..."
docker run --rm --volumes-from nocodb-nocodb-1 -v $(pwd):/backup ubuntu tar cvf /backup/nc_data.tar /usr/app/data
echo "Snaphsotting Nocodb postgres container to dump.sql..."
docker exec -it nocodb-root_db-1 pg_dump -U postgres -d root_db > dump.sql

echo "Done - remember to commit nc_data.tar and dump.sql when pushing your changes!"
