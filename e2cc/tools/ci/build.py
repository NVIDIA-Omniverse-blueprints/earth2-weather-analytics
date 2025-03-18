# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.



import omni.repo.ci

# Full rebuild both configs
omni.repo.ci.launch(["${root}/repo${shell_ext}", "build", "-x", "-r"])

# Extensions verification for publishing (if publishing enabled)
if omni.repo.ci.get_repo_config().get("repo_publish_exts", {}).get("enabled", True):
    omni.repo.ci.launch(["${root}/repo${shell_ext}", "publish_exts", "--verify"])

# Tool to promote extensions to the public registry pipeline, if enabled (for apps)
if omni.repo.ci.get_repo_config().get("repo_deploy_exts", {}).get("enabled", False):
    omni.repo.ci.launch(["${root}/repo${shell_ext}", "deploy_exts"])

# Use repo_docs.enabled as indicator for whether to build docs
# docs are also windows only on CI
repo_docs_enabled = omni.repo.ci.get_repo_config().get("repo_docs", {}).get("enabled", True)
repo_docs_enabled = repo_docs_enabled and omni.repo.ci.is_windows()

# Docs (windows only)
if repo_docs_enabled:
    omni.repo.ci.launch(["${root}/repo${shell_ext}", "docs", "--config", "release"])

# Package all
omni.repo.ci.launch(["${root}/repo${shell_ext}", "package", "-m", "main_package", "-c", "release"])
# omni.repo.ci.launch(["${root}/repo${shell_ext}", "package", "-m", "main_package", "-c", "debug"])

if repo_docs_enabled:
    omni.repo.ci.launch(["${root}/repo${shell_ext}", "package", "-m", "docs", "-c", "debug"])

# publish artifacts to teamcity
print("##teamcity[publishArtifacts '_build/packages']")
print("##teamcity[publishArtifacts '_build/**/*.log']")
