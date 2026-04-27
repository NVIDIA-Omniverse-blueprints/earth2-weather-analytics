__all__ = ['TimeManager',
           'UTC_START_TIME_CHANGED',
           'UTC_END_TIME_CHANGED',
           'UTC_PER_SECOND_CHANGED',
           'UTC_CURRENT_TIME_CHANGED',
           ]

import carb
import carb.events
import omni.timeline
from omni.timeline import TimelineEventType

import datetime

UTC_START_TIME_CHANGED: int = carb.events.type_from_string("omni.earth_2_command_center.app.core.UTC_START_TIME_CHANGED")
UTC_END_TIME_CHANGED: int   = carb.events.type_from_string("omni.earth_2_command_center.app.core.UTC_END_TIME_CHANGED")
UTC_PER_SECOND_CHANGED: int = carb.events.type_from_string("omni.earth_2_command_center.app.core.UTC_PER_SECOND_CHANGED")
UTC_CURRENT_TIME_CHANGED: int = carb.events.type_from_string("omni.earth_2_command_center.app.core.UTC_CURRENT_TIME_CHANGED")

class TimeManager:
    _utc_per_second: datetime.timedelta

    def __init__(self):
        self._timeline = omni.timeline.get_timeline_interface()
        timeline_event_stream = self._timeline.get_timeline_event_stream()
        self._subscription = timeline_event_stream.create_subscription_to_pop_by_type(
                int(TimelineEventType.CURRENT_TIME_TICKED),
                self._on_timeline_event)

        events_interface = carb.events.acquire_events_interface()
        self._utc_event_stream = events_interface.create_event_stream()

        self._tz = datetime.timezone.utc
        self._utc_start_time = datetime.datetime(1988, 6, 29, 12, 0, 0, tzinfo=self._tz)
        self._utc_end_time = datetime.datetime(1988, 6, 29, 18, 0, 0, tzinfo=self._tz)
        self._utc_per_second = datetime.timedelta(hours=2)
        self._sync(self._utc_start_time)

    def get_timeline(self):
        return self._timeline

    def get_timeline_event_stream(self):
        return self._timeline.get_timeline_event_stream()

    def get_utc_event_stream(self):
        return self._utc_event_stream

    @staticmethod
    def _conform_time(time: datetime.datetime):
        if time is None:
            return None

        if not time.tzinfo:
            return time.replace(tzinfo=datetime.timezone.utc)
        else:
            return time

    @property
    def utc_start_time(self):
        return self._utc_start_time

    @utc_start_time.setter
    def utc_start_time(self, utc_start: datetime.datetime):
        if isinstance(utc_start, datetime.datetime):
            utc_start = TimeManager._conform_time(utc_start)
            if self._utc_start_time != utc_start:
                utc_current_time = self.utc_time
                self._utc_start_time = utc_start
                self._sync(utc_current_time)
                self._utc_event_stream.push(UTC_START_TIME_CHANGED)
                self._utc_event_stream.pump()
        else:
            carb.log_warn(f'Trying to set utc_start_time with incompatible type: {type(utc_start)}')

    @property
    def utc_end_time(self):
        return self._utc_end_time

    @utc_end_time.setter
    def utc_end_time(self, utc_end:datetime.datetime):
        if isinstance(utc_end, datetime.datetime):
            utc_end = TimeManager._conform_time(utc_end)
            if self._utc_end_time != utc_end:
                utc_current_time = self.utc_time
                self._utc_end_time = utc_end
                self._sync(utc_current_time)
                self._utc_event_stream.push(UTC_END_TIME_CHANGED)
                self._utc_event_stream.pump()
        else:
            carb.log_warn(f'Trying to set utc_end_time with incompatible type: {type(utc_end)}')

    @property
    def utc_per_second(self):
        '''
        Duration in UTC time per second of playback. 1hr would result in 1hr of
        UTC time per 1s of playback.
        '''
        return self._utc_per_second

    @utc_per_second.setter
    def utc_per_second(self, utc_per_second:datetime.timedelta):
        if self._utc_per_second != utc_per_second:
            utc_current_time = self.utc_time
            self._utc_per_second = utc_per_second
            self._sync(utc_current_time)
            self._utc_event_stream.push(UTC_PER_SECOND_CHANGED)
            self._utc_event_stream.pump()

    @property
    def utc_time(self):
        return self.playback_to_utc_time(self.playback_time)

    @utc_time.setter
    def utc_time(self, utc_time:datetime.datetime):
        if isinstance(utc_time, datetime.datetime):
            utc_time = TimeManager._conform_time(utc_time)
            if utc_time != self.utc_time:
                self.playback_time = self.utc_to_playback_time(utc_time)
                self._utc_event_stream.push(UTC_CURRENT_TIME_CHANGED)
                self._utc_event_stream.pump()
        else:
            carb.log_warn(f'Trying to set utc_time with incompatible type: {type(utc_time)}')

    @property
    def playback_time(self):
        return self._timeline.get_current_time()

    @playback_time.setter
    def playback_time(self, time):
        self._timeline.set_current_time(time)

    def playback_to_utc_time(self, playback_time: float) -> datetime.datetime:
        # TODO: something is messing with the timelines current time. We're setting it to 0 and then the timeline reports 42758.4
        try:
            return self._utc_start_time + playback_time*self._utc_per_second
        except OverflowError:
            return self.utc_start_time

    def utc_to_playback_time(self, utc_time: datetime.datetime) -> float :
        utc_time = TimeManager._conform_time(utc_time)
        try:
            return (utc_time - self._utc_start_time) / self.utc_per_second
        except OverflowError:
            return self.playback_start_time
        except ZeroDivisionError:
            carb.log_error(f'Invalid UTC Per Second: {self.utc_per_second}')
            return 0.0

    @property
    def playback_start_time(self):
        return 0.0

    @property
    def playback_end_time(self):
        return self.utc_to_playback_time(self._utc_end_time)

    @property
    def current_utc_time(self):
        return self.utc_time

    def sync_stage(self):
        if stage := omni.usd.get_context().get_stage():
            utc_duration = self._utc_end_time - self._utc_start_time
            playback_duration = utc_duration.total_seconds() / self._utc_per_second.total_seconds() \
                    if self._utc_per_second != datetime.timedelta() else 0
            tcpersec = stage.GetTimeCodesPerSecond()
            stage.SetStartTimeCode(0)
            stage.SetEndTimeCode(playback_duration * tcpersec)
            # this seems necessary; despite `stage.GetTimeCodesPerSecond`
            # returning 60, the playback happens at some internal default which is 24.
            # explicitly setting tc-per-sec here overcomes that issue.
            stage.SetTimeCodesPerSecond(tcpersec)

    def _sync(self, utc_current_time: datetime.datetime):
        self.sync_stage()
        self._timeline.set_start_time(self.utc_to_playback_time(self.utc_start_time))
        self._timeline.set_end_time(self.utc_to_playback_time(self.utc_end_time))
        self._timeline.set_current_time(self.utc_to_playback_time(utc_current_time))

    def extend_to_include(self, start:datetime.datetime = None, end:datetime.datetime = None):
        """Extends the Global Timeline to include start and end time provided"""
        start = TimeManager._conform_time(start)
        end = TimeManager._conform_time(end)

        utc_current_time = self.utc_time
        if start is not None and self.utc_start_time > start:
            self._utc_start_time = start
        if end is not None and self.utc_end_time < end:
            self._utc_end_time = end
        self._sync(utc_current_time)

    def get_time_coverage(self, features=None):
        """
            Calculate the time coverage of the provided active features. If
            features==None, the time coverage of all registered features is
            returned
        """
        from .core import get_state
        features_api = get_state().get_features_api()

        start = None
        end = None
        for f in features if features is not None else features_api.get_features():
            if features is None and not f.active:
                continue
            if f.time_coverage is not None:
                if start is None or start > f.time_coverage[0]:
                    start = f.time_coverage[0]
                if end is None or end < f.time_coverage[1]:
                    end = f.time_coverage[1]
        return (start, end)

    def set_playback_duration(self, playback_duration=10):
        """
            Sets the playback duration for the currently set utc_start and utc_end
        """
        start = self.utc_start_time
        end = self.utc_end_time
        if start == end or start is None or end is None:
            carb.log_warn(f'Trying to set playback duration with empty timeline')
            return
        if playback_duration is None or playback_duration <= 0:
            carb.log_error(f'Invalid playback_duration provided: {playback_duration}')
            return

        self.utc_per_second = (end-start)/playback_duration
        self._sync(self._utc_time)

    def set_time_range(self, utc_start, utc_end, utc_time=None, playback_duration=10):
        """
            Sets the Global Timeline the provided start and end time points, and
            updates the utc_per_second to achieve the desired playback duration
        """
        if utc_start is None or utc_end is None:
            return
        utc_start = TimeManager._conform_time(utc_start)
        utc_end = TimeManager._conform_time(utc_end)

        utc_duration = utc_end-utc_start
        utc_current_time = self.utc_time if utc_time is None else TimeManager._conform_time(utc_time)

        self.utc_start_time = utc_start
        if utc_duration > datetime.timedelta():
            self.utc_end_time = utc_end
        else:
            utc_duration = datetime.timedelta(days=1)
            self.utc_end_time = utc_start + utc_duration

        # clamp utc_current_time
        if utc_current_time < self.utc_start_time:
            utc_current_time = self.utc_start_time
        elif utc_current_time > self.utc_end_time:
            utc_current_time = self.utc_end_time

        # calculate utc per second for provided playback duration
        self.utc_per_second = utc_duration/playback_duration if playback_duration>0 else self.utc_per_second
        self._sync(utc_current_time)

    def include_all_features(self, playback_duration=10.0, features=None):
        """
            Sets the Global Timeline to include all active features.
            If features is not None, then only features from the specified list
            are used (regardless of whether they are active).
        """
        time_coverage = self.get_time_coverage(features)
        self.set_time_range(*time_coverage, playback_duration=playback_duration)

    def _on_timeline_event(self, event):
        if event.type == int(TimelineEventType.CURRENT_TIME_TICKED):
            self._utc_event_stream.push(UTC_CURRENT_TIME_CHANGED)
            self._utc_event_stream.pump()

