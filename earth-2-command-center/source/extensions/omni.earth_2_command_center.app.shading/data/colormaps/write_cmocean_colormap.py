import sys
import csv
import png
import numpy as np
import cmocean

def write_cmocean_colormap(colormap_name, png_path):
    colormap = getattr(cmocean.cm, colormap_name)
    if not colormap:
        raise RuntimeError(f'Could not retrieve colormap: "{colormap_name}"')
    num_rows = colormap.N
    pixels = np.ndarray((1,num_rows*4), dtype=np.float32)
    for i in range(num_rows):
        x = i/(num_rows-1)
        val = colormap(x)
        pixels[0,4*i:4*i+4] = val
    
    pixels *= 256*256-1
    pixels = pixels.astype(np.uint16)
    png.from_array(pixels, mode="RGBA;16").save(png_path)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise RuntimeError('Argument missing')
    
    colormap_name = sys.argv[1]
    png_path = f'./{colormap_name}.png'
    
    write_cmocean_colormap(colormap_name, png_path)
