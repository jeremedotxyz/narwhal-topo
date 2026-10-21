# Engineering roadmap

| Phase | Deliverables | Required evidence |
|---|---|---|
| Reference software | Input adapters, observed-cell model, diagrams, snapshots, exports and tests | This repository, numerical experiment and CI |
| Sensor adapter | Real ADC/FPGA/CPU output contract, calibrated rays/range, health/status, time epoch | Captured hardware packets, replay fixtures and calibrated timing |
| Navigation | Measured extrinsics, clock offset/drift, sensor trajectory and uncertainty | Control targets and independent survey comparisons |
| Map metrology | Error propagation, correlation model, calibrated uncertainties and datum realization | Measured residuals, coverage, bias and uncertainty consistency |
| Acquisition recorder | Durable raw and point streams, restart/replay, sequence recovery and bounded tiling | Long-duration soak tests and data-loss accounting |
| GIS interoperability | LAS/LAZ/GeoTIFF, projected CRS and verified vertical datum | Round-trip reference files and independent GIS inspection |
| Geometric extensions | Topologically stitched contours, arbitrary transects, measured change detection | Known geometry fixtures and independent datasets |
| Mapping autonomy | ICP/SLAM only after observability study; loop closure and failure detection | Ground truth trajectories, adverse scenes and bounded drift |
| Deployment | Packaged web assets, project persistence, authentication and controlled remote access | Security review, deployment tests and recovery procedures |

No roadmap item is a claim that an unspecified physical sensor is operational. The present receiver speaks the proposed NWP1 point protocol; laser control, waveform acquisition, pose generation and calibration remain upstream responsibilities.
