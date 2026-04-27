#import omni.earth_2_command_center.app.globe_view.globe_scene as globe_scene
#import omni.earth_2_command_center.app.globe_view.globe_ui as globe_ui
#import omni.earth_2_command_center.app.globe_view.reference_manager as reference_manager

import omni.kit.test
#import datetime

class Test(omni.kit.test.AsyncTestCase):
    async def setUp(self):
        '''No need for setup work'''

    async def tearDown(self):
        '''No need for teardown work'''

    # ============================================================
    # Globe View Tests
    # ============================================================
    #async def test_globe_view_window(self):
    #    window = globe_view.Earth2GlobeView()
    #    self.assertIsNotNone(window)
    #    del window
