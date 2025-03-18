# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import os
import re

NVIDIA_HEADER = '''# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.
'''

def should_process_file(filepath):

    # Skip files in pip_prebundle, _build, and similar directories
    skip_dirs = ['pip_prebundle', '_build', '__pycache__', '.git']
    return not any(skip_dir in filepath for skip_dir in skip_dirs)

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove any existing comments at the start of the file
    content = re.sub(r'^(#.*\n)*', '', content.lstrip())

    # Add the new header
    new_content = NVIDIA_HEADER + content

    # Write the modified content back
    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)

def process_directory(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if should_process_file(filepath):
                    print(f"Processing: {filepath}")
                    process_file(filepath)

def main():
    # Get the project root directory (assuming script is run from project root)
    project_root = os.getcwd()

    # Process extensions source folder
    extensions_path = os.path.join(project_root, 'source', 'extensions')
    if os.path.exists(extensions_path):
        process_directory(extensions_path)

    # Process tools folder
    tools_path = os.path.join(project_root, 'tools')
    if os.path.exists(tools_path):
        process_directory(tools_path)

if __name__ == "__main__":
    main()