import omni.earth_2_command_center.app.core as core
import omni.earth_2_command_center.app.index as index
import omni.kit.test


class Test(omni.kit.test.AsyncTestCase):
    # Before running each test
    async def setUp(self):
        pass

    # After running each test
    async def tearDown(self):
        pass

    async def test_index_create_colormap(self):
        colormap = index.Colormap()
        self.assertIsNotNone(colormap)

    async def test_index_create_volume(self):
        features_api = core.get_state().get_features_api()
        # create volume
        volume = features_api.create_feature(
            index.ProjectedVolumeFeature,
            feature_desc=index.ProjectedVolumeFeatureDesc(
                name="Test",
            ),
        )

        self.assertIsNotNone(volume)
        self.assertEqual(volume.type, index.ProjectedVolumeFeature.feature_type)
