#!/usr/bin/env bash
# Runs once, only on first cluster init (docker-entrypoint-initdb.d convention).
# Creates the three NOW! databases and enables pgvector + PostGIS in each.
#
# POSTGRES_DB / POSTGRES_USER come from the postgres image's own env handling;
# this script runs as POSTGRES_USER against the default maintenance connection.
set -euo pipefail

DATABASES=("now_platform" "now_jakarta" "now_bali")

for db in "${DATABASES[@]}"; do
  echo "[init] ensuring database '${db}' exists"
  psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB:-postgres}" <<-EOSQL
    SELECT 'CREATE DATABASE ${db}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${db}')\gexec
EOSQL
done

for db in "${DATABASES[@]}"; do
  echo "[init] enabling extensions in '${db}'"
  psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${db}" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS postgis;
EOSQL
done

echo "[init] databases ready: ${DATABASES[*]}"
