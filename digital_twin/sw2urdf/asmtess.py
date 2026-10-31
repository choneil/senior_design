import re
from dl import triangles
def component_tess(S):
    """{component_path: triangles} from an assembly's FaceTessellations cache."""
    d = S['FaceTessellations/Directory']
    ents = []
    for m in re.finditer(rb'\xff\xfe\xff(.)((?:[\x20-\x7e]\x00)+)', d, re.S):
        s = m.group(2).decode('utf-16le')
        if re.fullmatch(r'\d{3}-\d{3}-\d{3}', s):
            ents.append((name, d[m.start()-8:m.start()], s))
        else:
            name = s[:ord(m.group(1))] if ord(m.group(1)) <= len(s) else s
    out = {}
    by_stream = {}
    for name, cid, sid in ents: by_stream.setdefault(sid, []).append((name, cid))
    for sid, comps in by_stream.items():
        data = S['FaceTessellations/' + sid]
        pos = sorted((data.find(cid), name) for name, cid in comps)
        pos = [(p, n) for p, n in pos if p >= 0]
        for i, (p, n) in enumerate(pos):
            end = pos[i+1][0] if i+1 < len(pos) else len(data)
            out[n] = triangles(data[p:end]).astype(float)
    return out
