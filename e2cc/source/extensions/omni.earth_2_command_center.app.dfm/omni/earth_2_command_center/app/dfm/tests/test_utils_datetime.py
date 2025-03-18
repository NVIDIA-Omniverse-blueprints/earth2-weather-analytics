# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


# import pytest
from datetime import datetime
import omni.earth_2_command_center.app.dfm.utils as parse_datetime


def test_iso_format_with_milliseconds_timezone():
    assert parse_datetime("2023-10-04T14:48:00.123456+0000") == datetime.strptime(
        "2023-10-04T14:48:00.123456+0000", "%Y-%m-%dT%H:%M:%S.%f%z"
    )


def test_iso_format_without_milliseconds_with_timezone():
    assert parse_datetime("2023-10-04T14:48:00+0000") == datetime.strptime(
        "2023-10-04T14:48:00+0000", "%Y-%m-%dT%H:%M:%S%z"
    )


def test_iso_format_with_milliseconds_no_timezone():
    assert parse_datetime("2023-10-04T14:48:00.123456") == datetime.strptime(
        "2023-10-04T14:48:00.123456", "%Y-%m-%dT%H:%M:%S.%f"
    )


def test_iso_format_without_milliseconds_no_timezone():
    assert parse_datetime("2023-10-04T14:48:00") == datetime.strptime(
        "2023-10-04T14:48:00", "%Y-%m-%dT%H:%M:%S"
    )


def test_iso_format_with_utc():
    assert parse_datetime("2023-10-04T14:48:00Z") == datetime.strptime(
        "2023-10-04T14:48:00Z", "%Y-%m-%dT%H:%M:%SZ"
    )


def test_common_format_with_slashes():
    assert parse_datetime("2023/10/04 14:48:00") == datetime.strptime(
        "2023/10/04 14:48:00", "%Y/%m/%d %H:%M:%S"
    )


def test_european_format_with_dashes():
    assert parse_datetime("04-10-2023 14:48:00") == datetime.strptime(
        "04-10-2023 14:48:00", "%d-%m-%Y %H:%M:%S"
    )


def test_us_format_with_dashes():
    assert parse_datetime("10-04-2023 14:48:00") == datetime.strptime(
        "10-04-2023 14:48:00", "%m-%d-%Y %H:%M:%S"
    )


# def test_unsupported_format():
#     with pytest.raises(ValueError, match="Unsupported datetime format"):
#         parse_datetime("2023.10.04 14:48:00")


# def test_empty_string():
#     with pytest.raises(ValueError, match="Unsupported datetime format"):
#         parse_datetime("")


# def test_non_datetime_string():
#     with pytest.raises(ValueError, match="Unsupported datetime format"):
#         parse_datetime("This is not a datetime string")
