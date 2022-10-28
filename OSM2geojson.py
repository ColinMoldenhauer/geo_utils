import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

from overpass import (get_area_bounding_points_check_order,
                      plot_area_polygon,
                      points_to_geojson)


crs = "EPSG:4326"
target_crs = "EPSG:3857"

fig, ax = plt.subplots(1, 1, figsize=(10,8))

name = "bayern"
points, exclaves, nodes, bounds = get_area_bounding_points_check_order("Bayern", [], ignore_enclaves=True, verbose=True)
plot_area_polygon(points, ax=ax, crs=crs, convert_crs=target_crs)
points_to_geojson(points, f"{name}.json", crs=crs, to_polygon=True)

plt.show()