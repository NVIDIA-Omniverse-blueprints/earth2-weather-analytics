# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

__all__ = ['SortedList',
           'GenericTimestampedSequence',
           'TimestampedSequence',
           'MosaicTimestampedSequence',
           'DiamondTimestampedSequence']

from typing import Any, List, Optional, Tuple, cast, Callable
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path

from omni.earth_2_command_center.app.core.time_manager import TimeManager, UTC_CURRENT_TIME_CHANGED

from .core import get_state

import hpcvis.dynamictexture

import carb
import omni.timeline

def is_jpeg_path(path):
    return Path(path).suffix.lower() in [
            '.jpg', '.jpeg', '.jpe', '.jif', '.jfif', '.jfi' ]

# TODO: add tests for this!
class SortedList:
    _list: list[tuple[datetime, Any]]

    def __init__(self):
        self._list = []

    def __bool__(self):
        return bool(self._list)

    def empty(self):
        return len(self._list) == 0

    def insert(self, element: tuple[datetime, Any]):
        idx, _ = self.find_closest_smaller_equal(element[0])
        if idx is None:
            self._list.insert(0, element)
        else:
            self._list.insert(idx + 1, element)

    def remove(self, element: tuple[datetime, Any]):
        self._list.remove(element)

    def find_closest_smaller_equal(self, timestamp: datetime) -> tuple[Optional[int], Optional[tuple[datetime, Any]]]:
        if len(self._list) == 0:
            return None, None
        if timestamp < self._list[0][0]:
            return None, None

        # binary search
        # NOTE: takes about log_2(len(self._list)) iterations
        # we could cache the last lookup and check in a subrange first to cover
        # the case during normal playback
        start_idx = 0
        end_idx = len(self._list)

        while end_idx - start_idx > 1:
            mid_idx = start_idx + (end_idx - start_idx) // 2
            if timestamp < self._list[mid_idx][0]:
                end_idx = mid_idx
            elif timestamp == self._list[mid_idx][0]:
                return mid_idx, self._list[mid_idx]
            else:
                start_idx = mid_idx

        return start_idx, self._list[start_idx]

    def find_lerp_tuple(self, time: datetime) -> Optional[tuple[Optional[float], tuple[datetime, Any],
                                                                      tuple[datetime, Any]]]:
        """
        Finds the interpolation points and interpolation weight to linearly
        interpolate between two elements. The inperpolation itself is left to
        the user as special handling might be required to handle the type hold
        by this list

        Parameters
        ----------
        time: datetime
            The timestamp for which to interpolate

        Returns
        -------
        Optional tuple (g, A, B), where g is the interpolation weight, and A,B
        are the elements (tuple of datetime and Any) to interpolate between.
        Returns None when the list is empty.
        """
        if len(self._list) == 0:
            return None

        # TODO: handle when this returns None for element
        idx0, element = self.find_closest_smaller_equal(time)
        # idx0 is None when requested time is before first element, so we can
        # trivially return the first element (we already checked for the empty
        # case)
        if idx0 is None:
            return (0.0, self._list[0], self._list[0])
        time0, el0 = element

        # if idx0 is the last element, we need to set idx1=idx0, else we can
        # pick the next index idx1=idx0+1
        idx1 = min(idx0+1, len(self._list)-1)
        if idx0 == idx1:
            return (0, (time0, el0), (time0, el0))

        time1, el1 = self._list[idx1]

        # calculate the interpolation weight
        lerp_weight = (time-time0)/(time1-time0) if (time1-time0) != timedelta() else 0.0

        return (lerp_weight, (time0, el0), (time1, el1))

    def lerp(self, time: datetime, lerp_operation: Optional[Callable[[float, Any, Any], Any]] = None) -> Any:
        """
        Linearly interpolates using the provided lerp_operation to find the
        value at the provided timestamp time.

        Parameters
        ----------
        time: datetime
            The timestamp for which to interpolate
        lerp_operation: Callable[float, Any, Any]->Any
            Operation that performs the computation (1-g)*A + g*B. When None,
            the default operation is performed which might not be valid for all
            types.

        Returns
        -------
        The interpolated value
        """
        lookup = self.find_lerp_tuple(time)
        if lookup is None:
            return None
        g, A, B = lookup

        if lerp_operation is None:
            return (1-g)*A[1] + g*B[1]
        else:
            return lerp_operation(g, A[1], B[1])


