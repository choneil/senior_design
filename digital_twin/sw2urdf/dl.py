import struct, numpy as np
def faces(d):
    """Yield (strip_lengths, verts[N,3], normals[N,3]) per tessellated face in a DisplayLists stream."""
    i = 0; L = len(d)
    while True:
        i = d.find(b'\x04\x00\x00\x00\x08\x00\x00\x00\x02\x00\x00\x00', i)
        if i < 0 or i + 16 > L: return
        k = struct.unpack_from('<I', d, i+12)[0]
        p = i + 16
        if 0 < k < 1_000_000 and p + 4*k + 16 <= L:
            strips = struct.unpack_from(f'<{k}I', d, p); S = sum(strips); q = p + 4*k
            if all(s >= 3 for s in strips) and struct.unpack_from('<4I', d, q) == (12, 100, 2, S):
                v = np.frombuffer(d, '<f4', S*3, q+16).reshape(S, 3)
                r = q + 16 + 12*S
                if struct.unpack_from('<4I', d, r) == (12, 100, 2, S):
                    n = np.frombuffer(d, '<f4', S*3, r+16).reshape(S, 3)
                    yield strips, v, n; i = r + 16 + 12*S; continue
        i += 4
def triangles(d, mode='strip'):
    tris = []
    for strips, v, n in faces(d):
        o = 0
        for s in strips:
            for j in range(s-2):
                if mode == 'strip':
                    a, b, c = (o+j, o+j+1, o+j+2) if j % 2 == 0 else (o+j+1, o+j, o+j+2)
                else:
                    a, b, c = o, o+j+1, o+j+2
                t = v[[a, b, c]]
                # orient with stored vertex normals
                if np.dot(np.cross(t[1]-t[0], t[2]-t[0]), n[a]+n[b]+n[c]) < 0: t = t[[0, 2, 1]]
                tris.append(t)
            o += s
    return np.array(tris)
def read_stl(path):
    b = open(path, 'rb').read(); n = struct.unpack_from('<I', b, 80)[0]
    a = np.frombuffer(b, np.dtype([('n', '<3f4'), ('v', '<9f4'), ('x', '<u2')]), n, 84)
    return a['v'].reshape(n, 3, 3).astype(float)
def area(t): return 0.5*np.linalg.norm(np.cross(t[:, 1]-t[:, 0], t[:, 2]-t[:, 0]), axis=1).sum()
def volume(t): return np.einsum('ij,ij->i', t[:, 0], np.cross(t[:, 1], t[:, 2])).sum()/6
