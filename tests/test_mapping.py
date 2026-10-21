from dataclasses import replace
from http.server import ThreadingHTTPServer
from pathlib import Path
import io,json,math,socket,struct,threading,time,unittest,urllib.request,urllib.error,zipfile,zlib
from narwhal_topo.model import Point,Settings
from narwhal_topo.mapping import build,contours
from narwhal_topo.registration import Pose,Trajectory,rotate,slerp,register
from narwhal_topo.ingest import parse,decode_nwp1
from narwhal_topo.export import ascii_grid,png,bundle
from narwhal_topo.server import State,handler


def plane():
    return [Point(i+.25,j+.25,i+2*j,100,10) for j in range(4) for i in range(4)]

class TerrainTests(unittest.TestCase):
    def test_known_plane_and_slope(self):
        p,_=build(plane(),Settings(cell_size=1,min_points=1,robust=False,contour_interval=1))
        self.assertEqual(p['grid']['cols'],4);self.assertEqual(p['grid']['z'][5],3)
        self.assertAlmostEqual(p['grid']['slope'][5],math.degrees(math.atan(math.sqrt(5))))
    def test_holes_are_not_filled(self):
        pts=[p for p in plane() if not(p.x==1.25 and p.y==1.25)]
        product,_=build(pts,Settings(cell_size=1,min_points=1,contour_interval=1))
        self.assertIsNone(product['grid']['z'][5]);self.assertIsNone(product['grid']['slope'][6])
        self.assertEqual(product['stats']['valid_cells'],15)
    def test_count_threshold(self):
        pts=[Point(.1,.1,2),Point(.2,.1,2.2),Point(1.1,.1,3)]
        p,_=build(pts,Settings(cell_size=1,min_points=2,contour_interval=1));self.assertEqual(p['grid']['z'],[2.1,None])
    def test_robust_spike(self):
        pts=[Point(.1,.1,z) for z in [1,1.01,.99,1.02,8]]
        p,kept=build(pts,Settings(cell_size=1,min_points=2));self.assertEqual(len(kept),4);self.assertEqual(p['stats']['robust_outliers'],1)
    def test_invalid_returns(self):
        pts=plane()+[Point(math.nan,0,0),Point(0,0,0,quality=1)]
        p,_=build(pts,Settings(cell_size=1,min_points=1));self.assertEqual(p['stats']['rejected_flags_or_nonfinite'],2)
    def test_oversized_grid_rejected(self):
        with self.assertRaises(ValueError):build([Point(0,0,0),Point(10000,10000,1)],Settings(min_points=1))
    def test_contour_locations(self):
        grid={'cols':2,'rows':2,'x0':0,'y0':0,'cell_size':1,'z':[0,1,0,1]}
        line=next(g for g in contours(grid,.5) if g['level']==.5)
        for seg in line['segments']:
            for x,y in seg:self.assertAlmostEqual(x,1)
    def test_contours_do_not_cross_nodata(self):
        self.assertEqual(contours({'cols':2,'rows':2,'x0':0,'y0':0,'cell_size':1,'z':[0,1,None,1]},.5),[])
    def test_invalid_settings(self):
        for kw in [dict(cell_size=0),dict(cell_size=float('nan')),dict(min_points=0),dict(frame='GPS'),dict(robust='yes')]:
            with self.subTest(kw=kw),self.assertRaises(ValueError):Settings(**kw)

class RegistrationTests(unittest.TestCase):
    def test_90degree_rotation(self):
        v=rotate((0,0,math.sqrt(.5),math.sqrt(.5)),(1,0,0));self.assertAlmostEqual(v[0],0);self.assertAlmostEqual(v[1],1)
    def test_pose_interpolation(self):
        t=Trajectory([Pose(0,(0,0,0),(0,0,0,1)),Pose(100_000_000,(2,0,0),(0,0,0,1))]);p=t.at(50_000_000,.2);self.assertEqual(p.position,(1,0,0))
    def test_no_extrapolation_or_long_gap(self):
        t=Trajectory([Pose(0,(0,0,0),(0,0,0,1)),Pose(1_000_000_000,(2,0,0),(0,0,0,1))])
        for time in [-1,500_000_000,2_000_000_000]:
            with self.assertRaises(ValueError):t.at(time,.2)
    def test_antipodal_quaternions(self):self.assertEqual(slerp((0,0,0,1),(0,0,0,-1),.5),(0,0,0,1))
    def test_extrinsic_then_pose(self):
        t=Trajectory([Pose(10,(5,0,0),(0,0,0,1))]);out=register([Point(1,2,3,timestamp_ns=10)],t,extrinsic_t=(0,4,0));self.assertEqual((out[0].x,out[0].y,out[0].z),(6,6,3))
    def test_duplicate_pose_times_rejected(self):
        with self.assertRaises(ValueError):Trajectory([Pose(1,(0,0,0),(0,0,0,1))]*2)

