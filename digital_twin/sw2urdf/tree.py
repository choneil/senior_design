import xml.etree.ElementTree as ET, numpy as np, os, re
NS = '{http://www.solidworks.com/sw2003/schema}'
WIN_ROOT, ROOT = None, None   # Windows folder in the tree's paths, and the local folder standing in for it
def set_root(win_asm, local_asm, win_paths=()):
    """Match the top assembly's stored Windows path against its local path: their common tail is the part
    of the Pack and Go layout that was kept, the rest are the two roots. When the assembly was saved from a
    subfolder (Pack and Go's CopyDesignTemp) its parts sit higher up, so of the stored folder and its parents
    take the one under which most of the tree's file paths (win_paths) exist locally."""
    global WIN_ROOT, ROOT
    w = win_asm.replace('\\', '/').split('/'); l = os.path.abspath(local_asm).split(os.sep)
    n = 0
    while n < min(len(w), len(l)) and w[-1 - n].lower() == l[-1 - n].lower(): n += 1
    WIN_ROOT, ROOT = '/'.join(w[:len(w) - n]).lower(), os.sep.join(l[:len(l) - n])
    paths = [p.replace('\\', '/') for p in win_paths]
    def hits(root):
        return sum(p.lower().startswith(root + '/') and os.path.exists(os.path.join(ROOT, *p[len(root) + 1:].split('/')))
                   for p in paths)
    if paths: WIN_ROOT = max(['/'.join(w[:k]).lower() for k in range(len(w) - n, 1, -1)], key=hits)   # ties: deepest
def local(p):
    """Map a Windows path in the tree to the unpacked Pack and Go folder (None if not found). Files from
    outside the root (vendor downloads) are packed under their own folders: the longest tail of the stored
    path that exists under the local root."""
    p = p.replace('\\', '/')
    if WIN_ROOT is not None and p.lower().startswith(WIN_ROOT + '/'):
        q = os.path.join(ROOT, *p[len(WIN_ROOT) + 1:].split('/'))
        if os.path.exists(q): return q
    if ROOT is None: return None
    parts = p.split('/')[1:]                             # drop the drive letter
    for k in range(len(parts)):
        q = os.path.join(ROOT, *parts[k:])
        if os.path.exists(q): return q
    return None
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
