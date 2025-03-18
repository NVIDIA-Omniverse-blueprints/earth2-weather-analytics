# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.



from datetime import datetime

def parse_datetime(datetime_str: str) -> datetime:
    """Converts a date time string in some ISO format into a python datetime object

    Parameters
    ----------
    datetime_str : str
        Datetime string

    Returns
    -------
    datetime
        Datetime object

    Raises
    ------
    ValueError
        Invalid / note supported
    """
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%Z",  # ISO format with milliseconds and timezone
        "%Y-%m-%dT%H:%M:%S%Z",  # ISO format without milliseconds but with timezone
        "%Y-%m-%dT%H:%M:%S.%f",  # ISO format with milliseconds, no timezone
        "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO format with milliseconds, with 'Z' for UTC
        "%Y-%m-%dT%H:%M:%S",  # ISO format without milliseconds or timezone
        "%Y-%m-%dT%H:%M:%SZ",  # ISO format with 'Z' for UTC
        "%Y/%m/%d %H:%M:%S",  # Common format with slashes
        "%d-%m-%Y %H:%M:%S",  # European format with dashes
        "%m-%d-%Y %H:%M:%S",  # US format with dashes
    ]

    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue

    raise ValueError("Unsupported datetime format: " + datetime_str)
