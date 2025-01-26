# Backups

Backups are handled via protohaven_api.cli command `backup_wiki`, run periodically via Cronicle (at https://cron.protohaven.org)

Backups are stored in the [Bookstack Backups](https://drive.google.com/drive/u/0/folders/1KMIh7uVgJvi0_C1wSizMAADFNAYGYNwW) folder of the Operations shared google drive.

Every backup is two gzipped files - one for the DB and one for file assets.

# Restoring backup

From a brand new install (with the appropriate indicated lines commented out in docker-compose.yaml):

```shell
# Just start the DB server, don't init the bookstack main server yet
docker compose up bookstack_db

# In a different terminal on the host machine, copy the backup into the mounted volume
mv /path/to/db_backup.sql.gz ./bookstack_db_data/db_backup.sql.gz

# Extract the file from the archive
gzip -d ./bookstack_db_data/db_backup.sql.gz

# Execute the restore command via docker exec so it runs in the container
docker exec -i --tty bookstack_db /bin/bash -c "mysql -u bookstack -p$DB_PASSWORD bookstackapp < /config/db_backup.sql"

# Ctrl+C to stop the DB server, then start the whole shebang
docker compose up

# There's now a `bookstack_app_data` directory. Let's decompress outside the container and move stuff in.
mv /path/to/files_backup.tar.gz /tmp/files_backup.tar.gz
tar -xvf /tmp/files_backup.tar.gz

# This should have created a /tmp/config folder. This gets mounted as /config in the container, so
# we just need to move everything inside that folder into the volume.
cp -rT /tmp/config/* ./bookstack_app_data/

```
