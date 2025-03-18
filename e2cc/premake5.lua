-- Shared build scripts from repo_build package
repo_build = require("omni/repo/build")

-- Repo root
root = repo_build.get_abs_path(".")

local function get_file_size(file_path)
    local file = io.open(file_path, "rb")
    if file then
        local size = file:seek("end")
        file:close()
        return size
    end
    return nil
end

local function check_lfs_valid()
    local path = "./source/extensions/omni.earth_2_command_center.app.setup/data/textures/world_A1_1k.jpg"
    local size = get_file_size(path)
    if size < 1024 then
        error("Textures have not been pulled from lfs! Use 'git lfs pull' to get the files. You can disable this check in the main premake5.lua file")
    end
end
-- comment out this line to skip LFS check
check_lfs_valid()

-- Insert kit template premake configuration, it creates solution, finds extensions.. Look inside for more details.
dofile("_repo/deps/repo_kit_tools/kit-template/premake5.lua")

-- Extra folder linking and file copy setup:
-- repo_build.prebuild_link {
--     -- Link python app sources in target dir for easier edit
--     { "source/pythonapps/target", bin_dir.."/pythonapps" },
-- }
-- repo_build.prebuild_copy {
--     -- Copy python app running scripts in target dir
--     {"source/pythonapps/runscripts/$config/*$shell_ext", bin_dir}
-- }

repo_build.prebuild_copy {
    {"licenses.md", bin_dir}
}

-- Earth-2 Command Center App
define_app("omni.earth_2_command_center.app_desktop")
define_app("omni.earth_2_command_center.app_streamer")
define_app("omni.earth_2_command_center.app_nvcf")
