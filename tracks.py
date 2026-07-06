"""Import KML / KMZ / GPX track files and normalise them to a simple geometry,
then emit GeoJSON (for the Leaflet overlay) or GPX (for download/export).

Deliberately small: it handles the geometry road-trip files actually carry —
Placemark Points (-> waypoints), LineStrings and gx:Tracks (-> tracks) from KML,
and wpt / trk / rte from GPX. Styling, folders, overlays, NetworkLinks, polygons
etc. are ignored (and named in `skipped`). Format is detected by magic bytes,
not the filename. XML is parsed with defusedxml (untrusted public uploads).
"""

from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

from defusedxml.ElementTree import fromstring as _xml_fromstring


class TrackError(ValueError):
    """Unusable / unrecognised upload — the caller turns this into a 400."""


# A KMZ is a ZIP; guard against decompression bombs on the public endpoint.
_MAX_KMZ_UNCOMPRESSED = 64 * 1024 * 1024
_MAX_KMZ_ENTRIES = 1000


def _empty() -> dict:
    return {"waypoints": [], "tracks": [], "skipped": []}


def _local(tag: str) -> str:
    """Element tag without its XML namespace: '{ns}Point' -> 'Point'."""
    return tag.rsplit("}", 1)[-1]


def _descendants(elem, name):
    return [e for e in elem.iter() if _local(e.tag) == name]


def _child_text(elem, name, default=""):
    for e in elem:
        if _local(e.tag) == name and e.text:
            return e.text.strip()
    return default


def _float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


# ---- KML ----

def _kml_coords(text):
    """A KML <coordinates> body: whitespace-separated 'lon,lat[,ele]' tuples."""
    pts = []
    for tok in (text or "").split():
        parts = tok.split(",")
        if len(parts) < 2:
            continue
        lon, lat = _float(parts[0]), _float(parts[1])
        if lat is None or lon is None:
            continue
        pts.append({"lat": lat, "lon": lon, "ele": _float(parts[2]) if len(parts) >= 3 else None})
    return pts


def _parse_kml(root):
    geom = _empty()
    skipped = set()
    for pm in _descendants(root, "Placemark"):
        name = _child_text(pm, "name")
        for pt in _descendants(pm, "Point"):
            for c in _kml_coords(_child_text(pt, "coordinates")):
                geom["waypoints"].append({"name": name, **c})
        for ls in _descendants(pm, "LineString"):
            pts = _kml_coords(_child_text(ls, "coordinates"))
            if pts:
                geom["tracks"].append({"name": name, "points": pts})
        for gx in _descendants(pm, "Track"):          # gx:Track -> local "Track"
            pts = []
            for c in _descendants(gx, "coord"):        # gx:coord: "lon lat [ele]" (space-sep)
                bits = (c.text or "").split()
                if len(bits) >= 2 and _float(bits[0]) is not None and _float(bits[1]) is not None:
                    pts.append({"lat": _float(bits[1]), "lon": _float(bits[0]),
                                "ele": _float(bits[2]) if len(bits) >= 3 else None})
            if pts:
                geom["tracks"].append({"name": name, "points": pts})
        for unhandled in ("Polygon", "Model"):
            if _descendants(pm, unhandled):
                skipped.add(unhandled)
    geom["skipped"] = sorted(skipped)
    return geom


# ---- GPX ----

def _gpx_point(elem):
    lat, lon = _float(elem.get("lat")), _float(elem.get("lon"))
    if lat is None or lon is None:
        return None
    return {"lat": lat, "lon": lon, "ele": _float(_child_text(elem, "ele") or None)}


def _parse_gpx(root):
    geom = _empty()
    for wpt in _descendants(root, "wpt"):
        p = _gpx_point(wpt)
        if p:
            p["name"] = _child_text(wpt, "name")
            geom["waypoints"].append(p)
    for container, ptname in (("trk", "trkpt"), ("rte", "rtept")):
        for c in _descendants(root, container):
            pts = [p for p in (_gpx_point(e) for e in _descendants(c, ptname)) if p]
            if pts:
                geom["tracks"].append({"name": _child_text(c, "name"), "points": pts})
    return geom


# ---- KMZ (zip wrapping a KML) ----

def _read_kmz(data: bytes) -> bytes:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise TrackError("not a valid KMZ (bad zip)") from e
    infos = zf.infolist()
    if len(infos) > _MAX_KMZ_ENTRIES:
        raise TrackError("KMZ has too many entries")
    if sum(i.file_size for i in infos) > _MAX_KMZ_UNCOMPRESSED:
        raise TrackError("KMZ is too large uncompressed")
    kmls = [i for i in infos if i.filename.lower().endswith(".kml")]
    if not kmls:
        raise TrackError("KMZ contains no .kml")
    pick = next((i for i in kmls if i.filename.lower() == "doc.kml"), kmls[0])
    return zf.read(pick.filename)


# ---- entry points ----

def parse(data: bytes) -> dict:
    """Detect KML/KMZ/GPX and return {waypoints, tracks, skipped}. Raises
    TrackError on anything unrecognised or empty."""
    if not data:
        raise TrackError("empty file")
    if data[:4] == b"PK\x03\x04":            # ZIP magic -> KMZ
        data = _read_kmz(data)
    try:
        root = _xml_fromstring(data)
    except Exception as e:
        raise TrackError(f"not valid XML: {type(e).__name__}") from e
    tag = _local(root.tag)
    if tag == "kml":
        geom = _parse_kml(root)
    elif tag == "gpx":
        geom = _parse_gpx(root)
    else:
        raise TrackError(f"unrecognised file (root <{tag}>): need KML, KMZ, or GPX")
    if not geom["waypoints"] and not geom["tracks"]:
        raise TrackError("no waypoints or tracks found")
    return geom


def counts(geom) -> dict:
    return {"waypoints": len(geom["waypoints"]), "tracks": len(geom["tracks"]),
            "points": sum(len(t["points"]) for t in geom["tracks"])}


def to_geojson(geom) -> dict:
    features = []
    for w in geom["waypoints"]:
        features.append({"type": "Feature", "properties": {"name": w.get("name") or ""},
                         "geometry": {"type": "Point", "coordinates": [w["lon"], w["lat"]]}})
    for t in geom["tracks"]:
        features.append({"type": "Feature", "properties": {"name": t.get("name") or ""},
                         "geometry": {"type": "LineString",
                                      "coordinates": [[p["lon"], p["lat"]] for p in t["points"]]}})
    return {"type": "FeatureCollection", "features": features}


def to_gpx(geom) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<gpx version="1.1" creator="waypoint" xmlns="http://www.topografix.com/GPX/1/1">']
    for w in geom["waypoints"]:
        out.append(f'  <wpt lat="{w["lat"]:.7f}" lon="{w["lon"]:.7f}">')
        if w.get("ele") is not None:
            out.append(f'    <ele>{w["ele"]:.2f}</ele>')
        if w.get("name"):
            out.append(f'    <name>{escape(w["name"])}</name>')
        out.append('  </wpt>')
    for t in geom["tracks"]:
        out.append('  <trk>')
        if t.get("name"):
            out.append(f'    <name>{escape(t["name"])}</name>')
        out.append('    <trkseg>')
        for p in t["points"]:
            out.append(f'      <trkpt lat="{p["lat"]:.7f}" lon="{p["lon"]:.7f}">')
            if p.get("ele") is not None:
                out.append(f'        <ele>{p["ele"]:.2f}</ele>')
            out.append('      </trkpt>')
        out.append('    </trkseg>')
        out.append('  </trk>')
    out.append('</gpx>')
    return "\n".join(out) + "\n"
