"""Strict bounded input adapters; original point provenance survives filtering."""
import csv,io,json,math,struct,zlib
from .model import Point,MAX_POINTS,REJECT_FLAGS

WIRE=struct.Struct('<QfffffHHIHH')

def numeric(v,name):
    try:return float(v)
    except (ValueError,TypeError):raise ValueError('invalid '+name)

def point(row):
    q=int(row.get('quality') or 0);t=int(row.get('timestamp_ns') or 0);lid=int(row.get('line_id') or 0)
    if not 0<=q<=65535 or not 0<=t<2**64 or not 0<=lid<2**32:raise ValueError('point integer field outside wire range')
    xyz=tuple(numeric(row[k],k) if row.get(k) is not None and row.get(k)!='' else math.nan for k in ('x','y','z'))
    intensity=numeric(row.get('intensity') or 0,'intensity')
    return Point(*xyz,intensity,t,q,lid)

def raw_to_point(row):
    # Same external-ray homogeneous-water geometry as narwhal-two-plus v0.1.0.
    q=(32 if row.get('simulated') is True else 0)|(0 if row.get('time_basis')=='TAI' else 16)
    if row.get('schema_version')!=1 or type(row.get('simulated')) is not bool:raise ValueError('raw event needs schema_version=1 and explicit simulated boolean')
    a=numeric(row['angle_rad'],'angle');t=int(row['timestamp_ns']);lid=int(row['line_id']);intensity=numeric(row.get('intensity') or 0,'intensity')
    if not math.isfinite(a) or abs(a)>math.pi/12+1e-9:raise ValueError('raw angle outside concept +/-15 degree calibration')
    delay=row.get('tof_ns')
    r=math.nan
    if delay is None:q|=1
    else:
        length=299792458*numeric(delay,'delay')*1e-9/1.34
        if not math.isfinite(length) or length<=.06:q|=8
        else:
            r=(length*length-.06**2)/(2*length)
            if not 1<=r<=15:r=math.nan;q|=2
    return point(dict(x=r*math.sin(a),y=-.03 if math.isfinite(r) else math.nan,z=r*math.cos(a),intensity=intensity,timestamp_ns=t,quality=q,line_id=lid))

def parse(text,fmt='jsonl'):
    points=[]
    if len(text.encode('utf8'))>32*1024*1024:raise ValueError('input exceeds 32 MiB')
    if fmt=='csv':rows=csv.DictReader(io.StringIO(text))
    elif fmt=='jsonl':rows=(json.loads(s) for s in text.splitlines() if s.strip())
    elif fmt=='ply':return parse_ply(text)
    else:raise ValueError('supported input formats: csv, jsonl, ply')
    raw=False
    for row in rows:
        if len(points)>=MAX_POINTS:raise ValueError('point limit exceeded')
        if not isinstance(row,dict):raise ValueError('record must be an object')
        israw='tof_ns' in row;raw=raw or israw
        points.append(raw_to_point(row) if israw else point(row))
    if not points:raise ValueError('no point records found')
    return points,{'format':fmt,'raw_events':raw,'raw_calibration':'concept-A-20261021 fixed ng=1.34 / 60 mm baseline / zero system delay' if raw else None}

def parse_ply(text):
    stream=io.StringIO(text)
    if stream.readline().strip()!='ply' or stream.readline().strip()!='format ascii 1.0':raise ValueError('only ASCII PLY 1.0 is supported')
    props=[];count=None;in_vertex=False
    for line in stream:
        bits=line.split()
        if bits[:2]==['element','vertex']:
            count=int(bits[2]);in_vertex=True
        elif bits[:1]==['element']:in_vertex=False
        elif bits[:1]==['property'] and in_vertex:
            if len(bits)!=3:raise ValueError('list properties not supported for vertices')
            props.append(bits[2])
        elif bits[:1]==['end_header']:break
    else:raise ValueError('missing PLY header terminator')
    if count is None or not 0<count<=MAX_POINTS or not all(k in props for k in ('x','y','z')):raise ValueError('invalid PLY vertex declaration')
    result=[]
    for _ in range(count):
        bits=stream.readline().split()
        if len(bits)!=len(props):raise ValueError('truncated or malformed PLY vertex')
        result.append(point(dict(zip(props,bits))))
    return result,{'format':'ply','raw_events':False}

def decode_nwp1(data):
    if len(data)<56:raise ValueError('short NWP1 datagram')
    magic,seq,count,version=struct.unpack_from('<4sIHH',data)
    if magic!=b'NWP1' or version!=1 or not 1<=count<=32 or len(data)!=16+count*40:raise ValueError('invalid NWP1 header')
    if zlib.crc32(data[:-4])!=struct.unpack('<I',data[-4:])[0]:raise ValueError('NWP1 CRC mismatch')
    result=[]
    for i in range(count):
        t,x,y,z,r,a,intensity,q,lid,status,reserved=WIRE.unpack_from(data,12+i*40)
        if reserved:raise ValueError('NWP1 reserved bytes nonzero')
        if not math.isfinite(a):raise ValueError('NWP1 angle must be finite')
        valid=not(q&REJECT_FLAGS)
        if valid and (not all(math.isfinite(v) for v in (x,y,z,r)) or r<=0):raise ValueError('invalid valid NWP1 point')
        if not valid and not all(math.isnan(v) for v in (x,y,z,r)):raise ValueError('invalid NWP1 point must use NaN')
        result.append(Point(x,y,z,intensity,t,q,lid))
    return seq,result
