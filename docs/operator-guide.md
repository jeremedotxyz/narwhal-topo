# Operator guide

## Start and inspect

From a source checkout, run `PYTHONPATH=src python3 -m narwhal_topo serve`. Open the printed localhost URL. The first model is a synthetic test basin; its seeded origin remains visible in the interface. The service builds the model before printing the ready URL.

Use 3D terrain to inspect the gridded surface, Point cloud to examine accepted returns, Relief map for north-up elevation/contours and Coverage for cell support. Drag the 3D canvas to orbit and use a wheel/trackpad scroll to zoom. Reset view returns to the initial camera. Vertical exaggeration changes only drawing, not elevations or exports. Color attribute changes do not recompute the terrain.

Move the Northing slider to select a grid row for a cross-section. Missing cells break the profile. In plan views, click a cell to inspect coordinates, count, elevation and sampling proxy. A hole is not zero elevation.

## Import a file

Choose Import point cloud and supply CSV, JSONL or ASCII PLY. Select the actual coordinate interpretation. MAP_ENU assumes your positions are already registered in local east/north/up metres. SENSOR_LOCAL is inspection only and does not turn forward range into bathymetry. POSE_REGISTERED requires an external sensor-pose CSV with matching timestamps.

The browser pose workflow assumes the trajectory is already at the sensor origin. For a navigation body pose, use the CLI and a measured extrinsic mounting transform. Review [data contracts](data-contracts.md) before using real measurements. Unsupported files, nonphysical configuration or missing poses fail with an explanation while preserving the last valid map.

## Tune support instead of inventing detail

Grid cell size controls aggregation. Minimum points controls evidence support. Start with a cell width that produces several observations per cell. If the model has too many holes, either acquire more data, reduce the minimum count with a stated limitation, or use a coarser grid. Do not interpret a smaller cell width as improved accuracy.

Robust rejection applies a cell-local median/MAD gate. With fewer than three points, the gate cannot identify an isolated spike. It can also suppress true narrow features. Compare rejection on/off and inspect the point cloud before treating a median surface as seabed. No ground-classification algorithm is included.

Contour interval controls diagram density. Very small intervals over a large height range are rejected at 100 levels. A contour is derived from the gridded model, not an independent observation.

## Live point capture

Start the service with `--udp-port 53200`. The default packet frame is SENSOR_LOCAL. The stream panel shows packets, invalid datagrams, sequence gaps and buffered points. Choose Capture buffered points when ready to build a snapshot. Old points are overwritten when the bounded ring fills; this is reported. The service does not save every datagram to disk or continuously fuse a moving survey.

Only declare `--udp-frame MAP_ENU` when the sender already supplies registered ENU positions. The bundled `udp-demo` sender uses synthetic ENU positions and is intended to test that explicit mode. To use external poses on received sensor data in this version, export the captured sensor-local points and process them with the offline pose-registration command; live trajectory fusion is not implemented.

UDP source identity is not authenticated. Use a trusted local integration network and do not expose the receiver to the public internet. The tools do not send sensor-control or laser-enable commands.

## Exports and interpretation

Export survey bundle downloads a ZIP containing numerical grids, full accepted points, contours, terrain image and metadata. PNG in the viewer downloads only the current canvas view. Preserve metadata with every measurement product. Use the archive's numerical files for analysis, not a screenshot or the browser's decimated display points.

All outputs are local coordinates until you supply and validate an external reference. Do not import metre ENU values as latitude/longitude. Review datum and frame before using them in GIS. ASCII rasters can be loaded by GIS software once the correct frame is assigned externally.

## Troubleshooting

| Symptom | Action |
|---|---|
| No cells meet minimum count | Increase cell size or reduce minimum count; inspect actual point density |
| Grid exceeds cell limit | Coarsen cells, crop input externally or split the survey into bounded areas |
| Too many contour levels | Increase contour interval |
| Pose gap / outside time span | Supply correctly timed poses; do not extrapolate a vehicle path |
| Surface absent for a scan line | Use point-cloud inspection; acquire a second spatial dimension and valid registration |
| NWP1 CRC/version error | Check the sender's exact packet contract; other LiDAR vendors are not automatically compatible |
| WebGL unavailable | Use Relief/Coverage views in a compatible browser; 3D needs WebGL |
| Port already in use | Choose `--port 8767` or another free local port |
| Invalid file schema | Check required x/y/z columns, units, JSONL line format and ASCII PLY header |

## Operational limits

Source checkout, Python >=3.10, a local single-user process, bounded memory, no persistent project database, no authenticated cloud hosting. Stop with Ctrl+C. Saved archives persist after the process exits; in-memory imports and packet buffers do not.
