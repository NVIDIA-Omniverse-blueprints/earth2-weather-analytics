-- Use folder name to build extension name and tag.
local ext = get_current_extension_info()

project_ext (ext)

-- Link only those files and folders into the extension target directory
repo_build.prebuild_link { "docs", ext.target_dir.."/docs" }
repo_build.prebuild_link { "data", ext.target_dir.."/data" }
repo_build.prebuild_link { "omni", ext.target_dir.."/omni" }

-- Link to python package cache --
-- https://docs.omniverse.nvidia.com/kit/docs/kit-manual/latest/guide/using_pip_packages.html#build-time-installation-using-repo-build --
repo_build.prebuild_link {
    { "%{root}/_build/target-deps/pip_prebundle", ext.target_dir.."/pip_prebundle" },
}