class InputExportTests(unittest.TestCase):
    def test_csv_and_ply(self):
        points,_=parse('x,y,z,intensity\n1,2,3,5\n','csv');self.assertEqual(points[0].z,3)
        pts,_=parse('ply\nformat ascii 1.0\nelement vertex 1\nproperty float x\nproperty float y\nproperty float z\nend_header\n1 2 3\n','ply');self.assertEqual(pts[0].x,1)
    def test_ply_truncation(self):
        with self.assertRaises(ValueError):parse('ply\nformat ascii 1.0\nelement vertex 1\nproperty float x\nproperty float y\nproperty float z\nend_header\n','ply')
    def test_raw_concept_adapter(self):
        e={'schema_version':1,'simulated':True,'time_basis':'SIM_RELATIVE','timestamp_ns':0,'line_id':0,'angle_rad':0,'tof_ns':(5+math.sqrt(25+.06**2))*1.34/299792458*1e9}
        pts,meta=parse(json.dumps(e));self.assertAlmostEqual(pts[0].z,5);self.assertEqual(pts[0].quality,48);self.assertTrue(meta['raw_events'])
    def test_nwp1_crc_and_exact_layout(self):
        data=struct.pack('<4sIHH',b'NWP1',5,1,1)+struct.pack('<QfffffHHIHH',1,1,2,3,4,0,100,48,7,0,0)
        packet=data+struct.pack('<I',zlib.crc32(data));seq,pts=decode_nwp1(packet);self.assertEqual(seq,5);self.assertEqual(pts[0].line_id,7)
        with self.assertRaises(ValueError):decode_nwp1(packet[:-1]+bytes([packet[-1]^1]))
    def test_export_orientation_and_bundle(self):
        p,pts=build(plane(),Settings(cell_size=1,min_points=1,robust=False,contour_interval=1));text=ascii_grid(p).splitlines();self.assertEqual(text[6].split()[0],'6.000000')
        image=png(p);self.assertEqual(image[:8],b'\x89PNG\r\n\x1a\n')
        z=zipfile.ZipFile(io.BytesIO(bundle(p,pts)));self.assertIn('terrain.asc',z.namelist());self.assertEqual(json.loads(z.read('metadata.json'))['metadata']['frame'],'MAP_ENU')

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state=State();cls.server=ThreadingHTTPServer(('127.0.0.1',0),handler(cls.state,Path('web').resolve()));cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.url=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.state.close();cls.thread.join()
    def post(self,path,body,origin=None):
        req=urllib.request.Request(self.url+path,json.dumps(body).encode(),{'Content-Type':'application/json',**({'Origin':origin} if origin else {})})
        return urllib.request.urlopen(req,timeout=10)
    def test_page_and_map_endpoint(self):
        self.assertIn(b'Survey Workbench',urllib.request.urlopen(self.url).read());self.assertGreater(json.load(urllib.request.urlopen(self.url+'/api/map'))['stats']['valid_cells'],0)
    def test_rebuild_and_failed_build_preserves_product(self):
        response=json.load(self.post('/api/rebuild',{'settings':{'cell_size':1,'min_points':2}}));self.assertEqual(response['stats']['cell_size_m'],1)
        with self.assertRaises(urllib.error.HTTPError):self.post('/api/rebuild',{'settings':{'cell_size':0}})
        self.assertEqual(self.state.settings.cell_size,1)
    def test_cross_origin_post_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.post('/api/demo',{},'https://unrelated.invalid')
        self.assertEqual(e.exception.code,403)
    def test_import_and_export_routes(self):
        text='x,y,z\n.1,.1,1\n.2,.1,1.01\n1.1,.1,2\n1.2,.1,2.01\n'
        response=json.load(self.post('/api/import',{'text':text,'format':'csv','settings':{'cell_size':1,'min_points':2},'name':'test.csv'}));self.assertEqual(response['stats']['valid_cells'],2)
        self.assertTrue(urllib.request.urlopen(self.url+'/api/export').read().startswith(b'PK'))
    def test_actual_udp_capture(self):
        state=State('MAP_ENU');state.listen('127.0.0.1',0);port=state.udp_socket.getsockname()[1]
        data=struct.pack('<4sIHH',b'NWP1',0,1,1)+struct.pack('<QfffffHHIHH',1,1,2,3,4,0,100,48,0,0,0);data+=struct.pack('<I',zlib.crc32(data))
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:s.sendto(data,('127.0.0.1',port))
            deadline=time.monotonic()+2
            while not state.ring and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(len(state.ring),1);self.assertEqual(state.live['packets'],1)
        finally:state.close()

if __name__=='__main__':unittest.main()
