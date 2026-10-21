"""Loopback workbench and optional bounded NWP1 receiver. No emission commands."""
from collections import deque
from dataclasses import asdict
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import json,math,mimetypes,socket,threading,time,urllib.parse
from .model import Settings,MAX_POINTS
from .ingest import parse,decode_nwp1
from .mapping import build
from .demo import survey
from .registration import Trajectory,register
from .export import bundle

class State:
    def __init__(self,udp_frame='SENSOR_LOCAL'):
        self.lock=threading.Lock();self.process_lock=threading.Lock();self.raw=survey();self.source={'kind':'synthetic','seed':532,'scene':'60 x 40 m seabed; no physical measurements'}
        self.settings=Settings();self.product,self.points=build(self.raw,self.settings,self.source)
        self.ring=deque(maxlen=MAX_POINTS);self.udp_frame=udp_frame;self.live={'enabled':False,'packets':0,'bad_packets':0,'sequence_gaps':0,'out_of_order_or_duplicate':0,'last_sequence':None,'overwritten_points':0}
        self.stop=threading.Event();self.udp_socket=None
    def listen(self,host,port):
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind((host,port));sock.settimeout(.2);self.udp_socket=sock
        self.live.update(enabled=True,address=f'{host}:{port}',frame=self.udp_frame)
        def loop():
            while not self.stop.is_set():
                try:
                    data,peer=sock.recvfrom(65535);seq,points=decode_nwp1(data)
                    with self.lock:
                        prev=self.live['last_sequence']
                        if prev is not None:
                            d=(seq-prev)%2**32
                            if 1<d<2**31:self.live['sequence_gaps']+=d-1
                            elif d==0 or d>=2**31:self.live['out_of_order_or_duplicate']+=1
                        self.live['last_sequence']=seq;self.live['packets']+=1
                        self.live['overwritten_points']+=max(0,len(self.ring)+len(points)-MAX_POINTS)
                        self.ring.extend(points)
                except socket.timeout:continue
                except ValueError:
                    with self.lock:self.live['bad_packets']+=1
                except OSError:break
        thread=threading.Thread(target=loop,daemon=True);thread.start();return thread
    def close(self):
        self.stop.set()
        if self.udp_socket:self.udp_socket.close()


def handler(state,webroot):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,status,body,kind='application/json'):
            if not isinstance(body,bytes):body=json.dumps(body,allow_nan=False).encode()
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
        def do_GET(self):
            path=urllib.parse.urlsplit(self.path).path
            if path=='/api/map':
                with state.lock:self.send(200,state.product)
            elif path=='/api/live':
                with state.lock:self.send(200,dict(state.live,buffered_points=len(state.ring)))
            elif path=='/api/export':
                with state.lock:data=bundle(state.product,state.points)
                self.send(200,data,'application/zip')
            else:
                files={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
                if path not in files:self.send(404,{'error':'not found'});return
                file=webroot/files[path]
                if not file.is_file():self.send(404,{'error':'web asset unavailable'});return
                self.send(200,file.read_bytes(),mimetypes.guess_type(str(file))[0] or 'text/plain')
        def do_POST(self):
            origin=self.headers.get('Origin')
            if origin and urllib.parse.urlsplit(origin).netloc!=self.headers.get('Host'):
                self.send(403,{'error':'cross-origin requests refused'});return
            if self.headers.get_content_type()!='application/json':self.send(415,{'error':'JSON content type required'});return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=40*1024*1024:raise ValueError('request exceeds allowed size or is empty')
                data=json.loads(self.rfile.read(size));path=urllib.parse.urlsplit(self.path).path
                if not isinstance(data,dict):raise ValueError('request must be an object')
                # Serialize builds; only replace the existing product after a successful build.
                with state.process_lock:
                    settings=Settings(**data.get('settings',asdict(state.settings)))
                    if path=='/api/demo':raw=survey();source={'kind':'synthetic','seed':532,'scene':'60 x 40 m seabed; no physical measurements'};settings=Settings(**dict(asdict(settings),frame='MAP_ENU'))
                    elif path=='/api/import':
                        raw,source=parse(data['text'],data.get('format','jsonl'));source.update(kind='imported',name=Path(data.get('name','points')).name)
                        if source.get('raw_events') and settings.frame=='MAP_ENU':raise ValueError('raw events are sensor-frame; choose SENSOR_LOCAL or provide poses')
                        if settings.frame=='POSE_REGISTERED':
                            trajectory=Trajectory.from_csv(data.get('poses',''))
                            raw=register(raw,trajectory,settings.max_pose_gap_s,tuple(data.get('extrinsic_q',[0,0,0,1])),tuple(data.get('extrinsic_t',[0,0,0])))
                            source['registration']='external trajectory / user supplied extrinsics'
                    elif path=='/api/rebuild':raw=state.raw;source=state.source;settings=Settings(**dict(asdict(settings),frame=state.settings.frame))
                    elif path=='/api/capture':
                        with state.lock:raw=list(state.ring)
                        source={'kind':'NWP1 capture','note':'No receiver calibration negotiation; frame supplied at server startup'}
                        settings=Settings(**dict(asdict(settings),frame=state.udp_frame))
                    else:self.send(404,{'error':'not found'});return
                    product,points=build(raw,settings,source)
                    with state.lock:state.raw=raw;state.settings=settings;state.source=source;state.product=product;state.points=points
                    self.send(200,product)
            except (ValueError,TypeError,KeyError,OverflowError) as e:self.send(400,{'error':str(e)})
    return Handler


def serve(host='127.0.0.1',port=8766,udp_port=None,udp_host='127.0.0.1',udp_frame='SENSOR_LOCAL'):
    state=State(udp_frame);webroot=Path(__file__).resolve().parents[2]/'web'
    if not webroot.is_dir():raise ValueError('run from the source checkout; web/ assets required')
    server=ThreadingHTTPServer((host,port),handler(state,webroot))
    if udp_port:state.listen(udp_host,udp_port)
    print(f'Narwhal Topo: http://{host}:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:state.close();server.server_close()
