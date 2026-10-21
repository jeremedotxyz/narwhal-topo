# Data contracts, coordinate frames and exports

All spatial quantities use metres. Coordinate interpretation is an explicit operator responsibility. Geographic longitude/latitude is not accepted as if it were ENU metres.

## Point files

Required columns/keys are `x`, `y`, `z`. Optional fields are `intensity`, `timestamp_ns`, `quality`, `line_id`.

```csv
x,y,z,intensity,timestamp_ns,quality,line_id
1.25,2.25,-15.02,1200,1000000000,0,1
1.30,2.20,-15.00,1250,1000050000,0,1
```

```json
{"x":1.25,"y":2.25,"z":-15.02,"intensity":1200,"timestamp_ns":1000000000,"quality":0,"line_id":1}
```

JSONL has one object per line. Files must not exceed 32 MiB or 300,000 points. Timestamp is an integer uint64 nanosecond count, quality a uint16 bitmask and line ID uint32. CSV timestamps are parsed as integers rather than passing through floating point; full nanosecond values remain exact in Python and accepted-point CSV. The browser is sent display positions and attributes, not potentially inexact JavaScript integer nanoseconds.

Missing optional fields default to zero. This does not verify synchronization. A source without UNSYNCED flags is only source-declared synchronized. Nonfinite positions or intensity and the invalid-return flag mask are rejected before reconstruction. A missing/null XYZ value can represent a no-return record and is counted as rejected rather than converted to a zero point.

ASCII PLY supports `format ascii 1.0`, a declared vertex count, scalar vertex properties, and at least x/y/z. Binary PLY and list-valued vertex properties are refused. Optional intensity can be present. Non-vertex elements are ignored after reading the declared vertex set; this importer is for point observations, not importing faces or meshes. Standard PLY output retains position and intensity only; use CSV for per-point timing/flags.

## Raw concept events

```json
{"schema_version":1,"timestamp_ns":0,"time_basis":"SIM_RELATIVE","simulated":true,"line_id":0,"angle_rad":0.0,"tof_ns":44.6992,"intensity":900}
```

The adapter is detected by the `tof_ns` key. Missing returns use `tof_ns:null`. It accepts the original Narwhal concept's fixed calibration only: 1.34 group index, 60 mm vertical baseline, zero system delay, 1-15 m range gate and +/-15 degree water-side scan. This is not a universal raw waveform interface or a real sensor calibration. Use `SENSOR_LOCAL` or provide external poses. `MAP_ENU` is refused for raw events.

## Quality flags

| Mask | Interpretation |
|---|---|
| 0x0001 | No return; rejected |
| 0x0002 | Out of range; rejected |
| 0x0004 | Saturated intensity; preserved, not automatically rejected |
| 0x0008 | Invalid delay; rejected |
| 0x0010 | Unsynchronized clock; reported in diagnostics |
| 0x0020 | Synthetic point; reported in interface/provenance |

Unknown upper bits are preserved without being interpreted. NWP1 health/status fields are not currently exposed in the retained Point model. No source-calibration assurance is derived from these flags.

## Poses and mounting transforms

Pose CSV columns:

```csv
timestamp_ns,tx,ty,tz,qx,qy,qz,qw
0,0,0,0,0,0,0,1
100000000,0.1,0,0,0,0,0,1
```

Translation is the local sensor origin in map ENU; quaternion rotates sensor axes into ENU when the mount is identity. Pose/point timestamps must share the same epoch and time scale. For Narwhal's proposed synchronized format this is TAI nanoseconds since 1970-01-01 00:00:00 TAI. Relative clocks are acceptable only if both streams share that same relative basis and their use is explicitly documented.

Rows must be strictly increasing. Quaternions are normalized; zero/nonfinite values fail. Interpolation uses linear translation and shortest-path SLERP. No extrapolation is allowed, and an interval larger than 0.2 seconds fails. Point timing precision does not establish physical time alignment.

The browser assumes poses already refer to the sensor. The CLI additionally supports `--extrinsics mounting.json`:

```json
{"q":[0,0,0,1],"t":[0.0,0.0,0.0]}
```

Here q/t map sensor points into the moving body frame before the trajectory body-to-map transform. Identity is not an implicit axis conversion. A body-pose source must include a measured mounting transform.

## NWP1 packet

The envelope is `<4sIHH`: magic `NWP1`, uint32 sequence, uint16 count (1-32), uint16 version (1). It is followed by count records and a little-endian uint32 CRC-32 over header+records. Record layout is `<QfffffHHIHH`, exactly 40 bytes:

| Offset | Field |
|---|---|
| 0 | timestamp_ns / uint64 |
| 8, 12, 16 | X, Y, Z / float32 |
| 20 | TX range / float32 |
| 24 | Water-side angle / float32 |
| 28 | Intensity / uint16 |
| 30 | Quality / uint16 |
| 32 | Line ID / uint32 |
| 36 | Health/status / uint16 |
| 38 | Reserved / uint16, zero |

Valid records require finite positions, angle and positive range. Invalid-return flags require NaN positions/range. Packets must match exact length and CRC. The server uses X/Y/Z as supplied; range/angle are validated but not reinterpreted. Raw ranging happens only in the raw JSONL adapter. The receiver's frame is configured at startup and is not encoded in NWP1.

## Map product

`metadata` contains version, settings, declared frame, units, source and evidence notes. `stats` describes counts, extrema, rectangular-grid coverage and processing time. `grid` provides columns, rows, lower-left corner, cell size, elevation, support count, sample spread, mean intensity, sampling proxy and slope. Internal flat array index is `row*cols+col`; row increases north. NoData is `null`. Cell coordinates refer to centers at `x0+(col+0.5)*cell`, `y0+(row+0.5)*cell`.

Contours are local metre segments grouped by elevation level. They are not topologically stitched polylines. The browser's `points` array can be display-decimated and is not a substitute for full-resolution numerical exports.

## ZIP contents

| File | Interpretation |
|---|---|
| `metadata.json` | Frame, source, settings, diagnostics and explicit uncertainty/evidence notes |
| `grid.json` | All numerical cell arrays; south-to-north row storage |
| `terrain.asc` | ESRI-style ASCII grid; north-to-south rows, -9999 NoData |
| `terrain.png` | North-up elevation palette, transparent unsupported cells; one image pixel per cell |
| `contours.svg` | Diagram with local contours, north up; viewBox scaled for display |
| `contours-local.json` | Original contour segment coordinates in declared local metres |
| `points.csv` | Full accepted points including timestamp, flags and line ID |
| `points.ply` | Full accepted XYZ and intensity for external cloud viewers |
| `README.txt` | Orientation, provenance and interpretation reminders |

ASC and PNG do not carry a verified CRS. No EPSG code, chart datum, geographic extent or georeferencing world file is invented. The local contour JSON is deliberately not described as RFC 7946 GeoJSON, which assumes geographic WGS84 coordinates. Use a validated adapter for geographic products.
