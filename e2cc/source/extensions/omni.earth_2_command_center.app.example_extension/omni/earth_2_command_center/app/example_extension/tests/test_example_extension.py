# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import omni.kit.test
#import omni.earth_2_command_center.app.example_extension as example_extension

class Test(omni.kit.test.AsyncTestCase):
    async def setUp(self):
        '''No need for setup work'''

    async def tearDown(self):
        '''No need for teardown work'''

    # ============================================================
    # Core Tests
    # ============================================================
    # here we can add our own tests
    # TODO: this will fail on windows as it somehow doesnt get a valid usd stage, need to investigate
    #async def test_example(self):
    #    self.assertIsNone(None)
