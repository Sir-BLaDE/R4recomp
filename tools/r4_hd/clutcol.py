"""clutcol.py: with the runtime on the debug port, record every (texture page,
CLUT) pair the last frames drew, the CLUT words (vram_peek) and the UV boxes
drawn, into /tmp/claude-0/cluts.json (append with argv[1] == "append").
Input for build_pack.py --cluts. Dev tool."""
import sys,json; sys.path.insert(0,'/home/claude/work')
from tcp import call
out=json.load(open('/tmp/claude-0/cluts.json')) if len(sys.argv)>1 and sys.argv[1]=='append' else []
seen={(o['page'][0],o['page'][1],o['mode'],o['clut'][0],o['clut'][1],tuple(o['words'])) for o in out}
f=call(4370,{'cmd':'mod_counters'})['frame']
pairs={}; boxes={}
for d in range(1,4):
    r=call(4370,{'cmd':'gpu_frame_dump','frame':f-d,'count':20000},timeout=120)
    tp=None
    for e in r['entries']:
        op=int(e['op'],16); w=[int(x,16) for x in e['w']]
        if op==0xE1: tp=w[0]&0x1ff
        def add(k,uvs):
            us=[u for u,v in uvs]; vs=[v for u,v in uvs]
            b=pairs.get(k)
            nb=(min(us),min(vs),max(us),max(vs))
            pairs[k]=nb if b is None else (min(b[0],nb[0]),min(b[1],nb[1]),max(b[2],nb[2]),max(b[3],nb[3]))
            boxes.setdefault(k,set()).add(nb)
        uvof=lambda x:(x&0xff,(x>>8)&0xff)
        if op in (0x2C,0x2D,0x2E,0x2F) and len(w)>=9:
            add(((w[4]>>16)&0x1ff, w[2]>>16),[uvof(w[2]),uvof(w[4]),uvof(w[6]),uvof(w[8])])
        if op in (0x24,0x25,0x26,0x27) and len(w)>=7:
            add(((w[4]>>16)&0x1ff, w[2]>>16),[uvof(w[2]),uvof(w[4]),uvof(w[6])])
        if op in (0x34,0x35,0x36,0x37) and len(w)>=9:
            add(((w[5]>>16)&0x1ff, w[2]>>16),[uvof(w[2]),uvof(w[5]),uvof(w[8])])
        if op in (0x3C,0x3D,0x3E,0x3F) and len(w)>=12:
            add(((w[5]>>16)&0x1ff, w[2]>>16),[uvof(w[2]),uvof(w[5]),uvof(w[8]),uvof(w[11])])
        if op in (0x64,0x65,0x66,0x67) and tp is not None and len(w)>=4:
            u,v=uvof(w[2]); ww=w[3]&0xffff; hh=w[3]>>16
            add((tp, w[2]>>16),[(u,v),(min(255,u+ww-1),min(255,v+hh-1))])
        if op in (0x74,0x75,0x76,0x77,0x7C,0x7D,0x7E,0x7F) and tp is not None:
            u,v=uvof(w[2]); sz=8 if op<0x7C else 16
            add((tp, w[2]>>16),[(u,v),(min(255,u+sz-1),min(255,v+sz-1))])
n=0
for (tp,cl),bb in pairs.items():
    mode=(tp>>7)&3
    if mode>1: continue
    px,py=(tp&15)*64,((tp>>4)&1)*256
    cx,cy=(cl&63)*16,(cl>>6)&511
    cnt=16 if mode==0 else 256
    hx=''
    for off in range(0,cnt,128):
        hx+=call(4370,{'cmd':'vram_peek','x':cx+off,'y':cy,'w':min(128,cnt-off),'h':1})['hex']
    words=[int(hx[i*4:i*4+4],16) for i in range(cnt)]
    # vram_peek hex byte order check: assume big-endian per word string
    key=(px,py,mode,cx,cy,tuple(words))
    if key in seen: continue
    seen.add(key); out.append({'page':[px,py],'mode':mode,'clut':[cx,cy],'words':words,'uv':list(bb),'boxes':sorted(boxes[(tp,cl)])}); n+=1
json.dump(out,open('/tmp/claude-0/cluts.json','w'))
print('pairs',len(pairs),'new',n,'total',len(out))
