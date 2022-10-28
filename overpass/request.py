import json
import pdb
import re
import urllib.parse
import urllib.request
from io import BytesIO
from urllib.error import HTTPError

import pandas as pd


class OverpassRequest:
    def __init__(self, base_url="https://overpass-api.de/api/interpreter?data=",
                 format_expression=None, expressions=None, out_expression=None, geojson=False):
        """
        Base class to create an Overpass Query and to request data from https://dev.overpass-api.de/overpass-doc/en/.
        :param base_url (optional): Base URL determining which public server to use.
        :param format_expression (optional): A valid initial overpass expression determining the output format.
        :param expressions (optional): A list of valid overpass expressions.
        :param out_expression (optional): A valid final overpass expression determining the output data.
        :param geojson (optional): Flag, whether to convert output data from OSM format to GeoJSON format.
        """
        self.base_url = base_url
        self.format_expr = format_expression or ""
        self.expressions = expressions or []
        self.out_expr = out_expression or ""
        self.geojson = geojson

    def set_format(self, format_expression):
        self.format_expr = format_expression

    def set_json_format(self):
        self.set_format("[out:json];")

    def set_csv_format(self, columns=[], header=True, sep=","):
        """
        :param columns: which data to include in the output CSV
        :param header: include a header row in the CSV
        :param sep: CSV separating character, default ","
        """
        cols = ','.join(columns)
        header = str(header).lower()
        self.format_expr = f'[out:csv({cols};{header};"{sep}")];'

    def bbox2filt(self, bbox):
        """
        :param bbox: bounding box of shape [[lat_min, long_min], [lat_max, long_max]]
        :return: string represenation of bbox used in Overpass API
        """
        return f"{bbox[0][0]},{bbox[0][1]},{bbox[1][0]},{bbox[1][1]}"

    def add_expression(self, expression):
        if isinstance(expression, list):
            for e in expression: self.add_expression(e)
        self.expressions.append(expression)

    def build_expression(self, type, semantic_filters=[], spatial_filters=[]):
        spatial_filters = [self.bbox2filt(filt) if isinstance(filt, list) else filt for filt in spatial_filters]
        sem = "".join([f"[{filt}]" for filt in semantic_filters])
        spat = "".join([f"({filt})" for filt in spatial_filters])
        self.expressions.append(type + sem + spat + ";")

    def set_conversion(self, convert):
        self.geojson = convert

    def set_output(self, out_expression):
        self.out_expr = out_expression

    def compose_query(self, verbose=False):
        assert len(self.expressions) > 0, "No expressions to compose, please add expressions first."
        self.query = self.format_expr
        for expr in self.expressions: self.query += expr
        if self.geojson: self.query += "convert item ::=::,::geom=geom(),_osm_type=type();"
        self.query += self.out_expr
        if verbose: print(f"{'Query:': <20}{self.query}")
        return self.query

    def get_data(self, raw_data=False, attempts=5, verbose=False):
        query = self.compose_query(verbose)
        format_search = re.search("[\[]out:([a-zA-Z]+)(?:[\(]|[]])", query)
        format = format_search.group(1) if format_search else "xml"

        url = self.base_url + query
        quoted = urllib.parse.quote(url, safe="/:?=")
        if verbose: print(f"{'Quoted URL:': <20}{quoted}")

        for i in range(attempts):
            try:
                requ = urllib.request.urlopen(quoted)
                if verbose: print(f"{'' if i else 'HTTP request:': <20}" +
                                  f"Attempt {i+1}/{attempts}: Success!")
                break
            except HTTPError as error:
                if i == attempts-1: raise error
                if verbose: print(f"{'' if i else 'HTTP request:': <20}" +
                                  f"Attempt {i+1}/{attempts}: {error}. Retrying!")

        with requ:
            data = requ.read()
        if raw_data:
            return data
        elif format == "csv":
            df = pd.read_csv(BytesIO(data))
            return df
        elif format == "json":
            d = json.loads(data.decode('utf8'))
            return d
        else:
            raise Warning("Unsupported format:", format)

    def print_query(self):
        query = self.compose_query(verbose=False)
        print(";\n".join(query.split(";")))


