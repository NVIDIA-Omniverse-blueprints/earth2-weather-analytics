__all__ = [ 'pinpoints_to_affine_mapping',
           'latlong_rect_to_affine_mapping',
           'affine_mapping_to_shader_param_value',
           'install_python_dependency' ]

import numpy as np

# source points in image space to target points in latlong (radians)
def pinpoints_to_affine_mapping(source, target, is_in_radians=True):
    if len(source) != len(target):
        raise RuntimeError('source and target points length mismatch')
    if len(source) < 3:
        raise RuntimeError('need 3 points')

    if not is_in_radians:
        target = target.copy()
        for idx,p in enumerate(target):
            target[idx] = np.deg2rad(p.astype(np.float32))

    L = np.array([
        target[0:3,0].transpose(),
        target[0:3,1].transpose(),
        [1, 1, 1]], dtype=np.float32)
    L_inv = np.linalg.inv(L)

    U = np.array([
        source[0:3,0].transpose(),
        source[0:3,1].transpose()
        ], dtype=np.float32)
    A_inv = np.dot(U, L_inv)

    return A_inv

def latlong_rect_to_affine_mapping(lon_min, lon_max, lat_min, lat_max, is_in_radians=True):
    # NOTE: we have to stay in the [0,1] domain of the image space so we can't
    # handle negative longitudes. We shift the transform before the fit and
    # return the shift as an additional longitudinal offset
    # NOTE: for a "full" fix, we should also check if the max is exceeding the
    # image space but for this we would require a longitudinal_scale as well
    # to scale the range into a valid image mapping
    longitudinal_offset = 0
    if lon_min < 0:
        longitudinal_offset = -lon_min
        lon_max -= lon_min
        lon_min = 0

    # NOTE: we know the solution analytically but this isn't called frequently
    #       so doing a 3x3 matrix inversion is of no concern. However, when the
    #       latlon window gets very small, we might need to care about conditioning.
    source = np.array(np.array([[0,0], [1,1], [0,1]], dtype=np.float32))
    target = np.array(np.array([[lon_min, lat_min], [lon_max, lat_max], [lon_min, lat_max]], dtype=np.float32))
    result = pinpoints_to_affine_mapping(source, target, is_in_radians)
    return result, longitudinal_offset if is_in_radians else np.radians(longitudinal_offset)

def affine_mapping_to_shader_param_value(mapping):
    return mapping.flatten()[0:6].tolist()

def install_python_dependency(name, *, module=None, version=None, extra_index_url=None, extra_args=None):
    import carb
    import copy
    if extra_args is not None:
        extra_args = copy.copy(extra_args)
    else:
        extra_args = []
    ignore_cache = False
    ignore_import_check = False

    # there is no functionality exposed to get the environment setup (apart from
    # calling installing, which we don't want yet. so we have to call this method
    # directly...
    from omni.kit.pipapi.pipapi import _initialize
    _initialize()

    needs_install = False
    import importlib
    try:
        import_name = module if module else name
        m = importlib.import_module(import_name)
        installed_version = getattr(m, '__version__', None)
        if installed_version is None:
            needs_install = True
        elif version is not None and installed_version != version:
            carb.log_warn(f'Package {name} is not at version {version} {f"(installed {installed_version})" if installed_version is not None else ""}')
            version_tuple = tuple(int(x) for x in version.split("."))
            installed_version_tuple = tuple(int(x) for x in installed_version.split("."))
            if installed_version_tuple < version_tuple:
                extra_args.append('--force-reinstall')
                ignore_cache = True
                ignore_import_check = True
                needs_install = True
    except ImportError:
        needs_install = True

    if not needs_install:
        return

    carb.log_warn(f'Installing Python Dependencies for {name}')
    extra_args.append('-v')
    if extra_index_url:
        extra_args.append('--extra-index-url')
        extra_args.append(extra_index_url)

    import omni.kit.pipapi
    if version is not None:
        package_name = f'{name}=={version}'
    else:
        package_name = name
    omni.kit.pipapi.install(package_name, module=module, extra_args=extra_args,
                            ignore_import_check=ignore_import_check, ignore_cache=ignore_cache)

