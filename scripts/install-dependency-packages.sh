#!/bin/bash

# This script installs additional packages used by the dependency image but
# not needed by the runtime image, such as additional packages required to
# build Python dependencies.
#
# Since the base image wipes all the apt caches to clean up the image that
# will be reused by the runtime image, we unfortunately have to do another
# apt-get update here, which wastes some time and network.

# Bash "strict mode", to help catch problems and bugs in the shell
# script. Every bash script you write should include this. See
# http://redsymbol.net/articles/unofficial-bash-strict-mode/ for
# details.
set -euo pipefail

# Display each command as it's run.
set -x

# Tell apt-get we're never going to be able to give manual
# feedback:
export DEBIAN_FRONTEND=noninteractive

# Update the package listing, so we know what packages exist:
apt-get update

# Install build-essential because sometimes Python dependencies need to build
# C modules, particularly when upgrading to newer Python versions. git is
# required by setuptools_scm for package installation. libffi-dev is sometimes
# needed to build cffi (a cryptography dependency).
apt-get -y install --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    git \
    libffi-dev \
    libsasl2-dev \
    libssl-dev \
    libzstd-dev \
    pkg-config \
    zlib1g-dev

# Quix Streams 3.25 pins confluent-kafka 2.11, which requires matching
# librdkafka headers. Debian trixie's 2.8 package is too old, so install the
# pinned upstream release into /usr/local. Verify the archive before building
# to keep the image build reproducible.
librdkafka_version=2.11.1
librdkafka_sha256=a2c87186b081e2705bb7d5338d5a01bc88d43273619b372ccb7bb0d264d0ca9f
librdkafka_archive=/tmp/librdkafka.tar.gz
librdkafka_source=/tmp/librdkafka

curl --fail --location --silent --show-error \
    "https://github.com/confluentinc/librdkafka/archive/refs/tags/v${librdkafka_version}.tar.gz" \
    --output "${librdkafka_archive}"
echo "${librdkafka_sha256}  ${librdkafka_archive}" | sha256sum --check
mkdir "${librdkafka_source}"
tar --extract --gzip --file "${librdkafka_archive}" \
    --directory "${librdkafka_source}" --strip-components=1
cd "${librdkafka_source}"
./configure --prefix=/usr/local
make -j"$(nproc)"
make install
ldconfig
rm -rf "${librdkafka_archive}" "${librdkafka_source}"
