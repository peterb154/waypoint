"""Pins the KML/KMZ/GPX importer (tracks.py): each format normalises to the same
geometry, round-trips to GPX, and untrusted/garbage input is rejected safely."""

from __future__ import annotations

import io
import zipfile

import pytest

import tracks

KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark><name>Start</name><Point><coordinates>-96.3050,39.2019,0</coordinates></Point></Placemark>
    <Placemark><name>Route</name><LineString>
      <coordinates>-96.30,39.20 -96.31,39.21 -96.32,39.22</coordinates>
    </LineString></Placemark>
  </Document>
</kml>"""

GPX = """<?xml version="1.0"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
  <wpt lat="39.2019" lon="-96.3050"><name>Start</name></wpt>
  <trk><name>Route</name><trkseg>
    <trkpt lat="39.20" lon="-96.30"><ele>310</ele></trkpt>
    <trkpt lat="39.21" lon="-96.31"/>
  </trkseg></trk>
</gpx>"""


def test_kml_parses_point_and_line():
    g = tracks.parse(KML.encode())
    assert tracks.counts(g) == {"waypoints": 1, "tracks": 1, "points": 3}
    assert g["waypoints"][0]["name"] == "Start"
    assert g["waypoints"][0]["lat"] == pytest.approx(39.2019)


def test_gpx_parses_wpt_and_trk():
    g = tracks.parse(GPX.encode())
    assert tracks.counts(g) == {"waypoints": 1, "tracks": 1, "points": 2}
    assert g["tracks"][0]["points"][0]["ele"] == pytest.approx(310.0)


def test_kmz_is_just_zipped_kml():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("doc.kml", KML)
    g = tracks.parse(buf.getvalue())
    assert tracks.counts(g)["tracks"] == 1


def test_geojson_shape():
    fc = tracks.to_geojson(tracks.parse(KML.encode()))
    types = sorted(f["geometry"]["type"] for f in fc["features"])
    assert types == ["LineString", "Point"]
    # GeoJSON is [lon, lat]
    pt = next(f for f in fc["features"] if f["geometry"]["type"] == "Point")
    assert pt["geometry"]["coordinates"] == [-96.3050, 39.2019]


def test_kml_round_trips_to_gpx_and_back():
    g1 = tracks.parse(KML.encode())
    g2 = tracks.parse(tracks.to_gpx(g1).encode())
    assert tracks.counts(g1) == tracks.counts(g2)
    assert g2["tracks"][0]["points"][1]["lat"] == pytest.approx(39.21)


def test_name_is_xml_escaped_on_export():
    g = {"waypoints": [{"name": "A & B <x>", "lat": 1.0, "lon": 2.0, "ele": None}],
         "tracks": [], "skipped": []}
    gpx = tracks.to_gpx(g)
    assert "A &amp; B &lt;x&gt;" in gpx
    # and it survives a round trip
    assert tracks.parse(gpx.encode())["waypoints"][0]["name"] == "A & B <x>"


def test_garbage_and_empty_rejected():
    for bad in (b"", b"not xml at all", b"<html><body>nope</body></html>"):
        with pytest.raises(tracks.TrackError):
            tracks.parse(bad)


def test_xxe_entity_is_not_expanded():
    # defusedxml must refuse the external/entity trick rather than read /etc/passwd.
    xxe = (b'<?xml version="1.0"?><!DOCTYPE kml [<!ENTITY x "PWNED">]>'
           b'<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><name>&x;</name>'
           b'<Point><coordinates>1,2</coordinates></Point></Placemark></kml>')
    with pytest.raises(tracks.TrackError):
        tracks.parse(xxe)
