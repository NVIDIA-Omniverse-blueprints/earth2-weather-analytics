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
