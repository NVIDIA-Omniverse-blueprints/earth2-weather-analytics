#!/bin/bash

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


export OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true
export PYTHONPATH=../../:$PYTHONPATH

if [[ $SERVICE_LOGGING_ENABLE_JSON == "true" ]]; then
    log_conf=../common/log_conf_json.yml
else
    log_conf=../common/log_conf.yml
fi

opentelemetry-instrument --service_name dfm-process \
    uvicorn process_fastapi:app --host 0.0.0.0 --port 8080 --log-config $log_conf --reload --reload-dir "../.." --reload-include "*.py"
