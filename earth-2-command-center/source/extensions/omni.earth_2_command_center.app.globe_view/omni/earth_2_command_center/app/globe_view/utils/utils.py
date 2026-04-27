__all__ = ['create_unique_prim_path', 'toggle_visibility']

import uuid
from pxr import UsdGeom, Sdf, Tf, Usd, Gf

import carb

def create_unique_prim_path(base_path = Sdf.Path('/World/globe_view'), prefix = 'prim'):
    return base_path.AppendChild(f'{prefix}_{uuid.uuid4().hex}')

# toggle USD Imageable viility attribute
def toggle_visibility(stage, path, value=None):
    if not stage:
        return

    prim = UsdGeom.Imageable(stage.GetPrimAtPath(path))
    if not prim:
        carb.log_warn(f'Could not find prim to toggle visibility: {path}')
        return
    vis_attr = prim.GetVisibilityAttr()
    if value is not None:
        vis_attr.Set('inherited' if value else 'invisible')
    else:
        if vis_attr.Get() == 'invisible':
            vis_attr.Set('inherited')
        else:
            vis_attr.Set('invisible')
