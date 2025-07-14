# ===========================================================================
# Tools
ARG GO_VERSION=1.22.4
FROM golang:${GO_VERSION}-alpine AS tools

ENV TOOLS_VERSION 0.8.1

RUN apk update && apk add --no-cache git gcc musl-dev \
    && go install github.com/timescale/timescaledb-tune/cmd/timescaledb-tune@latest \
    && go install github.com/timescale/timescaledb-parallel-copy/cmd/timescaledb-parallel-copy@latest
# ===========================================================================

#ARG BASE_IMAGE=postgres:17-alpine3.22
FROM postgres:17-alpine3.22

#LABEL maintainer="PostGIS Project - https://postgis.net" \
#      org.opencontainers.image.description="PostGIS 3.5.2+dfsg-1.pgdg110+1 spatial database extension with PostgreSQL 17 bullseye" \
#      org.opencontainers.image.source="https://github.com/postgis/docker-postgis"

ENV POSTGIS_MAJOR 3
ENV POSTGIS_VERSION 3.5.2+dfsg-1.pgdg110+1

ARG ALPINE_VERSION=3.21
ARG CLANG_VERSION=19
ARG PG_MAJOR=17
ARG PG_VERSION=17
ARG PG_MAJOR_VERSION=17
ARG PGVECTOR_VERSION='v0.7.2'


#LABEL maintainer="PostGIS Project - https://postgis.net" \
#      org.opencontainers.image.description="PostGIS 3.5.3 spatial database extension with PostgreSQL 17 Alpine" \
#      org.opencontainers.image.source="https://github.com/postgis/docker-postgis"

ENV POSTGIS_VERSION 3.5.3
ENV POSTGIS_SHA256 44222ed2b8f742ffc1ceb429b09ebb484c7880f9ba27bf7b6b197346cdd25437

RUN set -eux \
    && apk add --no-cache --virtual .fetch-deps \
        ca-certificates \
        openssl \
        tar \
    \
    && wget -O postgis.tar.gz "https://github.com/postgis/postgis/archive/${POSTGIS_VERSION}.tar.gz" \
    && echo "${POSTGIS_SHA256} *postgis.tar.gz" | sha256sum -c - \
    && mkdir -p /usr/src/postgis \
    && tar \
        --extract \
        --file postgis.tar.gz \
        --directory /usr/src/postgis \
        --strip-components 1 \
    && rm postgis.tar.gz \
    \
    && apk add --no-cache --virtual .build-deps \
        \
        gdal-dev \
        geos-dev \
        proj-dev \
        proj-util \
        sfcgal-dev \
        \
        # The upstream variable, '$DOCKER_PG_LLVM_DEPS' contains
        #  the correct versions of 'llvm-dev' and 'clang' for the current version of PostgreSQL.
        # This improvement has been discussed in https://github.com/docker-library/postgres/pull/1077
        $DOCKER_PG_LLVM_DEPS \
        \
        autoconf \
        automake \
        cunit-dev \
        file \
        g++ \
        gcc \
        gettext-dev \
        git \
        json-c-dev \
        libtool \
        libxml2-dev \
        make \
        pcre2-dev \
        perl \
        protobuf-c-dev \
    \
# build PostGIS - with Link Time Optimization (LTO) enabled
    && cd /usr/src/postgis \
    && gettextize \
    && ./autogen.sh \
    && ./configure \
        --enable-lto \
    && make -j$(nproc) \
    && make install \
    \
# This section is for refreshing the proj data for the regression tests.
# It serves as a workaround for an issue documented at https://trac.osgeo.org/postgis/ticket/5316
# This increases the Docker image size by about 1 MB.
    && projsync --system-directory --file ch_swisstopo_CHENyx06_ETRS \
    && projsync --system-directory --file us_noaa_eshpgn \
    && projsync --system-directory --file us_noaa_prvi \
    && projsync --system-directory --file us_noaa_wmhpgn \
# This section performs a regression check.
    && mkdir /tempdb \
    && chown -R postgres:postgres /tempdb \
    && su postgres -c 'pg_ctl -D /tempdb init' \
    && su postgres -c 'pg_ctl -D /tempdb -c -l /tmp/logfile -o '-F' start ' \
    && cd regress \
    && make -j$(nproc) check RUNTESTFLAGS="--extension --verbose" PGUSER=postgres \
    \
    && su postgres -c 'psql    -c "CREATE EXTENSION IF NOT EXISTS postgis;"' \
    && su postgres -c 'psql    -c "CREATE EXTENSION IF NOT EXISTS postgis_raster;"' \
    && su postgres -c 'psql    -c "CREATE EXTENSION IF NOT EXISTS postgis_sfcgal;"' \
    && su postgres -c 'psql    -c "CREATE EXTENSION IF NOT EXISTS fuzzystrmatch; --needed for postgis_tiger_geocoder "' \
    && su postgres -c 'psql    -c "CREATE EXTENSION IF NOT EXISTS address_standardizer;"' \
    && su postgres -c 'psql    -c "CREATE EXTENSION IF NOT EXISTS address_standardizer_data_us;"' \
    && su postgres -c 'psql    -c "CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder;"' \
    && su postgres -c 'psql    -c "CREATE EXTENSION IF NOT EXISTS postgis_topology;"' \
    && su postgres -c 'psql -t -c "SELECT version();"'              >> /_pgis_full_version.txt \
    && su postgres -c 'psql -t -c "SELECT PostGIS_Full_Version();"' >> /_pgis_full_version.txt \
    && su postgres -c 'psql -t -c "\dx"' >> /_pgis_full_version.txt \
    \
    && su postgres -c 'pg_ctl -D /tempdb --mode=immediate stop' \
    && rm -rf /tempdb \
    && rm -rf /tmp/logfile \
    && rm -rf /tmp/pgis_reg \
