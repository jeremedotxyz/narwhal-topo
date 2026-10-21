"""Portable numerical/diagram exports; local coordinates are not WGS84 GeoJSON."""
import csv,io,json,math,struct,zlib,zipfile
from html import escape

def ramp(t):
    stops=[(12,49,76),(22,103,139),(42,167,172),(126,206,172),(237,214,137),(244,132,79)]
    f=max(0,min(1,t))*(len(stops)-1);i=min(len(stops)-2,int(f));a=f-i
    return tuple(round(stops[i][k]*(1-a)+stops[i+1][k]*a) for k in range(3))

def png(product):
    g=product['grid'];lo=product['stats']['z_min'];hi=product['stats']['z_max'];rows=[]
    for j in range(g['rows']-1,-1,-1):
        row=bytearray([0])
        for i in range(g['cols']):
            n=j*g['cols']+i;v=g['z'][n]
            row.extend((*ramp((v-lo)/(hi-lo or 1)),255) if v is not None else (0,0,0,0))
        rows.append(bytes(row))
    def chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',g['cols'],g['rows'],8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b'')

def ascii_grid(product):
    g=product['grid'];header=f"ncols {g['cols']}\nnrows {g['rows']}\nxllcorner {g['x0']}\nyllcorner {g['y0']}\ncellsize {g['cell_size']}\nNODATA_value -9999\n"
    return header+''.join(' '.join('-9999' if v is None else f'{v:.6f}' for v in g['z'][j*g['cols']:(j+1)*g['cols']])+'\n' for j in range(g['rows']-1,-1,-1))

def point_csv(points):
    out=io.StringIO();w=csv.writer(out);w.writerow(['x','y','z','intensity','timestamp_ns','quality','line_id'])
    w.writerows((p.x,p.y,p.z,p.intensity,str(p.timestamp_ns),p.quality,p.line_id) for p in points);return out.getvalue()

def ply(points):
    return f'ply\nformat ascii 1.0\ncomment Narwhal Topo; see metadata.json for frame and provenance\nelement vertex {len(points)}\nproperty double x\nproperty double y\nproperty double z\nproperty float intensity\nend_header\n'+''.join(f'{p.x:.8f} {p.y:.8f} {p.z:.8f} {p.intensity:.2f}\n' for p in points)

def svg(product):
    g=product['grid'];w=g['cols']*g['cell_size'];h=g['rows']*g['cell_size'];scale=1000/w
    paths=[]
    for group in product['contours']:
        d=' '.join(f'M{(a[0]-g["x0"])*scale:.3f},{(g["y0"]+h-a[1])*scale:.3f} L{(b[0]-g["x0"])*scale:.3f},{(g["y0"]+h-b[1])*scale:.3f}' for a,b in group['segments'])
        paths.append(f'<path d="{d}"><title>Elevation {group["level"]} m</title></path>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 {h*scale:.3f}"><title>Narwhal Topo local contour map</title><desc>Frame {escape(product["metadata"]["frame"])}; metres; no geographic CRS assigned.</desc><rect width="100%" height="100%" fill="#0b1926"/><g fill="none" stroke="#81d8c4" stroke-width="0.8">'+''.join(paths)+'</g></svg>'

def bundle(product,points):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in [('metadata.json',json.dumps({'metadata':product['metadata'],'stats':product['stats']},indent=2)),('grid.json',json.dumps(product['grid'])),('terrain.asc',ascii_grid(product)),('terrain.png',png(product)),('contours.svg',svg(product)),('contours-local.json',json.dumps({'coordinate_frame':product['metadata']['frame'],'units':'metres','contours':product['contours']})),('points.csv',point_csv(points)),('points.ply',ply(points))]:z.writestr(name,data)
        z.writestr('README.txt','Narwhal Topo export. Read metadata.json before using coordinates. PNG has north up. ASC rows run north to south. Contours are local metre coordinates, not WGS84 GeoJSON. Uncertainty is a sampling proxy; no survey certification.\n')
    return out.getvalue()
