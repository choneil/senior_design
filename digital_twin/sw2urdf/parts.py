import os, numpy as np
from sw import streams, streams_bytes
from dl import triangles
from tree import local
_cache = {}
def part_mesh(file_elem, asm_streams):
    """Triangles (N,3,3) in part coordinates for a part file element, or None."""
    p = file_elem.get('swPath')
    if p in _cache: return _cache[p]
    s = None; lp = local(p)
    if lp and os.path.exists(lp): s = streams(lp)
    else:
        base = p.replace('\\', '/').split('/')[-1]
        for k, v in asm_streams.items():   # embedded imported / virtual parts
            kb = k.split('/', 1)[-1]
            if kb.lower() == base.lower() or kb.lower().replace('-sldprt', '.sldprt') == base.lower():
                s = streams_bytes(v); break
    t = None
    if s and 'Contents/DisplayLists' in s:
        t = triangles(s['Contents/DisplayLists']).astype(float)
        if len(t) == 0: t = None
    _cache[p] = t
    return t