# add .postgis-rundeps
    && apk add --no-cache --virtual .postgis-rundeps \
        \
        gdal \
        geos \
        proj \
        sfcgal \
        \
        json-c \
        libstdc++ \
        pcre2 \
        protobuf-c \
        \
        # ca-certificates: for accessing remote raster files
        #   fix https://github.com/postgis/docker-postgis/issues/307
        ca-certificates \
# clean
    && cd / \
    && rm -rf /usr/src/postgis \
    && apk del .fetch-deps .build-deps \
# At the end of the build, we print the collected information
# from the '/_pgis_full_version.txt' file. This is for experimental and internal purposes.
    && cat /_pgis_full_version.txt


RUN mkdir -p /docker-entrypoint-initdb.d
COPY ./postgis.d/initdb-postgis.sh /docker-entrypoint-initdb.d/10_postgis.sh
COPY ./postgis.d/update-postgis.sh /usr/local/bin

#===========================================================================
# TimescaleDB
ARG OSS_ONLY

#LABEL maintainer="Timescale https://www.timescale.com"


RUN set -ex; \
    echo "https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_VERSION}/community/" >> /etc/apk/repositories; \
    apk update; \
    if [ "$PG_MAJOR_VERSION" -ge 16 ] ; then \
        apk add --no-cache postgresql${PG_VERSION}-plpython3; \
    fi



RUN set -ex; \
    apk update; \
    apk add --no-cache --virtual .vector-deps \
        postgresql${PG_VERSION}-dev \
        git \
        build-base \
        clang${CLANG_VERSION} \
        llvm${CLANG_VERSION}-dev \
        llvm${CLANG_VERSION}; \
    git clone --branch ${PGVECTOR_VERSION} https://github.com/pgvector/pgvector.git /build/pgvector; \
    cd /build/pgvector; \
    make; \
    make install; \
    apk del .vector-deps;

COPY timescaledb.d/* /docker-entrypoint-initdb.d/
COPY --from=tools /go/bin/* /usr/local/bin/
#COPY --from=oldversions /usr/local/lib/postgresql/timescaledb-*.so /usr/local/lib/postgresql/
#COPY --from=oldversions /usr/local/share/postgresql/extension/timescaledb--*.sql /usr/local/share/postgresql/extension/

ARG TS_VERSION
RUN set -ex \
    && apk add --no-cache --virtual .fetch-deps \
                ca-certificates \
                git \
                openssl \
                openssl-dev \
                tar \
    && mkdir -p /build/ \
    && git clone https://github.com/timescale/timescaledb /build/timescaledb \
    \
    && apk add --no-cache --virtual .build-deps \
                coreutils \
                dpkg-dev dpkg \
                gcc \
                krb5-dev \
                libc-dev \
                make \
                cmake \
                util-linux-dev \
    \
    # Build current version \
    && cd /build/timescaledb && rm -fr build \
    && git checkout ${TS_VERSION} \
    && ./bootstrap -DCMAKE_BUILD_TYPE=RelWithDebInfo -DREGRESS_CHECKS=OFF -DTAP_CHECKS=OFF -DGENERATE_DOWNGRADE_SCRIPT=ON -DWARNINGS_AS_ERRORS=OFF -DPROJECT_INSTALL_METHOD="docker"${OSS_ONLY} \
    && cd build && make install \
    && cd ~ \
    \
    && if [ "${OSS_ONLY}" != "" ]; then rm -f $(pg_config --pkglibdir)/timescaledb-tsl-*.so; fi \
    && apk del .fetch-deps .build-deps \
    && rm -rf /build \
    && sed -r -i "s/[#]*\s*(shared_preload_libraries)\s*=\s*'(.*)'/\1 = 'timescaledb,\2'/;s/,'/'/" /usr/local/share/postgresql/postgresql.conf.sample


LABEL org.opencontainers.image.source="https://github.com/DataIntegrationGroup/NMSampleLocations"
