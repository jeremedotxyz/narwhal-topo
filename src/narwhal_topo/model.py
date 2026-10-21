from dataclasses import dataclass
import math

MAX_POINTS=300_000
MAX_CELLS=250_000
REJECT_FLAGS=1|2|8

@dataclass(frozen=True)
class Point:
    x:float
    y:float
    z:float
    intensity:float=0.0
    timestamp_ns:int=0
    quality:int=0
    line_id:int=0

@dataclass(frozen=True)
class Settings:
    cell_size:float=0.5
    min_points:int=2
    min_intensity:float=0.0
    robust:bool=True
    contour_interval:float=0.5
    frame:str='MAP_ENU'
    max_pose_gap_s:float=0.2
    vertical_floor_m:float=0.02
    def __post_init__(self):
        for n in ('cell_size','min_intensity','contour_interval','max_pose_gap_s','vertical_floor_m'):
            if not math.isfinite(getattr(self,n)):raise ValueError(n+' must be finite')
        if not 0.05<=self.cell_size<=20:raise ValueError('cell size must be 0.05-20 m')
        if type(self.min_points) is not int or not 1<=self.min_points<=100:raise ValueError('minimum count must be 1-100')
        if self.min_intensity<0 or self.contour_interval<=0 or self.max_pose_gap_s<=0 or self.vertical_floor_m<0:raise ValueError('invalid thresholds')
        if self.frame not in ('MAP_ENU','SENSOR_LOCAL','POSE_REGISTERED'):raise ValueError('invalid coordinate frame')
        if type(self.robust) is not bool:raise ValueError('robust must be boolean')
