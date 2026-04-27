FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Europe/Zurich

RUN apt-get update && apt-get install tzdata
RUN echo $TZ > /etc/timezone && dpkg-reconfigure -f noninteractive tzdata

# Install Python 3.12 and basic tooling
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl ca-certificates git && \
    rm -rf /var/lib/apt/lists/*

# Install uv via official installer
ADD https://astral.sh/uv/install.sh /tmp/install_uv.sh
RUN sh /tmp/install_uv.sh && rm /tmp/install_uv.sh
ENV PATH="/root/.local/bin:${PATH}"

# Set workdir and copy local folder into the image
WORKDIR /app
# ./workspace expected to be mapped
COPY src/pyproject.toml src/README.md /app
#COPY uv.lock /app

# Make venv “active” for all later commands
RUN uv python install 3.12 --default -n
RUN python3.12 -m venv .venv
ENV PATH="/app/.venv/bin:$PATH"
RUN echo 'export PATH="/root/.local/bin:$PATH"' >> /root/.bashrc

# install general python dependencies
COPY earth-2-federation/dist /app/wheels
RUN uv sync

## install earth2 federation package
RUN pip install ./wheels/earth2_blueprint-0.8.17-py3-none-any.whl[federation,sfno] --find-links=./wheels/

# run dfm poc start in prepare only mode which prepares the folder structure
# change permissions to give others rwx access to transfer folder as else we get permission errors on the client side
COPY src/federations.yaml .
RUN dfm poc start -f earth2 --prepare-only && chmod o+rwx ./workspace/earth2_poc/federation/prod_00/homesite@earth2.nvidia.com/transfer

# now we can start the federation
COPY src/scripts/startup.sh /app
ENTRYPOINT ["./startup.sh"]

