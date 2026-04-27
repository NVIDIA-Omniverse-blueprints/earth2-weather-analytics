__all__ = ['DFMSchedulerTask', 'DFMScheduler', 'dfm_error_check']

from typing import Callable, Optional
import asyncio
import threading
import time
import copy
from functools import partial

import carb

from nv_dfm_core.session import Session, JobStatus
from nv_dfm_core.api import Pipeline, ErrorToken
from nv_dfm_core.exec import Frame
from nv_dfm_core.targets.flare import FlareOptions

def dfm_error_check(data):
    if isinstance(data, ErrorToken):
        error = ErrorToken.model_validate(data)
        for e in error.errors:
            carb.log_error(f'Received Error {e.type}: {e.message}')
            carb.log_error(f'StackTrace:\n{e.stack_trace.encode("utf-8").decode("unicode_escape")}')
        return True
    return False

def default_callback(
    _from_site: str,
    _node: int | str | None,
    frame: Frame,
    _target_place: str,
    data: object,
) -> None:
    #carb.log_error(f'default_callback - data:{data}, type:{type(data)}, target_place={_target_place}')
    if frame.is_stop_frame():
        # this indicates that the pipeline has completed
        return
    if dfm_error_check(data):
        #TODO: cancel task?
        pass

    #if not isinstance(data, StopToken):
    #    carb.log_error(f'default_callback - data:{data}, type:{type(data)}')

class DFMSchedulerTask:
    def __init__(self,
                 session: Session,
                 site: str,
                 pipeline: Pipeline,
                 default_callback: Callable = None,
                 place_callbacks: Optional[dict] = None,
                 done_callback: Callable = None,
                 input_params: dict = None,
                 timeout: int = 300):
        self.session = session
        self.site = site
        self.pipeline = pipeline
        self.default_callback = default_callback
        self.place_callbacks = place_callbacks if place_callbacks else {}
        self.done_callback = done_callback
        self.input_params = input_params
        self.timeout = timeout
        self.cancel_event = threading.Event()
        self._job = None
        self._done = False

    def cancel(self):
        self.cancel_event.set()

    def schedule(self, input_params:dict = None):
        input_params = input_params if input_params is not None else self.input_params
        if input_params is None:
            input_params = {}

        from omni.earth_2_command_center.app.dfm import get_dfm
        return get_dfm().schedule(self, input_params=input_params)

    def finished(self):
        if self._job:
            return self._done
        else:
            return True

    async def wait(self):
        if self._job:
            return await self._job
        else:
            return None

    def running(self):
        return not self.finished()

class DFMScheduler:
    def __init__(self):
        #self._jobs = []
        pass

    def _thread_worker(self, task, *args, **kwargs):
        with task.session:
            #restrict = (site, "homesite") if site != "homesite" else (site,)
            prepared = task.session.prepare(task.pipeline)#, restrict_to_sites=restrict)

            dfm_task = None
            def yield_callback_internal(callback, _from_site: str, _node: int | str | None, _frame: Frame,
                                        target_place: str, data: object) -> None:
                carb.log_info(f'yield callback on thread: {threading.current_thread()}')
                # do error checking
                if dfm_error_check(data):
                    task.cancel()
                # hand over to user callback
                if callback:
                    callback(_from_site, _node, _frame, target_place, data)

            carb.log_info(f'executing on thread: {threading.current_thread()}')
            dfm_task = task.session.execute(
                prepared,
                *args,
                default_callback=task.default_callback if task.default_callback else default_callback,
                place_callbacks={place:partial(yield_callback_internal, callback) for place,callback in
                                 task.place_callbacks.items()},
                autostop=True,
                options=FlareOptions(task_timeout_s=task.timeout),
                **kwargs,
            )
            carb.log_info(f'waiting for results on thread: {threading.current_thread()}')

            try:
                start_time = time.monotonic()
                while True:
                    if time.monotonic()-start_time > task.timeout:
                        raise TimeoutError
                    if task.cancel_event.is_set():
                        carb.log_warn('cancelling task')
                        task.cancel_event.clear()
                        carb.log_warn(f'Task status: {dfm_task.get_status()}')
                        dfm_task.cancel()
                        break
                    else:
                        if dfm_task.get_status() == JobStatus.FINISHED:
                            #carb.log_warn('finished! waiting for dfm to finish...')
                            # we need to wait for dfm to really finish
                            dfm_task.wait_until_finished(timeout=max(1, task.timeout-(time.monotonic()-start_time)))
                            carb.log_info('dfm finished')
                            break
                        else:
                            task.cancel_event.wait(1.0)
            except TimeoutError:
                carb.log_error('Task timed out')
                task.cancel_event.clear()
                dfm_task.cancel()
            except Exception as e:
                carb.log_error('error in working thread')
                import traceback
                traceback.print_exc()
                raise RuntimeError('Pipeline execution failed. Timeout reached?') from e
            task._done = True

        return True

    def schedule(self, task:DFMSchedulerTask, *args, **kwargs):
        result = copy.copy(task)
        result._done = False
        result._job = asyncio.to_thread(self._thread_worker, result, *copy.copy(args),
                                                            **copy.deepcopy(kwargs))
        #self._jobs.append(result._job)
        return result

    def __del__(self):
        pass

