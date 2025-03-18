# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

ARG BASE_IMAGE=ubuntu:latest
FROM $BASE_IMAGE

RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    libeccodes0 \
    libeccodes-dev \
    openssh-client \
    libkrb5-dev \
    gcc \
    gfortran \
    curl \
    wget \
    vim \
    git \
    && rm -rf /var/lib/apt/lists/*

# Add source code of gfortran, curl and wget for distribution
RUN mkdir -p /source && cd /source && \
    git clone --single-branch --depth=1 --filter=tree:0 https://github.com/ecmwf/eccodes.git && \
    git clone --single-branch --depth=1 --filter=tree:0 https://github.com/krb5/krb5.git && \
    git clone --single-branch --depth=1 --filter=tree:0 https://github.com/gcc-mirror/gcc.git && \
    git clone --single-branch --depth=1 --filter=tree:0 https://github.com/mirror/wget.git && \
    git clone --single-branch --depth=1 --filter=tree:0 https://github.com/curl/curl.git && \
    git clone --single-branch --depth=1 --filter=tree:0 https://github.com/vim/vim.git && \
    rm -rf /source/gcc/libgo/ && \
    apt-get remove -y git

# Install Miniforge
RUN curl -fsSLo /tmp/miniforge3.sh --retry 3 --retry-delay 5 "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh" \
    && bash /tmp/miniforge3.sh -b -p /opt/conda \
    && rm /tmp/miniforge3.sh

# Execute all RUN commands in conda base environment
SHELL ["/opt/conda/bin/conda", "run", "-n", "base", "--live-stream", "/bin/bash", "-c"]

# Install poetry into the base conda environment
RUN pip install poetry

# Tell poetry not to create a separate virtual env
RUN poetry config virtualenvs.create false

# Now, create Conda environment for DFM and make it the default environment for RUN commands
RUN conda create -n dfm python=3.12.9
SHELL ["/opt/conda/bin/conda", "run", "-n", "dfm", "--live-stream", "/bin/bash", "-c"]

# Tell eccodes to use system so library
ENV ECCODES_PYTHON_USE_FINDLIBS=1
ENV LD_LIBRARY_PATH=/lib/x86_64-linux-gnu/

RUN mkdir -p /app/k8s/process
RUN mkdir -p /app/k8s/common

COPY ./src/k8s/process/*.py /app/k8s/process
COPY ./src/k8s/process/run.sh /app/k8s/process
COPY ./src/k8s/common/log_conf*.yml /app/k8s/common

COPY ./src/dfm /app/dfm

# Install DFM dependencies using Poetry
COPY ./src/pyproject.toml /app
COPY ./src/poetry.lock /app
WORKDIR /app
RUN for i in {1..3}; do \
      /opt/conda/bin/poetry install --no-root --with core && break || sleep 15; \
    done && \
    rm ./pyproject.toml ./poetry.lock

# Install dependencies and bootstrap opentelemetry
WORKDIR /app/k8s/process
RUN opentelemetry-bootstrap -a install

ENV NAME="Earth-2 Weather Analytics Process Service"

EXPOSE 8080

# Run
ENTRYPOINT [ "/opt/conda/bin/conda", "run", "-n", "dfm", "--live-stream" ]
CMD ["./run.sh"]
