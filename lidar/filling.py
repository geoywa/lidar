import os
import time
import numpy as np
import richdem as rd
from scipy import ndimage
from skimage import measure
from osgeo import gdal, ogr, osr


# class for true depression
class Depression:
    def __init__(self, id, count, size, volume, meanDepth, maxDepth, minElev, bndElev):
        self.id = id
        self.count = count
        self.size = size
        self.volume = volume
        self.meanDepth = meanDepth
        self.maxDepth = maxDepth
        self.minElev = minElev
        self.bndElev = bndElev


# identify regions based on region growing method
def regionGroup(img_array, min_size, no_data):
    img_array[img_array == no_data] = 0
    label_objects, nb_labels = ndimage.label(img_array)
    sizes = np.bincount(label_objects.ravel())
    mask_sizes = sizes > min_size
    mask_sizes[0] = 0
    image_cleaned = mask_sizes[label_objects]
    label_objects, nb_labels = ndimage.label(image_cleaned)
    # nb_labels is the total number of objects. 0 represents background object.
    return label_objects, nb_labels


# convert numpy array to rdarray
def np2rdarray(in_array, no_data, projection, geotransform):
    out_array = rd.rdarray(in_array, no_data=no_data)
    out_array.projection = projection
    out_array.geotransform = geotransform
    return out_array


# compute depression attributes
def get_dep_props(objects, resolution):
    dep_list = []

    for object in objects:
        unique_id = object.label
        count = object.area
        size = count * pow(resolution, 2)  # depression size
        min_elev = np.float(object.min_intensity)  # depression min elevation
        max_elev = np.float(object.max_intensity)  # depression max elevation
        max_depth = max_elev - min_elev  # depression max depth
        mean_depth = np.float((max_elev * count - np.sum(object.intensity_image)) / count)  # depression mean depth
        volume = mean_depth * count * pow(resolution, 2)  # depression volume
        dep_list.append(Depression(unique_id, count, size, volume, mean_depth, max_depth, min_elev, max_elev))

    return dep_list


# save the depression list info to csv
def write_dep_csv(dep_list, csv_file):
    csv = open(csv_file, "w")
    header = "region-id" + "," + "count"+"," + "area" + "," + "volume" + "," + "avg-depth" + "," + "max-depth" + \
             "," + "min-elev" + "," + "max-elev"
    csv.write(header + "\n")
    for dep in dep_list:
        line = "{},{},{},{:.2f},{:.2f},{:.2f},{:.2f},{:.2f}".format(dep.id, dep.count, dep.size, dep.volume,
                                                                dep.meanDepth, dep.maxDepth, dep.minElev, dep.bndElev)
        csv.write(line + "\n")
    csv.close()


# raster to vector
def polygonize(img,shp_path):
    # mapping between gdal type and ogr field type
    type_mapping = {gdal.GDT_Byte: ogr.OFTInteger,
                    gdal.GDT_UInt16: ogr.OFTInteger,
                    gdal.GDT_Int16: ogr.OFTInteger,
                    gdal.GDT_UInt32: ogr.OFTInteger,
                    gdal.GDT_Int32: ogr.OFTInteger,
                    gdal.GDT_Float32: ogr.OFTReal,
                    gdal.GDT_Float64: ogr.OFTReal,
                    gdal.GDT_CInt16: ogr.OFTInteger,
                    gdal.GDT_CInt32: ogr.OFTInteger,
                    gdal.GDT_CFloat32: ogr.OFTReal,
                    gdal.GDT_CFloat64: ogr.OFTReal}

    ds = gdal.Open(img)
    prj = ds.GetProjection()
    srcband = ds.GetRasterBand(1)

    dst_layername = "Shape"
    drv = ogr.GetDriverByName("ESRI Shapefile")
    dst_ds = drv.CreateDataSource(shp_path)
    srs = osr.SpatialReference(wkt=prj)

    dst_layer = dst_ds.CreateLayer(dst_layername, srs=srs)
    # raster_field = ogr.FieldDefn('id', type_mapping[srcband.DataType])
    raster_field = ogr.FieldDefn('id', type_mapping[gdal.GDT_Int32])
    dst_layer.CreateField(raster_field)
    gdal.Polygonize(srcband, srcband, dst_layer, 0, [], callback=None)
    del img, ds, srcband, dst_ds, dst_layer


