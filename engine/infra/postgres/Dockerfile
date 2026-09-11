# Postgres 16 + pgvector + PostGIS.
#
# Base image is the official pgvector/pgvector:pg16 build (Debian bookworm,
# not EOL) which already has the PGDG apt repo configured and pgvector
# compiled in. We add PostGIS from the same PGDG repo so both extensions are
# installable via CREATE EXTENSION in every database (see
# ./init/01-create-databases.sh).
#
# (postgis/postgis:16-* images are still on Debian bullseye, whose security
# apt repo has gone stale/EOL and fails `apt-get update` — hence building
# the other direction: postgis on top of the pgvector image.)
FROM pgvector/pgvector:pg16

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-postgis-3 \
    && rm -rf /var/lib/apt/lists/*
