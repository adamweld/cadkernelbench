# SPDX-License-Identifier: MIT OR Apache-2.0
# The corpus runner: every kernel the corpus workers drive, in one image, run without network and
# as an unprivileged user (see README.md beside this file). Builds for x86_64 and aarch64.
#
#     docker build -t ckb-corpus -f corpus/docker/Dockerfile .          # from the repository root

ARG CADRS_COMMIT=d208672fb0b99e85ab627e7088618f0a76824edc

FROM rust:1-bookworm AS cadrs
ARG CADRS_COMMIT
RUN git clone --filter=blob:none https://github.com/rvdende/cadrs.git /src/cadrs \
 && git -C /src/cadrs checkout -q ${CADRS_COMMIT}
COPY corpus/cadrs_worker /src/cadkernelbench/corpus/cadrs_worker
# The worker names cadrs as a checkout beside this repository: ../../../cadrs from its directory.
RUN cd /src/cadkernelbench/corpus/cadrs_worker && cargo build --release --locked \
 && cp target/release/cadrs-corpus /usr/local/bin/

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends 7zip libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir cadquery-ocp==8.0.1.1.0 numpy usd-brep==1.0.1
COPY --from=cadrs /usr/local/bin/cadrs-corpus /usr/local/bin/cadrs-corpus
COPY corpus /opt/ckb/corpus
RUN useradd --uid 10001 --create-home bench
ENV OCCT_PYTHON=/usr/local/bin/python CADRS_CORPUS=/usr/local/bin/cadrs-corpus PYTHONDONTWRITEBYTECODE=1
USER bench
WORKDIR /opt/ckb