class GenericTimestampedSequence:
    _utc_time: Optional[datetime]
    _time_manager: TimeManager

    def __init__(self):
        # initialize list
        self._timestamped_list = SortedList()

        # initialize time
        self._time_manager = cast(TimeManager, get_state().get_time_manager())
        assert self._time_manager
        self._utc_time = None
        self._update_mapping(self._time_manager.utc_time)

        # create timeline subscription
        self._timeline_subscription = None
        event_stream = self._time_manager.get_utc_event_stream()
        self._timeline_subscription = event_stream.create_subscription_to_pop(self._time_event)

        self._hooks = []

    def register_hook(self, hook):
        self._hooks.append(hook)

    def insert(self, utc_time: datetime, obj):
        if not utc_time.tzinfo:
            utc_time = utc_time.replace(tzinfo=datetime.timezone.utc)
        self._timestamped_list.insert((utc_time, obj))
        # need to update even if time's unchanged
        self._update_mapping(force_update=True)

    def insert_multiple(self, entries):
        for e in entries:
            if not e[0].tzinfo:
                e = (e[0].replace(tzinfo=datetime.timezone.utc), e[1])
            self._timestamped_list.insert(e)

        # need to update even if time's unchanged
        self._update_mapping(force_update=True)

    @property
    def time_coverage(self):
        if self._timestamped_list.empty():
            return None
        else:
            return (self._timestamped_list._list[0][0], self._timestamped_list._list[-1][0])

    @property
    def list(self):
        return self._timestamped_list

    def _time_event(self, event):
        if event.type != UTC_CURRENT_TIME_CHANGED:
            return
        # update time
        cur_utc_time = self._time_manager.utc_time
        self._update_mapping(cur_utc_time)

    def _update_mapping(self, cur_utc_time: Optional[datetime] = None, force_update: bool = False):
        if cur_utc_time is None:
            cur_utc_time = self._time_manager.utc_time
        if not cur_utc_time.tzinfo:
            cur_utc_time = cur_utc_time.replace(tzinfo=datetime.timezone.utc)

        # check if update is needed
        if not force_update and self._utc_time == cur_utc_time:
            return  # early out
        if self._timestamped_list.empty():
            return  # early out

        target_idx, target_element = self._timestamped_list.find_closest_smaller_equal(cur_utc_time)
        if target_idx is None:
            # time is before our first element, so stick to first
            target_idx = 0
            target_element = self._timestamped_list._list[0] # make an interface for this

        for h in self._hooks:
            h(cur_utc_time, target_idx, target_element)

        self._utc_time = cur_utc_time

    def release(self):
        # unsubscribe first so we don't have callbacks that access the texture
        try:
            if self._timeline_subscription is not None:
                self._timeline_subscription.unsubscribe()
                self._timeline_subscription = None
        except:
            pass
        self._time_manager = None
        self._hooks = []

    def __del__(self):
        self.release()

class TimestampedSequence(GenericTimestampedSequence):
    _utc_time: Optional[datetime]
    _time_manager: TimeManager

    def __init__(self):
        super().__init__()

        # create dynamic texture
        dynamictexture_interface: Any = hpcvis.dynamictexture.acquire_dynamic_texture_interface()  # type: ignore
        self._tex = dynamictexture_interface.create()
        import uuid
        self._tex.target_url = f'dynamic://timestamped_sequence_{uuid.uuid4()}'
        self._cur_path = None

        # register hook for time utc updates
        self.register_hook(self._on_update)

    def _on_update(self, cur_utc_time, target_idx, target_element):
        if not is_jpeg_path(target_element[1]):
            carb.log_error('Trying to load a non-jpeg through the jpeg decoder. Only jpegs are supported for image sequences')
        else:
            self._tex.load_from_url(target_element[1])

    @property
    def target_url(self):
        return self._tex.target_url

    @target_url.setter
    def target_url(self, url):
        self._tex.target_url = url

    @property
    def tex(self):
        return self._tex

    def __del__(self):
        self.release()

class MosaicTimestampedSequence(GenericTimestampedSequence):
    def __init__(self, tileCount: int, urlPrefix=None):
        super().__init__()

        prefix = f"mosaic{tileCount}" if urlPrefix is None else urlPrefix
        dynamictexture_interface: Any = hpcvis.dynamictexture.acquire_dynamic_texture_interface()  # type: ignore
        self._tex_list = [dynamictexture_interface.create() for i in range(tileCount)]
        import uuid
        for t in self._tex_list:
            t.target_url = f'dynamic://{prefix}_timestamped_sequence_{uuid.uuid4()}'
        self.register_hook(self._on_update)

    def tex_list(self):
        return self._tex_list

    def _on_update(self, cur_utc_time, target_idx, target_element):
        assert(len(target_element[1]) == len(self._tex_list))

        for i in range(len(self._tex_list)):
            if not is_jpeg_path(target_element[1][i]):
                carb.log_error('Trying to load a non-jpeg through the jpeg decoder. Only jpegs are supported for image sequences')
            else:
                self._tex_list[i].load_from_url(target_element[1][i])

    @property
    def target_url(self):
        return [t.target_url for t in self._tex_list]

    def __del__(self):
        self.release()


class DiamondTimestampedSequence(MosaicTimestampedSequence):
    def __init__(self):
        super().__init__(tileCount=10, urlPrefix="diamond")
