__all__ = ["GlobeOrbitCameraManipulator", "OrbitGesture", "ZoomGesture"]

import carb
import carb.settings

import omni.ui as ui
import omni.ui.scene as sc

from pxr import Usd, UsdGeom, Sdf, Gf

import numpy as np
from typing import Dict, List, Optional, Union, Sequence, Callable

from omni.kit.viewport.utility import get_active_viewport

from omni.earth_2_command_center.app.geo_utils import get_geo_converter

# map val to torus [range_start, range_end
def wrap_to_range(val, range_start, range_end):
    range_width = range_end-range_start
    num = (val-range_start)//range_width
    return val + range_width*np.ceil((range_start-val)/range_width);

def build_gestures(bindings: dict = None, *args, **kwargs):
    """utility function to parse the bindings
    """
    bindings = sc.GestureBindings(bindings, gesture_module="omni.earth_2_command_center.app.globe_view")

    #gestures = []
    #for gesture, binding in bindings.parse_bindings(gesture_ignore_list=[], *args, **kwargs):
    #    gestures.append(gesture)
    #return gestures
    return [gesture for gesture, binding in bindings.parse_bindings(gesture_ignore_list=[], *args, **kwargs)]

class GlobeOrbitCameraModel(sc.AbstractManipulatorModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.__settings = carb.settings.get_settings()
        self.__settings_changed_subs = []

        self.__items = {
            # 'view': (sc.AbstractManipulatorItem(), 16),
            'projection': (sc.AbstractManipulatorItem(), 16),
            'transform': (sc.AbstractManipulatorItem(), 16),
            'latlonalt': (sc.AbstractManipulatorItem(), 3)
            }
        self.__values = {item: [] for item, _ in self.__items.values()}

        # Faster access for key-values looked up during animation
        self.__transform = self.__items.get('transform')[0]
        self.__projection = self.__items.get('projection')[0]
        self.__latlonalt = self.__items.get('latlonalt')[0]

    def __del__(self):
        self.destroy()

    def destroy(self):
        if self.__settings and self.__settings_changed_subs:
            for subscription in self.__settings_changed_subs:
                self.__settings.unsubscribe_to_change_events(subscription)
            self.__settings_changed_subs = None
        self.__settings = None

    def __validate_arguments(self, name: Union[str, sc.AbstractManipulatorItem],
                             values: Sequence[Union[int, float]] = None) -> sc.AbstractManipulatorItem:
        if isinstance(name, sc.AbstractManipulatorItem):
            return name
        item, expected_len = self.__items.get(name, (None, None))
        if item is None:
            raise KeyError(f"GlobeOrbitCameraModel doesn't understand values of {name}")
        if values and (len(values) != expected_len):
            if (not isinstance(expected_len, tuple)) or (not len(values) in expected_len):
                raise ValueError(f"GlobeOrbitCameraModel {name} takes {expected_len} values, got {len(values)}")
        return item

    def get_item(self, name: str) -> sc.AbstractManipulatorItem():
        return self.__items.get(name, (None, None))[0]

    def set_ints(self, item: Union[str, sc.AbstractManipulatorItem], values: Sequence[int]):
        item = self.__validate_arguments(item, values)
        self.__values[item] = values
        self._item_changed(item)

    def set_floats(self, item: Union[str, sc.AbstractManipulatorItem], values: Sequence[int]):
        item = self.__validate_arguments(item, values)
        self.__values[item] = values
        self._item_changed(item)

    def get_as_ints(self, item: Union[str, sc.AbstractManipulatorItem]) -> List[int]:
        item = self.__validate_arguments(item)
        return self.__values[item]

    def get_as_floats(self, item: Union[str, sc.AbstractManipulatorItem]) -> List[float]:
        item = self.__validate_arguments(item)
        return self.__values[item]

    def _item_changed(self, item: Union[str, sc.AbstractManipulatorItem, None]):
        # item == None is the signal to push all model values into a final matrix at 'transform'
        if item is not None:
            if not isinstance(item, sc.AbstractManipulatorItem):
                item = self.__items.get(item)
                item = item[0] if item else None
            ## Either of these adjust the pixel-to-world mapping
            #if item == self.__center_of_interest or item == self.__projection:
            #    self.calculate_pixel_to_world(Gf.Vec3d(self.get_as_floats(self.__center_of_interest)))
            #    super()._item_changed(item)
            #    return

        # handle state change ourselves or pass on to parent
        super()._item_changed(item)

class OrbitGesture(sc.DragGesture):
    def __init__(self, model: sc.AbstractManipulatorModel, configure_model: Optional[Callable], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        self.__configure_model = configure_model

    def destroy(self):
        self.model = None
        super().destroy()

    def on_began(self, mouse: Optional[Sequence[float]] = None, *args, **kwargs):
        mouse = np.array(mouse if mouse else self.sender.gesture_payload.mouse)
        if self.__configure_model:
            self.__configure_model(self.model, mouse, *args, **kwargs)
        self.__initial_pos = mouse
        self.__last_pos = mouse
        self.__viewport = get_active_viewport()

        # we use the aspect ratio of the framebuffer as the vertical FOV of the camera is ignored
        frame_info = self.__viewport.frame_info
        self.__aspect_ratio = frame_info['resolution'][0]/frame_info['resolution'][1]

        # get camera information
        camera = UsdGeom.Camera(self.__viewport.stage.GetPrimAtPath(self.__viewport.camera_path))
        gfcamera = camera.GetCamera(Usd.TimeCode.Default())
        fov = [
               gfcamera.GetFieldOfView(Gf.Camera.FOVHorizontal),
               gfcamera.GetFieldOfView(Gf.Camera.FOVHorizontal)/self.__aspect_ratio]
        latlonalt = self.model.get_as_floats('latlonalt')
        # radius of our globe
        sphere_radius = get_geo_converter().sphere_radius
        # linear approximation to the angle of rotation that would keep the same point on the
        # globe under the mouse while dragging.
        self.__rot_speed = [np.rad2deg(np.atan(np.tan(np.deg2rad(f/2))*latlonalt[2]/sphere_radius)) for f in fov]

    def on_changed(self, mouse: Optional[Sequence[float]] = None):
        """
        Called when there is a change while the Gesture is active
        """
        mouse = np.array(mouse if mouse else self.sender.gesture_payload.mouse)
        diff = self.__last_pos - mouse
        self.__last_pos = mouse
        latlonalt_item = self.model.get_item('latlonalt')
        latlonalt = list(self.model.get_as_floats(latlonalt_item))

        latlonalt[0] = np.clip(latlonalt[0]+diff[1]*self.__rot_speed[1], -90, 90)
        latlonalt[1] = wrap_to_range(latlonalt[1]+diff[0]*self.__rot_speed[0], -180, 180)
        self.model.set_floats(latlonalt_item, latlonalt)

    def on_ended(self, mouse: Optional[Sequence[float]] = None, final_position: bool = True):
        """
        Called when the Gesture finished
        """
        self.__initial_pos = None
        self.__viewport = None

class ZoomGesture(sc.DragGesture):
    def __init__(self, model: sc.AbstractManipulatorModel, configure_model: Optional[Callable], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        self.__configure_model = configure_model

        settings = carb.settings.get_settings()
        self.__zoom_limits = (
                settings.get_as_float("exts/omni.earth_2_command_center.app.globe_view/zoom_min"),
                settings.get_as_float("exts/omni.earth_2_command_center.app.globe_view/zoom_max"))

    def destroy(self):
        self.model = None
        super().destroy()

    def on_began(self, mouse: Optional[Sequence[float]] = None, *args, **kwargs):
        """
        Called when the Gesture is started
        """
        mouse = np.array(mouse if mouse else self.sender.gesture_payload.mouse)
        if self.__configure_model:
            self.__configure_model(self.model, mouse, *args, **kwargs)
        self.__initial_pos = mouse
        self.__last_pos = mouse
        self.__viewport = get_active_viewport()

        self.__latlonalt_item = self.model.get_item('latlonalt')
        latlonalt = self.model.get_as_floats(self.__latlonalt_item)
        self.__zoom_range = [latlonalt[2]/4, latlonalt[2], latlonalt[2]*4]
        self.__zoom_speed = [latlonalt[2]-latlonalt[2]/4, latlonalt[2]-latlonalt[2]*4]
        self.__last_alt = latlonalt[2]

    def on_changed(self, mouse: Optional[Sequence[float]] = None):
        """
        Called when there is a change while the Gesture is active
        """
        mouse = np.array(mouse if mouse else self.sender.gesture_payload.mouse)
        diff = mouse - self.__last_pos
        #diff = mouse - self.__initial_pos
        self.__last_pos = mouse
        latlonalt = list(self.model.get_as_floats(self.__latlonalt_item))
        zoom_amount = diff[0]
        if zoom_amount < 0:
            zoom_amount = np.abs(zoom_amount)
            latlonalt[2] = self.__last_alt - zoom_amount*(self.__last_alt-max(self.__last_alt*2, 1))
        else:
            zoom_amount = np.abs(zoom_amount)
            latlonalt[2] = (1-zoom_amount)*self.__last_alt

        #latlonalt[2] = np.clip(latlonalt[2]-(diff[0]+diff[1])*self.__zoom_scale, 0, 50000)
        latlonalt[2] = np.clip(latlonalt[2], *self.__zoom_limits)
        self.__last_alt = latlonalt[2]
        self.model.set_floats(self.__latlonalt_item, latlonalt)

    def on_ended(self, mouse: Optional[Sequence[float]] = None, final_position: bool = True):
        """
        Called when the Gesture finished
        """
        self.__initial_pos = None
        self.__viewport = None

class GlobeOrbitCameraManipulator(sc.GestureBindingManipulator):
    """
    Our Globe Camera Manipulator
    """

    def __init__(self, factory_args, *args, **kwargs):
        """
        Constructor

        Args:
            factory_args: this comes from the omni.kit.viewport.window callback that is called when we register our
            manipulator
            bindings (dict): Set up the bindings for the manipulator.
            model (omni.ui.scene.AbstractManipulatorModel): Set the model of the manipulator.
        """
        super().__init__(*args, **kwargs)
        self.model = kwargs.get("model", None) or GlobeOrbitCameraModel()
        self.manager = None
        self.__transform = None
        self._screen = None
        self._latlonalt_item = self.model.get_item('latlonalt')
        self._setup()

    def get_default_bindings(self):
        return {
                "OrbitGesture": "LeftButton",
                "ZoomGesture": "RightButton",
        }

    def _build_gestures(self, bindings, *args, **kwargs):
        return build_gestures(bindings=bindings, model=self.model, manager=self.manager, configure_model=self._on_began)

    def _setup(self):
        """
        make sure model is consistent with current active camera
        """
        self._viewport = get_active_viewport()
        self._usd_ctx = self._viewport.usd_context
        self._stage = self._viewport.stage

        # get the position of the camera and update the model to match it
        self._cam_prim = self._stage.GetPrimAtPath(self._viewport.camera_path)
        latlonalt = self.model.get_as_floats(self._latlonalt_item)
        transform = self._viewport.transform
        latlonalt_new = get_geo_converter().xyz_to_latlonalt(*transform.GetRow3(3))
        # there is an ambiguity when the camera is aligned with the poles
        if not np.isclose(np.abs(latlonalt_new[0]), 90):
            self.model.set_floats(self._latlonalt_item, latlonalt_new)

    def on_build(self):
        """
        We create a new omni.ui.Screen with our gestures
        """
        gestures = self.get_gestures()
        if gestures:
            # Need to hold a reference to this or the sc.Screen would be destroyed when out of scope
            self.__transform = sc.Transform()
            with self.__transform:
                self._screen = sc.Screen(gestures=gestures)
        elif self.__transform:
            self.__transform.clear()
            self._screen = None

    def destroy(self):
        """Destroys the manipulator instance."""
        if self.__transform:
            self.__transform.clear()
            self.__transform = None
        self._screen = None
        if self.model:
            self.model.destroy()
            self.model = None
        super().destroy()

    # ----------------------------------------
    # Actual Manipulator work
    # ----------------------------------------
    def _on_began(self, model: GlobeOrbitCameraModel, *args, **kwargs):
        """
        This is called by the Model to inform the Gesture that a manipulation has begun
        """
        self._setup()

    def on_model_updated(self, item):
        # TODO: this is where we should update the representation
        latlonalt_item = self.model.get_item('latlonalt')
        if item == latlonalt_item:
            latlonalt = self.model.get_as_floats(latlonalt_item)
            #xyz = get_geo_converter().latlonalt_to_xyz(*latlonalt)
        self._setup()

    def on_model_updated(self, item):
        # TODO: this is where we should update the representation
        latlonalt_item = self.model.get_item('latlonalt')
        if item == latlonalt_item:
            latlonalt = self.model.get_as_floats(latlonalt_item)
            #xyz = get_geo_converter().latlonalt_to_xyz(*latlonalt)
            with Usd.EditContext(self._stage, Usd.EditTarget(self._stage.GetSessionLayer())):
                xformable = UsdGeom.Xformable(self._cam_prim)
                ops = xformable.GetOrderedXformOps()
                if ops[0].GetOpType() != UsdGeom.XformOp.TypeRotateXYZ:
                    new_op = xformable.AddXformOp(UsdGeom.XformOp.TypeRotateXYZ, opSuffix='foo')
                    new_op.Set(Gf.Vec3d())
                    xformable.SetXformOpOrder([new_op] + ops)
                    ops = xformable.GetOrderedXformOps()
                    ops[2].Set(Gf.Vec3d())

                # setting lat,lon rotation
                cur = ops[0].Get(Usd.TimeCode.Default())
                cur[0] = 90-latlonalt[0]
                cur[2] = latlonalt[1]+90
                ops[0].Set(cur)

                # setting alt translation
                ops[1].Set(Gf.Vec3d(0,0,latlonalt[2]+get_geo_converter().sphere_radius))

