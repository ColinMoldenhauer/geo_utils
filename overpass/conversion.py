import os
import pickle

import geopandas
import numpy as np
import pandas as pd
import shapely.validation
from shapely.geometry import Polygon, LineString


def df2points(df):
    points = np.array(df.apply(lambda row: [row["@lat"], row["@lon"]], axis=1).to_list())
    return points


def osmdict2points(data):
    points = []
    for el in data["elements"]:
        if el["type"] == "node":
            lat = el["lat"]
            lon = el["lon"]
        else:
            lat = el["center"]["lat"]
            lon = el["center"]["lon"]
        points.append((lat, lon))
    return np.array(points)


def geodict2points(data):
    points = []
    for el in data["elements"]:
        lon, lat = el["geometry"]["coordinates"]
        points.append((lon, lat))
    return np.array(points)


def data2points(data):
    if isinstance(data, dict):
        if data["elements"][0]["type"] in ["node", "way", "relation"]:
            points = osmdict2points(data)
        else:
            points = geodict2points(data)
    elif isinstance(data, pd.DataFrame):
        points = df2points(data)
    return points


def save_points(points, filename, overwrite=False):
    if not os.path.exists(filename) or overwrite:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "wb") as fp:
            pickle.dump(points, fp)


def geotransform_points(points, crs_in="EPSG:4326", crs_out="EPSG:3857"):
    points = geopandas.points_from_xy([p[0] for p in points], [p[1] for p in points])
    data = geopandas.GeoSeries(points, crs=crs_in)
    data_out = data.to_crs(crs_out)
    points_out = data_out.apply(lambda p: (p.x, p.y)).to_list()
    return points_out


def points_to_geojson(points, file, to_polygon=False, crs="EPSG:3857"):
    assert file.endswith("json"), "File must be a json!"
    if isinstance(points, list):
        points = geopandas.points_from_xy([p[0] for p in points], [p[1] for p in points])
        if to_polygon: points = Polygon(points)
    data = geopandas.GeoSeries(points, crs=crs)
    data.to_file(file, driver='GeoJSON')


def points_to_geojson_old(points, file, crs="EPSG:3857"):
    points = geopandas.points_from_xy([p[0] for p in points], [p[1] for p in points])
    data = geopandas.GeoSeries(points, crs=crs)
    json_str = data.to_json()
    with open(file, "w") as f:
        f.write(json_str)


def points_to_csv(points, name="", crs="EPSG:3857"):
    points = geopandas.points_from_xy([p[0] for p in points], [p[1] for p in points])
    data = geopandas.GeoSeries(points, crs=crs)
    df = geopandas.GeoDataFrame({"x": data.x, "y": data.y})
    df.to_csv(name)


def points_to_pickle(points, file):
    with open(file, "wb") as f:
        pickle.dump(points, f)


def points_from_pickle(file):
    with open(file, "rb") as f:
        return pickle.load(f)

def filter_points(points, h=None, v=None):
    # format points [lat lon]
    points = np.array(points)
    if h:
        hmin, hmax = h
    else:
        hmin, hmax = [None]*2
    if hmin is None:
        hmin = np.min(points[:, 0])
    if hmax is None:
        hmax = np.max(points[:, 0])
    if v:
        vmin, vmax = v
    else:
        vmin, vmax = [None]*2
    if vmin is None:
        vmin = np.min(points[:, 1])
    if vmax is None:
        vmax = np.max(points[:, 1])

    h_valid = (points[:,0] >= hmin) & (points[:,0] <= hmax)
    v_valid = (points[:,1] >= vmin) & (points[:,1] <= vmax)

    points = points[h_valid & v_valid]
    return points.tolist()


def split_area(points, split_percentages, mode="h"):
    assert sum(split_percentages) == 1, "Sum of percentages must be 1!"
    eps = 1e-3

    points = np.array(points)

    xmin = np.min(points[:, 0])
    xmax = np.max(points[:, 0])
    ymin = np.min(points[:, 1])
    ymax = np.max(points[:, 1])

    perc_cumulative = 0
    remainder = Polygon(points)
    splits = []

    for i, perc in enumerate(split_percentages[:-1]):
        perc_cumulative += perc
        print(i, perc, perc_cumulative)
        if mode == "h":
            y = ymin + perc_cumulative*(ymax-ymin)
            splitter = LineString([[xmin-eps, y], [xmax+eps, y]])
            split_result = shapely.ops.split(remainder, splitter)

            curr_split = split_result.geoms[0]
            remainder = split_result.geoms[1]
        elif mode == "v":
            x = xmin + perc_cumulative*(xmax-xmin)
            splitter = LineString([[x, ymin-eps], [x, ymax+eps]])
            split_result = shapely.ops.split(remainder, splitter)

            curr_split = split_result.geoms[0]
            remainder = split_result.geoms[1]
        else:
            raise NotImplementedError(f"Unknown mode {mode}.")

        splits.append(curr_split)
        if i == len(split_percentages)-2:
            splits.append(remainder)

    return splits