# extract sinks from dem
def ExtractSinks(in_dem, min_size, out_dir):

    start_time = time.time()

    out_dem = os.path.join(out_dir, "dem.tif")
    out_dem_filled = os.path.join(out_dir, "dem_filled.tif")
    out_dem_diff = os.path.join(out_dir, "dem_diff.tif")
    out_sink = os.path.join(out_dir, "sink.tif")
    out_region = os.path.join(out_dir, "region.tif")
    out_depth = os.path.join(out_dir, "depth.tif")
    out_csv_file = os.path.join(out_dir, "regions_info.csv")
    out_vec_file = os.path.join(out_dir, "regions.shp")

    # create output folder if nonexistent
    if not os.path.exists(out_dir):
        os.mkdir(out_dir)

    # load the dem and get dem info
    print("Loading data ...\n")
    dem = rd.LoadGDAL(in_dem)
    no_data = dem.no_data
    projection = dem.projection
    geotransform = dem.geotransform
    cell_size = geotransform[1]

    # get min and max elevation of the dem
    max_elev = np.float(np.max(dem))
    min_elev = np.float(np.min(dem[dem > 0]))
    print("min = {:.2f}, max = {:.2f}, no_data = {}, cell_size = {}\n".format(min_elev, max_elev, no_data, cell_size))

    # depression filling
    print("Depression filling ...\n")
    dem_filled = rd.FillDepressions(dem, in_place=False)
    dem_diff = dem_filled - dem
    dem_diff.no_data = 0

    print("Saving filled dem ...\n")
    rd.SaveGDAL(out_dem_filled, dem_filled)
    rd.SaveGDAL(out_dem_diff, dem_diff)

    # nb_labels is the total number of objects. 0 represents background object.
    print("Region grouping ...\n")
    label_objects, nb_labels = regionGroup(dem_diff, min_size, no_data)
    dem_diff[label_objects == 0] = 0
    depth = np2rdarray(dem_diff, no_data=0, projection=projection, geotransform=geotransform)
    rd.SaveGDAL(out_depth, depth)
    del dem_diff, depth

    print("Computing properties ...\n")
    objects = measure.regionprops(label_objects, dem)
    dep_list = get_dep_props(objects, cell_size)
    write_dep_csv(dep_list, out_csv_file)
    del objects, dep_list

    # convert numpy to richdem data format
    region = np2rdarray(label_objects, no_data=0, projection=projection, geotransform=geotransform)
    del label_objects

    print("Saving sink dem ...\n")
    sink = np.copy(dem)
    sink[region == 0] = 0
    sink = np2rdarray(sink, no_data=0, projection=projection, geotransform=geotransform)
    rd.SaveGDAL(out_sink, sink)
    # del sink

    print("Saving refined dem ...\n")
    dem_refined = dem_filled
    dem_refined[region > 0] = dem[region > 0]
    dem_refined = np2rdarray(dem_refined, no_data=no_data, projection=projection, geotransform=geotransform)
    rd.SaveGDAL(out_dem, dem_refined)
    rd.SaveGDAL(out_region, region)
    del dem_refined, region, dem

    print("Converting raster to vector ...\n")
    polygonize(out_region, out_vec_file)

    end_time = time.time()
    print("Total run time:\t\t\t {:.4f} s\n".format(end_time - start_time))

    return sink


if __name__ == '__main__':

    # ************************ change the following parameters if needed ******************************** #
    # set input files
    in_dem = "data/dem.tif"
    # parameters for depression filling
    min_size = 1000        # minimum number of pixels as a depression
    min_depth = 0.3        # minimum depression depth
    # set output directory
    out_dir = os.path.join(os.path.expanduser("~"), "temp")  # create a temp folder under user home directory
    # ************************************************************************************************** #

    sink = ExtractSinks(in_dem, min_size=min_size, out_dir=out_dir)
    dem = rd.LoadGDAL(in_dem)
    demfig = rd.rdShow(dem, ignore_colours=[0], axes=False, cmap='jet', figsize=(6, 5.5))
    sinkfig = rd.rdShow(sink, ignore_colours=[0], axes=False, cmap='jet', figsize=(6, 5.5))

    print("Results are saved in: {}".format(out_dir))
