/******************************************************************************
 * Copyright 2025 NVIDIA Corporation. All rights reserved.
 *****************************************************************************/

// # XAC Kernel:
// ** Basic Sparse Volume Rendering **

// # Summary:
// render a sparse volume and optionally apply local shading

NV_IDX_XAC_VERSION_1_0

using namespace nv::index;
using namespace nv::index::xac;

class Volume_sample_program
{
    NV_IDX_VOLUME_SAMPLE_PROGRAM

public:
    NV_IDX_DEVICE_INLINE_MEMBER
    void initialize() {}

    NV_IDX_DEVICE_INLINE_MEMBER
    int execute(
        const Sample_info_self& sample_info,
              Sample_output&    sample_output)
    {
        // sample_output.set_color(make_float4(0.0f, 0.0f, 1.0f, 1.0f));
        // return NV_IDX_PROG_OK;

        // get current sample position
        const float3& sample_position = sample_info.sample_position_object_space;

        // get reference to the sparse volume
        const auto& sparse_volume = state.self;
        const Colormap colormap = state.self.get_colormap();

        // generate a volume sampler
        // filter modes: NEAREST, TRILINEAR, TRICUBIC_BSPLINE, TRICUBIC_CATMUL
        const auto sampler = sparse_volume.generate_sampler<float,VDB_volume_filter_mode::TRILINEAR, nanovdb::Fp8>();

        // sample the volume at the current position
        const float sample_value = sampler.fetch_sample(sample_position);

        // sample the color value
        const float4 sample_color = colormap.lookup(sample_value);

        // store the output color
        sample_output.set_color(sample_color);

        return NV_IDX_PROG_OK;
    }
}; // class Volume_sample_program
