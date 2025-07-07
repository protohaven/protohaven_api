#!/usr/bin/env bash

echo "Snapshotting Nocodb server container data to nc_data.tar..."
docker run --rm --volumes-from nocodb_frontend -v $(pwd)/nocodb:/backup ubuntu tar cvf /backup/nc_data.tar /usr/app/data
echo "Snaphsotting Nocodb postgres container to dump.sql..."
docker exec -it nocodb_db pg_dump -U postgres -d root_db > nocodb/dump.sql

echo "Done - remember to commit nc_data.tar and dump.sql when pushing your changes!"
