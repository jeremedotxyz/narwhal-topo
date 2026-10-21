"""Observed-cell median terrain model; holes stay holes, with no interpolation."""
from collections import defaultdict
from dataclasses import asdict
import math,statistics,time
from .model import MAX_POINTS,MAX_CELLS,REJECT_FLAGS


def contours(grid,interval):
    cols,rows=grid['cols'],grid['rows'];z=grid['z'];step=grid['cell_size'];out=[]
    finite=[v for v in z if v is not None]
    if not finite:return []
    first=math.ceil(min(finite)/interval)*interval
    levels=max(0,math.floor((max(finite)-first)/interval)+1)
    if levels>100:raise ValueError('too many contour levels; increase contour interval')
    for k in range(levels):
        level=first+k*interval;segments=[]
        for j in range(rows-1):
            for i in range(cols-1):
                ids=(j*cols+i,j*cols+i+1,(j+1)*cols+i+1,(j+1)*cols+i)
                values=[z[n] for n in ids]
                if any(v is None for v in values):continue
                corners=((i+.5,j+.5),(i+1.5,j+.5),(i+1.5,j+1.5),(i+.5,j+1.5))
                hits=[]
                for a,b in ((0,1),(1,2),(2,3),(3,0)):
                    za,zb=values[a],values[b]
                    if (za>=level)==(zb>=level):continue
                    f=(level-za)/(zb-za)
                    x=grid['x0']+(corners[a][0]+f*(corners[b][0]-corners[a][0]))*step
                    y=grid['y0']+(corners[a][1]+f*(corners[b][1]-corners[a][1]))*step
                    hits.append([round(x,6),round(y,6)])
                if len(hits)==2:segments.append(hits)
                elif len(hits)==4:
                    # Bilinear-center decision for saddle cases; documented approximation.
                    if (sum(values)/4>=level)==(values[0]>=level):pairs=((0,1),(2,3))
                    else:pairs=((0,3),(1,2))
                    segments.extend([[hits[a],hits[b]] for a,b in pairs])
        if segments:out.append({'level':round(level,6),'segments':segments})
    return out


def build(points,settings,provenance=None):
    started=time.perf_counter();points=list(points)
    if len(points)>MAX_POINTS:raise ValueError('point limit exceeded')
    accepted=[];rejected=0
    for p in points:
        if p.quality&REJECT_FLAGS or not all(math.isfinite(v) for v in (p.x,p.y,p.z,p.intensity)) or p.intensity<settings.min_intensity:
            rejected+=1;continue
        accepted.append(p)
    if not accepted:raise ValueError('no finite, valid points remain after filtering')
    step=settings.cell_size
    x0=math.floor(min(p.x for p in accepted)/step)*step;y0=math.floor(min(p.y for p in accepted)/step)*step
    cols=math.floor((max(p.x for p in accepted)-x0)/step)+1;rows=math.floor((max(p.y for p in accepted)-y0)/step)+1
    if cols*rows>MAX_CELLS:raise ValueError(f'grid has {cols*rows:,} cells; increase cell size (limit {MAX_CELLS:,})')
    buckets=defaultdict(list)
    for p in accepted:
        i=math.floor((p.x-x0)/step);j=math.floor((p.y-y0)/step);buckets[j*cols+i].append(p)
    size=cols*rows
    z=[None]*size;count=[0]*size;spread=[None]*size;proxy=[None]*size;intensity=[None]*size;inliers=[];outliers=0
    for cell,batch in buckets.items():
        values=[p.z for p in batch];med=statistics.median(values);mad=statistics.median(abs(v-med) for v in values)
        threshold=max(.12,4.5*1.4826*mad)
        selected=[p for p in batch if not settings.robust or len(batch)<3 or abs(p.z-med)<=threshold]
        outliers+=len(batch)-len(selected);inliers.extend(selected);count[cell]=len(selected)
        if len(selected)<settings.min_points:continue
        values=[p.z for p in selected];z[cell]=statistics.median(values)
        spread[cell]=statistics.stdev(values) if len(values)>1 else 0.0
        robust_sigma=1.4826*statistics.median(abs(v-z[cell]) for v in values)
        proxy[cell]=math.hypot(robust_sigma/math.sqrt(len(values)),settings.vertical_floor_m)
        intensity[cell]=statistics.mean(p.intensity for p in selected)
    heights=[v for v in z if v is not None]
    if not heights:raise ValueError('no cells meet minimum count; reduce minimum points or increase cell size')
    slope=[None]*size
    for j in range(1,rows-1):
        for i in range(1,cols-1):
            n=j*cols+i
            if z[n] is None or any(z[k] is None for k in (n-1,n+1,n-cols,n+cols)):continue
            dx=(z[n+1]-z[n-1])/(2*step);dy=(z[n+cols]-z[n-cols])/(2*step)
            slope[n]=math.degrees(math.atan(math.hypot(dx,dy)))
    grid={'cols':cols,'rows':rows,'x0':x0,'y0':y0,'cell_size':step,'z':z,'count':count,'spread':spread,'uncertainty_proxy':proxy,'intensity':intensity,'slope':slope}
    linework=contours(grid,settings.contour_interval)
    stride=max(1,math.ceil(len(inliers)/60000));shown=inliers[::stride]
    stats={'input_points':len(points),'accepted_points':len(inliers),'rejected_flags_or_nonfinite':rejected,'robust_outliers':outliers,'display_points':len(shown),
           'valid_cells':len(heights),'total_cells':size,'coverage':len(heights)/size,'observed_area_m2':len(heights)*step*step,
           'z_min':min(heights),'z_max':max(heights),'z_mean':statistics.mean(heights),'cell_size_m':step,
           'synthetic_points':sum(bool(p.quality&32) for p in inliers),'unsynced_points':sum(bool(p.quality&16) for p in inliers),
           'build_ms':round((time.perf_counter()-started)*1000,1)}
    meta={'schema_version':1,'software':'narwhal-topo/0.1.0','frame':settings.frame,'units':'metres','datum':'user-declared; not independently verified',
          'provenance':provenance or {},'settings':asdict(settings),'surface_method':'per-cell median; no gap filling','uncertainty':'sampling proxy, not total propagated survey uncertainty',
          'mapping_status':'sensor-local visualization only' if settings.frame=='SENSOR_LOCAL' else 'registered input assumed; validation against control required'}
    product={'metadata':meta,'stats':stats,'grid':grid,'contours':linework,'points':[[p.x,p.y,p.z,p.intensity] for p in shown]}
    return product,inliers
