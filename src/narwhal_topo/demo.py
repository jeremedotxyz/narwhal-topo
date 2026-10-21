"""Synthetic ENU survey; geometry/noise are illustrative, never measurements."""
import math,random
from .model import Point

def terrain(x,y):
    return -15+1.0*math.sin(x*.13)*math.cos(y*.12)+3.8*math.exp(-((x-12)**2/40+(y-5)**2/25))-2.6*math.exp(-((y+7-.15*x)**2/6))+.025*x

def survey(seed=532):
    rng=random.Random(seed);points=[]
    for j in range(160):
        for i in range(240):
            x=-30+(i+.5)*.25+rng.uniform(-.045,.045);y=-20+(j+.5)*.25+rng.uniform(-.045,.045)
            z=terrain(x,y)+rng.gauss(0,.025)
            if rng.random()<.008:z+=rng.choice([-1,1])*rng.uniform(1,3)
            # Deliberate unsurveyed strip demonstrates holes, not invented terrain.
            if -2<x<1 and y>7:continue
            points.append(Point(x,y,z,rng.randint(700,3000),round((j*240+i)/20000*1e9),32|16,j))
    return points