def get_area_bounding_points_check_orderCM(area_name, filters, ignore_enclaves=False, verbose=True):

    ovp = OverpassRequest()
    ovp.set_json_format()
    ovp.build_expression("area", [f'name="{area_name}"', *filters])
    ovp.add_expression("rel(pivot);")
    ovp.set_output("out geom;")

    data = ovp.get_data(verbose=verbose)
    bounds = data["elements"][0]["bounds"]
    assert len(data["elements"]) == 1, f"Output should have exactly one element, but has {len(data['elements'])}\nElements: {data['elements']}."

    members = data["elements"][0]["members"]
    points = []
    nodes = []
    exclaves = []
    ignored = []

    # remove all non-ways
    members_ways = [m for m in members if m["type"] == "way"]

    members_others = [m for m in members if m["type"] != "way"]
    members_nodes = [m for m in members_others if m["type"] == "node"]
    nodes = [[m["lon"], m["lat"]] for m in members_nodes]

    # TODO: handle rest members
    """
      "type": "relation",
          "ref": 3720495,
          "role": "subarea"
        },
    """
    member_rest = [m for m in members_others if m["type"] != "node"]
    # assert len(member_rest) == 0, f"rest should be empty, but is {member_rest}"

    for i, m in enumerate(members_ways[:]):
        curr_segm = [[p["lon"], p["lat"]] for p in m["geometry"]]
        if len(points):
            first = curr_segm[0]
            f_inp = first in points
            f_iprev = first == points[-1]
            last = curr_segm[-1]
            l_inp = last in points
            l_iprev = last == points[-1]

            if f_inp and l_inp:
                # closing segment
                if first == points[-1]:
                    points.extend(curr_segm)
                elif last == points[-1]:
                    points.extend(curr_segm[::-1])
                else:
                    raise Exception("Points not consecutive, check!")
            elif f_inp:
                if ignore_enclaves and not f_iprev:
                    ignored.extend(curr_segm)
                    continue
                # next segment, correct order
                points.extend(curr_segm)
            elif l_inp:
                if ignore_enclaves and not l_iprev:
                    ignored.extend(curr_segm)
                    continue
                # next segment, wrong order
                points.extend(curr_segm[::-1])
            else:
                # found an isolated border part -> don't add to main polygon
                if ignore_enclaves and (first in ignored or last in ignored):
                    ignored.extend(curr_segm)
                    continue
                if exclaves:
                    last_exclave = exclaves[-1]
                    f_ine = first in last_exclave
                    l_ine = last in last_exclave

                    if f_ine and l_ine:
                        if first == last_exclave[-1]:
                            # closing segment, correct order
                            exclaves[-1].extend(curr_segm)
                        elif last == last_exclave[-1]:
                            # closing segment, wrong order
                            exclaves[-1].extend(curr_segm[::-1])
                        else:
                            # potential unknown case
                            raise Exception("Points not consecutive, check!")
                    elif f_ine:
                        # next exclave segment, correct order
                        exclaves[-1].extend(curr_segm)
                    elif l_ine:
                        # next exclave segment, wrong order
                        exclaves[-1].extend(curr_segm[::-1])
                    else:
                        # new enclave
                        exclaves.append(curr_segm)
                else:
                    # first enclave
                    exclaves.append(curr_segm)
        else:
            # assumes first segment is not special (exclave, island, etc)
            # check order of first segment explicitly


            first = m["geometry"][0]
            first = [first["lon"], first["lat"]]
            last = m["geometry"][-1]
            last = [last["lon"], last["lat"]]

            # get next segment
            # TODO: handle edge case at end
            try:
                next_segm = [[p["lon"], p["lat"]] for p in members_ways[i+1]["geometry"]]
            except Exception as e:
                print("problem with next segment")
                print(members_ways[i+1])
                raise e

            if last in next_segm:
                # correct order
                points.extend(curr_segm)
            elif first in next_segm:
                # first segment in wrong order
                points.extend(curr_segm[::-1])
            else:
                # assuming the order of border segments is correct, the first segment is already an enclave
                exclaves.append(curr_segm)

    return points, exclaves, nodes, bounds
