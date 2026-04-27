#!/bin/bash

e2cc_path=/opt/nvidia/omniverse/earth-2-command-center

export PATH=${e2cc_path}/kit/python/:$PATH
source ${e2cc_path}/setup_python_env.sh

export LD_LIBRARY_PATH=${e2cc_path}/kit/:${e2cc_path}/kit/extscore/omni.client/bin/deps/:$LD_LIBRARY_PATH

script_path=$(dirname $0)

$script_path/get_index_data.py