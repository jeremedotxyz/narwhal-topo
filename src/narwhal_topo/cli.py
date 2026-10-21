import argparse,json,socket,struct,sys,time,zlib
from dataclasses import asdict
from pathlib import Path
from .model import Settings
from .ingest import parse
from .mapping import build
from .registration import Trajectory,register
from .demo import survey
from .export import bundle
from .server import serve

def main(argv=None):
    parser=argparse.ArgumentParser(description='Narwhal Topo: observed-cell LiDAR mapping and visualization')
    sub=parser.add_subparsers(dest='command',required=True)
    run=sub.add_parser('serve');run.add_argument('--host',default='127.0.0.1');run.add_argument('--port',type=int,default=8766)
    run.add_argument('--udp-port',type=int);run.add_argument('--udp-host',default='127.0.0.1');run.add_argument('--udp-frame',choices=['SENSOR_LOCAL','MAP_ENU'],default='SENSOR_LOCAL')
    batch=sub.add_parser('build');batch.add_argument('input');batch.add_argument('--format',choices=['csv','jsonl','ply']);batch.add_argument('--frame',choices=['MAP_ENU','SENSOR_LOCAL','POSE_REGISTERED'],required=True)
    batch.add_argument('--poses');batch.add_argument('--extrinsics');batch.add_argument('--cell',type=float,default=.5);batch.add_argument('--min-points',type=int,default=2);batch.add_argument('--contours',type=float,default=.5);batch.add_argument('--out',default='runs/survey.zip')
    sample=sub.add_parser('demo');sample.add_argument('--out',default='runs/demo.zip')
    sender=sub.add_parser('udp-demo');sender.add_argument('--host',default='127.0.0.1');sender.add_argument('--port',type=int,default=53200)
    args=parser.parse_args(argv)
    try:
        if args.command=='serve':serve(args.host,args.port,args.udp_port,args.udp_host,args.udp_frame);return 0
        if args.command=='udp-demo':
            pts=survey()
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
                for i in range(0,len(pts),32):
                    chunk=pts[i:i+32];data=struct.pack('<4sIHH',b'NWP1',i//32,len(chunk),1)
                    for p in chunk:data+=struct.pack('<QfffffHHIHH',p.timestamp_ns,p.x,p.y,p.z,max(.1,(p.x*p.x+p.y*p.y+p.z*p.z)**.5),0,int(p.intensity),p.quality,p.line_id,0,0)
                    data+=struct.pack('<I',zlib.crc32(data));sock.sendto(data,(args.host,args.port));time.sleep(.001)
            print(f'Sent {len(pts)} synthetic ENU points; receiver must explicitly use --udp-frame MAP_ENU');return 0
        if args.command=='demo':points=survey();settings=Settings();source={'kind':'synthetic','seed':532}
        else:
            fmt=args.format or Path(args.input).suffix.lstrip('.');points,source=parse(Path(args.input).read_text(),fmt)
            settings=Settings(cell_size=args.cell,min_points=args.min_points,contour_interval=args.contours,frame=args.frame)
            if source.get('raw_events') and args.frame=='MAP_ENU':raise ValueError('raw events require sensor-local frame or external poses')
            if args.frame=='POSE_REGISTERED':
                if not args.poses:raise ValueError('--poses is required for registered mapping')
                ext=json.loads(Path(args.extrinsics).read_text()) if args.extrinsics else {'q':[0,0,0,1],'t':[0,0,0]}
                points=register(points,Trajectory.from_csv(Path(args.poses).read_text()),settings.max_pose_gap_s,ext['q'],ext['t'])
                source['registration']='external sensor trajectory; explicit extrinsics or identity mount'
        product,inliers=build(points,settings,source);out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(bundle(product,inliers))
        print(json.dumps(product['stats'],indent=2));return 0
    except (OSError,ValueError,TypeError,KeyError) as e:print(f'error: {e}',file=sys.stderr);return 2
