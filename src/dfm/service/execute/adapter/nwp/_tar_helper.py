# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import asyncio
import io
import tarfile

""" helper function to read a tar file header from a stream """


async def read_tar_header(async_stream: asyncio.StreamReader) -> tarfile.TarInfo:
    try:
        header = await async_stream.readexactly(tarfile.BLOCKSIZE)
    except asyncio.IncompleteReadError:
        return None
    if not header:
        return None
    try:
        member = tarfile.TarInfo.frombuf(
            header, encoding="utf-8", errors="surrogateescape"
        )
        return member
    except tarfile.HeaderError:
        return None


""" helper function to read tar file data into a BytesIO buffer """


async def read_file_from_tar(
    async_stream: asyncio.StreamReader, header: tarfile.TarInfo
) -> io.BytesIO:
    if header.isfile() and header.size > 0:
        remaining = header.size
        buffer = io.BytesIO(bytearray(header.size))
        while remaining > 0:
            chunk = await async_stream.readexactly(tarfile.BLOCKSIZE)
            if not chunk:
                raise RuntimeError("bad tar file data")
            read_len = len(chunk)
            data = chunk if remaining >= read_len else chunk[:remaining]
            buffer.write(data)
            remaining -= read_len
        buffer.seek(0)
        if buffer.getbuffer().nbytes != header.size:
            raise RuntimeError(
                f"buffer size does not match size listed in header {buffer.getbuffer().nbytes} != {header.size}"
            )
        return buffer
