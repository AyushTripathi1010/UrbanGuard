#!/usr/bin/env bash
set -euo pipefail

# Creates extra databases listed in POSTGRES_MULTIPLE_DATABASES (comma-separated)
# alongside the primary POSTGRES_DB created by the entrypoint.
if [ -z "${POSTGRES_MULTIPLE_DATABASES:-}" ]; then
    exit 0
fi

for db in $(echo "$POSTGRES_MULTIPLE_DATABASES" | tr ',' ' '); do
    db="$(echo "$db" | xargs)"
    echo "creating extra database: $db"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
        CREATE DATABASE "$db";
        GRANT ALL PRIVILEGES ON DATABASE "$db" TO "$POSTGRES_USER";
EOSQL
done
