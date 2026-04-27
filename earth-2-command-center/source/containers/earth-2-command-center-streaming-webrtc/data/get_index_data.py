#!/usr/bin/env python3

import os
import sys
import omni.client
from pathlib import Path

def main():
    if 'OMNI_USER' not in os.environ or 'OMNI_PASS' not in os.environ:
        raise RuntimeError('OMNI_USER and OMNI_PASS variables must be set')
    server = 'omniverse://earth2-gtcdemo.sample.omniverse.nvidia.com'
    print(f'Using omni.client {omni.client.get_version()}')
    if not omni.client.initialize():
        raise RuntimeError("Failed to initialize omni.client library")

    _, si = omni.client.get_server_info(server)
    print(f'Connected to Nucleus server {server}')

    nucleus_relative_path = os.environ.get('NUCLEUS_INDEX_DATA_RELATIVE_PATH', 'Projects/Earth-2/SCREAM')
    local_relative_path = os.environ.get('LOCAL_INDEX_DATA_RELATIVE_PATH', '/opt/nvidia/index')
    Path(local_relative_path).mkdir(parents=True, exist_ok=True)

    remote_path = f'{server}/{nucleus_relative_path}'
    _, file_list = omni.client.list(remote_path)

    for le in file_list:
        remote_file_path = remote_path + '/' + le.relative_path
        print(f'Downloading {remote_file_path}')
        result, local_path = omni.client.get_local_file(remote_file_path, download=True)
        if result != omni.client.Result.OK:
            print('Downloading failed!')
        print(f'Downloaded to {local_path}')
        destination_path = local_relative_path + '/' + Path(le.relative_path).name
        print(f'Renaming downloaded file to {destination_path}')
        Path(local_path).rename(destination_path)

    return 0

if __name__ == "__main__":
    sys.exit(main())
