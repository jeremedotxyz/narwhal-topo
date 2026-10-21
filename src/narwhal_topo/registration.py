"""Quaternion interpolation and rigid transforms. No SLAM or navigation inference."""
import bisect,csv,io,math
from dataclasses import dataclass
from .model import Point

@dataclass(frozen=True)
class Pose:
    t:int
    position:tuple
    q:tuple # x,y,z,w, body to map

def normalized(q):
    if len(q)!=4 or not all(math.isfinite(v) for v in q):raise ValueError('invalid quaternion')
    n=math.sqrt(sum(v*v for v in q))
    if n<1e-12:raise ValueError('zero quaternion')
    return tuple(v/n for v in q)

def rotate(q,p):
    q=normalized(q);x,y,z,w=q
    tx=2*(y*p[2]-z*p[1]);ty=2*(z*p[0]-x*p[2]);tz=2*(x*p[1]-y*p[0])
    return (p[0]+w*tx+y*tz-z*ty,p[1]+w*ty+z*tx-x*tz,p[2]+w*tz+x*ty-y*tx)

def slerp(a,b,f):
    a=normalized(a);b=normalized(b);dot=sum(x*y for x,y in zip(a,b))
    if dot<0:b=tuple(-v for v in b);dot=-dot
    if dot>.9995:return normalized(tuple(x+f*(y-x) for x,y in zip(a,b)))
    theta=math.acos(max(-1,min(1,dot)));s=math.sin(theta)
    return tuple((math.sin((1-f)*theta)*x+math.sin(f*theta)*y)/s for x,y in zip(a,b))

class Trajectory:
    def __init__(self,poses):
        self.poses=list(poses);self.times=[p.t for p in self.poses]
        if not self.poses or any(b<=a for a,b in zip(self.times,self.times[1:])):raise ValueError('poses must be nonempty and strictly time ordered')
        for p in self.poses:
            if p.t<0 or not all(math.isfinite(v) for v in p.position):raise ValueError('invalid pose')
            normalized(p.q)
    @classmethod
    def from_csv(cls,text):
        out=[]
        for row in csv.DictReader(io.StringIO(text)):
            out.append(Pose(int(row['timestamp_ns']),tuple(float(row[k]) for k in ('tx','ty','tz')),normalized(tuple(float(row[k]) for k in ('qx','qy','qz','qw')))))
        return cls(out)
    def at(self,t,max_gap_s):
        i=bisect.bisect_left(self.times,t)
        if i<len(self.times) and self.times[i]==t:return self.poses[i]
        if i==0 or i==len(self.times):raise ValueError('point outside trajectory time span; extrapolation refused')
        a,b=self.poses[i-1],self.poses[i]
        if (b.t-a.t)*1e-9>max_gap_s:raise ValueError('trajectory gap exceeds limit')
        f=(t-a.t)/(b.t-a.t)
        return Pose(t,tuple(x+f*(y-x) for x,y in zip(a.position,b.position)),slerp(a.q,b.q,f))

def register(points,trajectory,max_gap_s=.2,extrinsic_q=(0,0,0,1),extrinsic_t=(0,0,0)):
    if not all(math.isfinite(v) for v in extrinsic_t) or len(extrinsic_t)!=3:raise ValueError('invalid extrinsic translation')
    extrinsic_q=normalized(extrinsic_q)
    out=[]
    for p in points:
        pose=trajectory.at(p.timestamp_ns,max_gap_s)
        local=rotate(extrinsic_q,(p.x,p.y,p.z));body=tuple(local[i]+extrinsic_t[i] for i in range(3))
        world=rotate(pose.q,body);xyz=tuple(world[i]+pose.position[i] for i in range(3))
        out.append(Point(*xyz,p.intensity,p.timestamp_ns,p.quality,p.line_id))
    return out
