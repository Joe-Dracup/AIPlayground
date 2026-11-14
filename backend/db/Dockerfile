# The official Postgres image, plus extensions. Add more packages to the install line as needed.
FROM postgres:18

# The package only puts PostGIS on disk; a migration turns it on with CREATE EXTENSION.
# Clearing the apt lists afterwards keeps them out of the image, since they're only needed to install.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-18-postgis-3 \
    && rm -rf /var/lib/apt/lists/*
