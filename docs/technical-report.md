# Narwhal Topo: An Inspectable Pipeline for Underwater LiDAR Terrain Mapping

**Technical report · version 0.1.0 · 21 October 2026**  
**Repository:** [jeremedotxyz/narwhal-topo](https://github.com/jeremedotxyz/narwhal-topo)  
**Status:** implemented software reference with synthetic validation; not a peer-reviewed instrument or hydrographic certification.

## Abstract

Narwhal Topo converts bounded sets of LiDAR point observations into an inspectable terrain model and interactive diagram workbench. Inputs are registered local-coordinate points, sensor-coordinate points accompanied by an external pose trajectory, or sensor-local observations for inspection. The software provides file adapters, a proposed Narwhal NWP1 UDP receiver, validity filtering, quaternion-based registration, observed-cell median gridding, conservative cell-wise spike rejection, slope estimates, contour segments, cross-sections and numerical/graphical exports. A browser interface renders terrain triangles, point clouds, relief maps and observation support. It explicitly preserves unsupported cells rather than fabricating topography. A reproducible analytic seabed experiment examines grid resolution and cell support. The default half-metre model retains 37,511 synthetic returns in 9,444 supported cells and yields approximately 0.0192 m cell-center RMSE under the chosen noise and sampling assumptions. This does not establish physical sensor accuracy. Twenty-five unit and integration tests cover numerical geometry, input contracts, missing data, packet integrity, HTTP state and real loopback UDP reception. Remaining work includes calibrated sensor/navigation integration, propagated survey uncertainty, durable acquisition and GIS-specific adapters.

## 1. Motivation and scope

A LiDAR receiver produces observations, not a complete geographic map. A useful mapping system must establish what each observation measures, where the instrument was located, how the instrument was oriented, which returns are valid, and which spatial regions actually have evidence. A high-detail display should make these dependencies visible rather than mask them with smooth interpolation.

The purpose of this implementation is a local engineering tool that can be run, inspected, tested and extended. It supports the point records proposed by [Narwhal Two Plus](https://github.com/jeremedotxyz/narwhal-two-plus), but it does not make that concept into a physical instrument. Actual acquisition electronics, optical calibration and navigation remain separate responsibilities. The present repository supplies a receiver and offline processing path, not a laser driver or FPGA acquisition firmware.

The scientific evidence in this report consists of source-visible algorithms, deterministic synthetic experiments and software tests. No measured ocean survey, independent control network, calibrated sensor characterization or hydrographic acceptance trial is included. The workbench's reference scene is labeled synthetic in the interface, exports and reproduction results.

## 2. System architecture

The pipeline is input → validation → coordinate registration or explicit frame declaration → point filtering → grid construction → terrain/support diagnostics → diagrams and exports. The browser requests candidate products from a local HTTP service. Numerical processing occurs on the service; the browser performs visualization and interaction. An optional UDP thread buffers point records for a user-triggered reconstruction snapshot.

Three coordinate modes are intentionally separate. `MAP_ENU` accepts points already located in a metre-based east, north, up frame. `POSE_REGISTERED` accepts sensor points and a time-aligned external sensor trajectory. `SENSOR_LOCAL` permits inspection when no map registration is available. In sensor-local mode, the concept sensor's Z coordinate is forward distance and must not be interpreted as elevation or bathymetric depth. A single fan scan can be essentially one-dimensional and cannot alone support a two-dimensional terrain surface.

The service uses standard Python only. The frontend uses WebGL 1 and Canvas 2D without a framework or external asset service. This keeps the executable reference small, offline-capable after checkout and auditable. It also makes the limitations clear: the system is an in-memory local workbench rather than a production geospatial platform.

## 3. Inputs and measurement interpretation

### 3.1 Point files

CSV and JSONL records supply X, Y, Z and optional intensity, timestamp, quality and line ID. ASCII PLY 1.0 is supported for vertex positions and optional intensity. Distances must be metres. Point coordinates are not automatically inferred to be longitude/latitude or any projected EPSG system. Missing timestamps default to zero; absence of an explicit unsynchronized flag is not evidence that the source clock was independently checked.

The importer rejects malformed schemas and invalid integer ranges. Nonfinite positions/intensity and defined invalid-return flags are removed before gridding. Saturation is not automatically a positional rejection in this version; its meaning must be assessed against the source estimator. Intensity is an uncalibrated count unless the sender establishes an independent radiometric interpretation.

### 3.2 Narwhal raw event adapter

The optional raw JSONL adapter accepts version-1 concept ToF events from Narwhal Two Plus. It uses the fixed external-ray model of that concept: vacuum light speed 299,792,458 m/s, group index 1.34, vertical baseline 0.06 m, zero system-delay offset and a +/-15 degree water-side scan. The corresponding bistatic range is solved before point construction. Raw events must be explicitly marked simulated or nonsimulated, and synchronized versus relative time is retained in flags.

This adapter is a compatibility demonstration, not a general calibration solution. It has no UI controls for refractive-index gradients, port geometry, per-angle timing correction or instrument thermal calibration. A real instrument should deliver calibrated point records or replace the adapter with a validated calibrated model. Raw events cannot be declared already ENU by the importer.

### 3.3 Packet stream

NWP1 packets use the exact proposed Narwhal 40-byte point record, a versioned 12-byte header and a four-byte CRC. The decoder validates magic, version, point count, total length, reserved record bytes, coordinate validity and CRC. Valid points require finite positions and positive finite range. Invalid-return records require NaN position/range fields. Packet sequence diagnostics distinguish missing forward values from duplicate/out-of-order arrivals.

The stream has no sender authentication, retransmission, discovery, calibration negotiation or time synchronization. A correct CRC proves only that the received byte pattern matches its checksum, not that measurements are accurate or a sender is trusted. Frame is explicitly declared at receiver startup. The default is sensor local. A 300,000-point ring buffer is bounded and counts overwritten points; it is not a lossless mission recorder.

## 4. Registration mathematics

Let p_s be a sensor-coordinate point, R_bs and t_bs an optional sensor-to-body mounting transform, and R_mb(t), t_mb(t) the body-to-map pose at acquisition time. The implemented transformation is:

```math
p_m = R_{mb}(t)\,[R_{bs}p_s+t_{bs}]+t_{mb}(t).
```

When the trajectory directly describes the sensor origin and orientation in ENU, the mounting transform is identity. This is the browser import convention. The CLI accepts an explicit mounting JSON for body-frame trajectories. The quaternion must map the supplied local axes into the pose's parent frame; no implicit FRD-to-ENU rotation is inserted.

Pose rows must be strictly increasing in nanosecond timestamp. Translation is interpolated linearly. Orientation is interpolated using normalized shortest-arc quaternion SLERP, with normalized linear interpolation for nearly identical quaternions. Antipodal quaternions are treated as the same orientation by flipping one sign. Zero or nonfinite quaternion inputs are rejected.

Interpolation does not extrapolate beyond the trajectory span. The default maximum interval between bracketing poses is 0.2 seconds. Pose and point time bases must already be aligned. The code does not estimate latency, clock drift or navigation bias. These constraints are tested independently of the synthetic terrain scene.

## 5. Surface reconstruction

### 5.1 Grid geometry and evidence support

For cell width h, the lower-left corner is aligned by flooring the minimum accepted coordinate to a multiple of h. A point at (x,y) belongs to integer cell:

```math
i=\lfloor(x-x_0)/h\rfloor,\qquad j=\lfloor(y-y_0)/h\rfloor.
```

Internal row index increases northward. The represented terrain value lies at the cell center, not at the original point coordinates. A grid's resolution is a bin size, not sensor precision, effective optical footprint or independent spatial resolving power. Finer bins cannot recover unsampled detail.

A supported cell needs at least the configured minimum number of retained returns. Unsupported cells are `null` internally, transparent in the terrain PNG and -9999 in the ASCII raster. No interpolation, inverse-distance expansion, inpainting or gap filling is applied. Contour and mesh construction require supported neighbors and therefore do not bridge those gaps.

The supplied synthetic scene intentionally omits a strip of observations. That strip remains absent from the output. The valid-cell fraction is computed against the rectangular grid footprint; observed area is valid cell count times h². Neither is a convex-hull area or a geographic survey-boundary estimate.

### 5.2 Robust cell aggregation

For each populated cell, let m be the median elevation and MAD the median of |z−m|. When robust rejection is enabled and a cell has at least three observations, the gate is:

```math
|z-m| \le \max(0.12\;\mathrm{m},\;4.5\times1.4826\times MAD).
```

The 0.12 m absolute floor is a conservative reference setting, not a sensor-derived tolerance. It reduces rejection of genuine within-cell terrain variation at the default sample scale, but is not guaranteed suitable for every slope or target. Fewer than three observations bypass this gate because cell-wise evidence is insufficient for meaningful robust spike classification.

After rejection, the cell's terrain value is the median of retained elevations. The model also records retained count, sample standard deviation, mean intensity and a sampling proxy. Filtering is cell-local. It is not seabed classification, multipath discrimination, an object detector or a full statistical neighborhood filter. Real narrow features can be removed or smoothed; disabling rejection and inspecting raw returns is therefore an important diagnostic.

### 5.3 Slope and contours

Interior slopes use central finite differences in east/north directions where the center and four axial neighbors all have terrain values. The slope angle is atan(sqrt((dz/dx)²+(dz/dy)²)), expressed in degrees. Unsupported neighborhoods have no slope estimate.

Contour segments use marching-squares edge interpolation on four supported cell centers. Ambiguous saddle cases are paired by a bilinear-center decision. This is a documented local approximation; the output is a set of segments, not a topologically stitched polygon network. There are no contours across NoData quads. A maximum of 100 contour levels prevents unbounded output from an excessively small interval over a large Z range.

## 6. Uncertainty and accuracy language

The diagnostic labeled sampling uncertainty proxy is:

```math
u_{proxy}=\sqrt{(1.4826\,MAD/\sqrt{n})^2+u_{floor}^2}.
```

MAD is recomputed around the retained cell median. The default floor is 0.02 m. This quantity describes a rough sampling-spread diagnostic; it is not a statistically calibrated confidence interval for a median and is not total propagated uncertainty. Returns can be spatially correlated, cells can include real slope, and a robust MAD can be zero even when systematic bias is large.

Total map uncertainty additionally depends on range estimation, refraction/port correction, pose orientation/position, time alignment, mounting calibration, datum realization and interpolation/model error. None of those terms are propagated here. The UI and metadata identify the value as a proxy and require independent control before a physical accuracy claim.

Negative ENU Z is an elevation relative to a user-established zero. It is not automatically positive water depth, chart datum depth, tidal correction or a safe-navigation surface. No navigational use or safety certification is asserted.

## 7. Visualization and diagrams

The 3D surface connects neighboring supported grid centers with two triangles per quad. The point-cloud view instead displays accepted returns, preserving their shape rather than displaying grid medians. The browser caps only the cloud display at 60,000 points using a deterministic stride. All accepted points participate in numerical processing and exports. Large scenes can therefore be visually decimated without changing the analysis, and the display count is shown explicitly.

A perspective camera supports orbit, zoom, reset and visual vertical exaggeration. Exaggeration changes only the view matrix. Color attributes select elevation, mean return intensity, retained count or the sampling proxy. Relief-map shading is an illustrative slope-based contrast, not a physical illumination/radiance model. The reference is not a photorealistic reconstruction.

Plan views are north-up in declared map coordinates. Clicking a cell reports center coordinates and its evidence support. The cross-section selects a discrete grid row; paths break at missing values. It is not a freely interpolated arbitrary transect. Screenshots show a graphical view, while the survey bundle retains numerical results and provenance.

## 8. Reproducible experiment

The seed-532 reference scene covers a local 60 by 40 m region. It contains a smooth undulating seabed, an elevated mound, a diagonal depression, independent Gaussian elevation noise (standard deviation 0.025 m), occasional synthetic spikes and an intentionally unsampled strip. Approximately 0.25 m sample spacing gives 37,776 input observations after omitting that strip. There is no real optical propagation, pose noise, beam divergence, multipath, backscatter or terrain occlusion model.

The reproduction script builds 0.25, 0.5 and 1.0 m grids. The finest grid permits one observation per cell; coarser grids require two. Each cell median is compared to analytic surface truth at the cell center. The default 0.5 m configuration retains 37,511 observations, rejects 265 cell-wise spikes, supports 9,444 of 9,600 cells, and gives 0.019236 m center-based RMSE in the committed run. The 0.25 m model gives 0.173238 m RMSE because one-point cells provide no basis for identifying the isolated spikes. The 1.0 m case gives 0.014375 m RMSE while aggregating over a larger footprint.

These comparisons demonstrate how support and aggregation affect this chosen scene. They do not prove that larger cells always improve a real map, nor that the sensor attains centimetric accuracy. The truth is known to the generator and the observations omit many physical error sources. See [exact results and assumptions](../examples/reference-results.md).

## 9. Software verification

Twenty-five tests cover a known plane and its analytic slope, NoData preservation, count thresholds, spike rejection, invalid returns, grid bounds, known contour locations, contours near holes, configuration validation, 90-degree rotation, translation interpolation, antipodal quaternions, mounting transform order, pose time constraints, CSV/PLY parsing and truncation, raw-event ranging, independent NWP1 byte construction and CRC corruption, export row orientation, archive contents, HTTP endpoints, failed-build product preservation, cross-origin rejection and actual UDP receipt over a loopback socket.

The tests establish properties of this implementation. They do not validate the fixed concept calibration against an instrument. Browser checks additionally exercise the actual controls and rendered views; those checks are recorded separately from automated numerical tests. GitHub Actions runs the reference checks on Python 3.10 and 3.12.

## 10. Limits and next engineering work

The current implementation is bounded to 300,000 input points and 250,000 cells, with 32 MiB point text and at most 100 contour levels. Data processing is in memory; long-running missions require durable packet/raw-waveform capture and tiled reconstruction. The UI is a single local workspace, without project persistence, authenticated users or a cloud deployment model.

Planned extensions are calibrated sensor adapters, trajectory/extrinsic provenance, full uncertainty propagation, independently surveyed control, LAS/LAZ and GeoTIFF adapters, explicit projected CRS/datum support, contour stitching, registration diagnostics and hardware-in-the-loop trials. Automatic SLAM or ICP would require a separate observability study and validation dataset. Neither is silently assumed here.

## References and provenance

1. [Narwhal Two Plus reference design and proposed point protocol](https://github.com/jeremedotxyz/narwhal-two-plus). Upstream concept data contract; not measured sensor performance.
2. [PDAL `writers.gdal` documentation](https://pdal.io/en/stable/stages/writers.gdal.html). Background for point-to-raster products, resolution and missing-value handling. Narwhal Topo implements its own narrower median-cell method and does not depend on PDAL.
3. [Khronos WebGL 1.0 specification, version 1.0.3](https://registry.khronos.org/webgl/specs/1.0.3/). Rendering API basis for the browser workbench.

Prepared with AI-assisted implementation and documentation. All numerical results here are produced by this repository's analytic/synthetic experiment. No external institution, journal review, physical trial or independent certification is implied.
