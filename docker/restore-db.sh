#!/bin/sh
# Restore the lws157 dump into the database named by POSTGRES_DB.
# Run inside the db container:  docker compose exec db sh /docker/restore-db.sh
# Drops and recreates the target database, so only use it on a local copy.
set -eu

DUMP=${1:-/dumps/lws0910.sql}
LIST=$(mktemp)

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\";" \
    -c "CREATE DATABASE \"$POSTGRES_DB\" OWNER \"$POSTGRES_USER\";"

# Skip the adminpack extension: the dump is from PostgreSQL 12 and adminpack
# was removed in PostgreSQL 17. The app does not use it.
pg_restore -l "$DUMP" | grep -v adminpack > "$LIST"

# --no-owner/--no-acl: the dump was taken as user "postgres" on another server.
pg_restore --exit-on-error --no-owner --no-acl -L "$LIST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$DUMP"
rm -f "$LIST"

echo "Restored $DUMP into $POSTGRES_DB"
