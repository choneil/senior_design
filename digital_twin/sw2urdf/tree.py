import xml.etree.ElementTree as ET, numpy as np, os, re
NS = '{http://www.solidworks.com/sw2003/schema}'
WIN_ROOT, ROOT = None, None   # Windows folder in the tree's paths, and the local folder standing in for it
def set_root(win_asm, local_asm):
    """Match the top assembly's stored Windows path against its local path: their common tail is the part
    of the Pack and Go layout that was kept, the rest are the two roots."""
    global WIN_ROOT, ROOT
    w = win_asm.replace('\\', '/').split('/'); l = os.path.abspath(local_asm).split(os.sep)
    n = 0
    while n < min(len(w), len(l)) and w[-1 - n].lower() == l[-1 - n].lower(): n += 1
    WIN_ROOT, ROOT = '/'.join(w[:len(w) - n]).lower(), os.sep.join(l[:len(l) - n])
def local(p):
    """Map a Windows path in the tree to the unpacked Pack and Go folder (None if outside it)."""
    p = p.replace('\\', '/')
    if WIN_ROOT is None or not p.lower().startswith(WIN_ROOT + '/'): return None
    return os.path.join(ROOT, *p[len(WIN_ROOT) + 1:].split('/'))
def load(xml_path):
    r = ET.parse(xml_path).getroot()
    files = {f.get('id'): f for f in r.iter(NS+'swFile')}
    models = {m.get('id'): m for m in r.iter(NS+'swModel')}
    return files, models
def mat(s):
    a = np.array([float(x) for x in s.split()]).reshape(4, 4)
    return a.T   # SolidWorks stores row-vector form; convert to column-vector 4x4
def walk(files, models, mid, T=np.eye(4), path=()):
    """Yield (instance_path, model, file_elem, world_T, suppressed/hidden) for each leaf part."""
    m = models[mid]
    for ref in m.findall(NS+'swReference'):
        child = models[ref.get('swModelRef')]
        Tc = T @ mat(ref.get('swTransform'))
        name = f"{ref.get('swName')}-{ref.get('swReferenceNumber')}"
        off = ref.get('swSuppressed') == 'YES' or ref.get('swHidden') == 'YES'
        f = files[child.get('swFileRef')]
        if f.get('swDocType') == 'ASSEMBLY':
            yield (path+(name,), child, f, Tc, off, True)
            yield from ((p, c, ff, t, o or off, a) for p, c, ff, t, o, a in walk(files, models, child.get('id'), Tc, path+(name,)))
        else:
            yield (path+(name,), child, f, Tc, off, False)
def top(models, files):
    kids = {r.get('swModelRef') for m in models.values() for r in m.findall(NS+'swReference')}
    return [i for i, m in models.items() if i not in kids and files[m.get('swFileRef')].get('swDocType') == 'ASSEMBLY']
