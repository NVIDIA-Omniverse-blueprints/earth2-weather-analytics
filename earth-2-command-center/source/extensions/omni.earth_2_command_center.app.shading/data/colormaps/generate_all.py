import matplotlib as mpl
import cmocean

from write_matplotlib_colormap import *
from write_cmocean_colormap import *
from write_cmweather_colormap import *

if __name__ == '__main__':
    colormaps = mpl.colormaps()
    for c in colormaps:
        print(f'Processing "{c}"')
        write_matplotlib_colormap(c, f'{c}.png')

    #colormaps = cmocean.cm.cmapnames
    #for c in colormaps:
    #    print(f'Processing "{c}"')
    #    write_cmocean_colormap(c, f'{c}.png')


