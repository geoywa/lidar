"""Module for delineating the nested hierarcy of elevated features (i.e., mounts).

"""

import os
import pkg_resources
import richdem as rd
import numpy as np
import lidar
from .filling import ExtractSinks
from .slicing import DelineateDepressions


def get_min_max_nodata(dem):
    """Gets the minimum, maximum, and no_data value of a numpy array.

    Args:
        dem (np.array): The numpy array containing the image.

    Returns:
        tuple: The minimum, maximum, and no_data value.
    """
    no_data = dem.no_data
    max_elev = np.float(np.max(dem[dem != no_data]))
    min_elev = np.float(np.min(dem[dem != no_data]))

    return min_elev, max_elev, no_data


def FlipDEM(dem, delta=100, out_file=None):
    """Flips the DEM.

    Args:
        dem (np.array): The numpy array containing the image.
        delta (int, optional): The base value to be added to the flipped DEM. Defaults to 100.
        out_file (str, optional): File path to the output image. Defaults to None.

    Returns:
        np.array: The numpy array containing the flipped DEM.
    """
    # get min and max elevation of the dem
    no_data = dem.no_data
    max_elev = np.float(np.max(dem[dem != no_data]))
    # min_elev = np.float(np.min(dem[dem != no_data]))

    dem = dem * (-1) + max_elev + delta
    dem[dem == no_data * (-1)] = no_data

    if out_file is not None:
        print("Saving flipped dem ...")
        rd.SaveGDAL(out_file, dem)
        return out_file

    return dem


def DelineateMounts(in_dem, min_size, min_height, interval, out_dir, bool_shp=False):
    """Delineates the nested hierarchy of elevated features (i.e., mounts).

    Args:
        in_dem (str): File path to the input DEM.
        min_size (int): The minimum number of pixels to be considered as an object.
        min_height (float): The minimum depth of the feature to be considered as an object.
        interval (float): The slicing interval.
        out_dir (str): The output directory.
        bool_shp (bool, optional): Whether to generate shapefiles. Defaults to False.

    Returns:
        tuple: File paths to the depression ID and level.
    """
    if not os.path.exists(out_dir):
        os.mkdir(out_dir)

    print("Loading data ...")
    dem = rd.LoadGDAL(in_dem)
    # projection = dem.projection
    geotransform = dem.geotransform
    cell_size = np.round(geotransform[1], decimals=3)

    out_dem = os.path.join(out_dir, "dem_flip.tif")
    in_dem = FlipDEM(dem, delta=100, out_file=out_dem)

    min_elev, max_elev, no_data = get_min_max_nodata(dem)
    print(
        "min = {:.2f}, max = {:.2f}, no_data = {}, cell_size = {}".format(
            min_elev, max_elev, no_data, cell_size
        )
    )

    sink_path = ExtractSinks(in_dem, min_size, out_dir)
    dep_id_path, dep_level_path = DelineateDepressions(
        sink_path, min_size, min_height, interval, out_dir, bool_shp
    )

    return dep_id_path, dep_level_path


# #####################################  main script
if __name__ == "__main__":

    # identify the sample data directory of the package
    package_name = "lidar"
    data_dir = pkg_resources.resource_filename(package_name, "data/")

    # use the sample dem. Change it to your own dem if needed
    in_dem = os.path.join(data_dir, "dsm.tif")
    # set output directory. By default, use the temp directory under user's home directory
    out_dir = os.path.join(os.path.expanduser("~"), "temp")

    if not os.path.exists(out_dir):
        os.mkdir(out_dir)

    # parameters for identifying sinks and delineating nested depressions
    min_size = 1000  # minimum number of pixels as a depression
    min_height = 0.3  # minimum depth as a depression
    interval = 0.3  # slicing interval for the level-set method
    bool_shp = False  # output shapefiles for each individual level

    mount_id_path, mount_level_path = DelineateMounts(
        in_dem, min_size, min_height, interval, out_dir, bool_shp
    )
    print("Results are saved in: {}".format(out_dir))

    dem = rd.LoadGDAL(in_dem)
    dem_fig = rd.rdShow(
        dem, ignore_colours=[0], axes=False, cmap="jet", figsize=(6, 5.5)
    )
    mount_id = rd.LoadGDAL(mount_id_path)
    mount_id_fig = rd.rdShow(
        mount_id, ignore_colours=[0], axes=False, cmap="jet", figsize=(6, 5.5)
    )
    mount_level = rd.LoadGDAL(mount_level_path)
    mount_level_fig = rd.rdShow(
        mount_level, ignore_colours=[0], axes=False, cmap="jet", figsize=(6, 5.5)
    )
