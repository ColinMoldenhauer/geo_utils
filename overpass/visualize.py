import geopandas
from shapely.geometry import Polygon
import matplotlib.pyplot as plt

def plot_area_polygon(points, ax=None, crs=None, convert_crs=None, **plot_kwargs):
    plot_defaults = {"color": "red",
                     "markersize": 1}
    plot_defaults.update(plot_kwargs)

    if ax is None: fig, ax = plt.subplots()

    poly = Polygon(points)
    data = geopandas.GeoSeries(poly, crs=crs)
    if convert_crs: data = data.to_crs(convert_crs)

    return data.plot(ax=ax, **plot_defaults)
