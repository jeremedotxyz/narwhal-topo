"""Draw the share card from the actual seeded mapping product.

Run from the checkout: PYTHONPATH=src python scripts/generate_social_preview.py
Only artwork regeneration needs Pillow (python -m pip install Pillow).
The application itself has no third-party runtime dependencies.
Outputs: editable SVG and GitHub-ready 1280 x 640 PNG.
"""
from html import escape
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont
from narwhal_topo.demo import survey
from narwhal_topo.mapping import build
from narwhal_topo.model import Settings

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'assets'
OUT.mkdir(parents=True, exist_ok=True)
W, H, SCALE = 1280, 640, 3
BG, INK, DIM, ACC, GRID = '#09233D', '#DCECF6', '#83B7D2', '#6DE1DE', '#17334C'
image = Image.new('RGB', (W*SCALE, H*SCALE), BG)
draw = ImageDraw.Draw(image)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
       '<title>Narwhal Topo / Underwater LiDAR mapping workbench</title>',
       '<desc>Actual synthetic reference reconstruction: isometric observed terrain, half-metre contours, and a northing cross-section. No physical survey accuracy is claimed.</desc>',
       f'<rect width="{W}" height="{H}" fill="{BG}"/>']

def line(points, color=DIM, width=0.7):
    if len(points) < 2:
        return
    draw.line([(x*SCALE, y*SCALE) for x,y in points], fill=color, width=max(1, round(width*SCALE)))
    coords = ' '.join(f'{x:.2f},{y:.2f}' for x,y in points)
    svg.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="{width}"/>')

def rect(x,y,w,h,color=DIM,width=.7):
    line([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)],color,width)

def text(x,y,value,size=12,color=INK,bold=False):
    # Menlo is available on macOS; DejaVu is a portable Pillow/fontconfig fallback.
    candidates = ['/System/Library/Fonts/Menlo.ttc',
                  '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
                  'DejaVuSansMono.ttf']
    for candidate in candidates:
        try:
            font = ImageFont.truetype(candidate, round(size*SCALE), index=1 if bold and candidate.endswith('.ttc') else 0)
            break
        except OSError:
            continue
    else:
        raise RuntimeError('Install a monospace TrueType font to regenerate artwork')
    draw.text((x*SCALE,y*SCALE),value,font=font,fill=color,anchor='ls',stroke_width=0)
    svg.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="Courier New,Courier,monospace" font-size="{size}" font-weight="{700 if bold else 400}">{escape(value)}</text>')

def panel(x,y,w,h,title):
    rect(x,y,w,h)
    text(x+14,y+24,title,13,ACC)
    line([(x,y+37),(x+w,y+37)])

# Same navy, engineering grid, cyan/white ink and sheet border as Two Plus.
for x in range(24,W-23,20):
    line([(x,24),(x,H-24)], GRID, .45)
for y in range(24,H-23,20):
    line([(24,y),(W-24,y)], GRID, .45)
rect(24,24,W-48,H-48, DIM, .9)
line([(24,116),(1256,116)])
text(44,74,'NARWHAL / TOPO',38,INK,True)
text(46,100,'UNDERWATER LiDAR / TERRAIN RECONSTRUCTION',13,DIM)
text(850,51,'NARWHAL TWO PLUS / COMPANION',13,ACC)
text(850,75,'POINTS > TERRAIN > UNDERSTANDING',12,INK)
text(850,99,'github.com/jeremedotxyz/narwhal-topo',11,DIM)
for i in range(1,9):
    text(24+i*1232/9,17,str(i),8,DIM)
for y,label in [(158,'A'),(294,'B'),(430,'C'),(594,'D')]:
    text(10,y,label,8,DIM)

product,_ = build(survey(), Settings(), {'kind':'synthetic','seed':532})
g = product['grid']; stats=product['stats']
cols, rows, cell = g['cols'],g['rows'],g['cell_size']
xmin,ymin=g['x0'],g['y0']; xmax=xmin+cols*cell; ymax=ymin+rows*cell
cx,cy=(xmin+xmax)/2,(ymin+ymax)/2
zmid=stats['z_mean']

def iso(x,y,z):
    x-=cx;y-=cy
    return (430+7.9*(.88*x+.62*y), 345+7.9*(-.22*x+.32*y-2.0*(z-zmid)))

panel(44,134,770,390,'01 / OBSERVED-CELL TERRAIN / ISOMETRIC')
zfloor=stats['z_min']-.4
for i in range(7):
    x=xmin+(xmax-xmin)*i/6
    line([iso(x,ymin,zfloor),iso(x,ymax,zfloor)],'#32516B',.5)
for j in range(5):
    y=ymin+(ymax-ymin)*j/4
    line([iso(xmin,y,zfloor),iso(xmax,y,zfloor)],'#32516B',.5)
line([iso(xmin,ymin,zfloor),iso(xmax,ymin,zfloor),iso(xmax,ymax,zfloor),iso(xmin,ymax,zfloor),iso(xmin,ymin,zfloor)],DIM,.8)

def mesh(indices, color):
    points=[]
    for n in indices:
        z=g['z'][n]
        if z is None:
            line(points,color,.55);points=[];continue
        x=xmin+(n%cols+.5)*cell;y=ymin+(n//cols+.5)*cell
        points.append(iso(x,y,z))
    line(points,color,.55)

for j in range(0,rows,3):
    mesh([j*cols+i for i in range(cols)],'#6C9FB8')
for i in range(0,cols,3):
    mesh([j*cols+i for j in range(rows)],'#4F98AC')
for group in product['contours']:
    for a,b in group['segments']:
        line([iso(*a,group['level']),iso(*b,group['level'])],ACC,.8)
text(60,505,'LOCAL ENU / 2x VERTICAL EXAGGERATION / GAPS PRESERVED',11,DIM)
# A small projected frame triad; direction follows the plotted axes.
origin=(102,449)
line([origin,(151,437)],INK,.9);line([origin,(138,471)],INK,.9);line([origin,(102,412)],INK,.9)
text(155,439,'E',10,ACC);text(140,480,'N',10,ACC);text(97,405,'U',10,ACC)

panel(834,134,402,250,'02 / CONTOURS / 0.50 m INTERVAL')
px,py,factor=902,183,4.4
plan=lambda x,y:(px+(x-xmin)*factor,py+(ymax-y)*factor)
for i in range(7):
    x=xmin+(xmax-xmin)*i/6
    line([plan(x,ymin),plan(x,ymax)],'#32516B',.5)
for j in range(5):
    y=ymin+(ymax-ymin)*j/4
    line([plan(xmin,y),plan(xmax,y)],'#32516B',.5)
rect(px,py,(xmax-xmin)*factor,(ymax-ymin)*factor,DIM,.6)
for group in product['contours']:
    color=INK if math.isclose(group['level']%2,0,abs_tol=1e-8) else ACC
    for a,b in group['segments']:
        line([plan(*a),plan(*b)],color,.65)
text(848,372,'-18.41 to -10.06 m / LOCAL VERTICAL ZERO',10,DIM)
line([(1208,220),(1208,189),(1203,199),(1208,189),(1213,199)],INK,.9)
text(1204,183,'N',10,ACC)
text(852,201,'+20',9,DIM);text(852,356,'-20',9,DIM)

j=rows//2
north=ymin+(j+.5)*cell
panel(834,400,402,124,f'03 / SECTION / N {north:+.2f} m')
left,right,top,bottom=855,1218,448,498
for k in range(3):
    y=top+(bottom-top)*k/2
    line([(left,y),(right,y)],'#32516B',.5)
points=[]
for i in range(cols):
    z=g['z'][j*cols+i]
    if z is None:
        line(points,ACC,1.35);points=[];continue
    x=left+(i+.5)/cols*(right-left)
    y=bottom-(z-stats['z_min'])/(stats['z_max']-stats['z_min'])*(bottom-top)
    points.append((x,y))
line(points,ACC,1.35)
text(855,515,'-30 E',9,DIM);text(1028,515,'0',9,DIM);text(1184,515,'+30 E',9,DIM)

line([(24,548),(1256,548)],DIM,.9)
for x in (298,552,806):
    line([(x,548),(x,616)],DIM,.7)
text(44,582,f"{stats['accepted_points']:,}",25,INK,True)
text(44,604,'ACCEPTED RETURNS',11,DIM)
text(320,582,'0.50 m',25,INK,True)
text(320,604,'GRID CELL SIZE',11,DIM)
text(574,582,f"{stats['valid_cells']:,}",25,INK,True)
text(574,604,'OBSERVED CELLS',11,DIM)
text(828,579,'SYNTHETIC REFERENCE',18,ACC,True)
text(828,603,'NRW-REF-0532 / REV A / v0.1.0',11,DIM)
svg.append('</svg>')
(OUT/'social-preview.svg').write_text('\n'.join(svg)+'\n')
image.resize((W,H),Image.Resampling.LANCZOS).save(OUT/'social-preview.png',optimize=True)
print(f'Saved {OUT}/social-preview.svg and .png ({W} x {H})')
