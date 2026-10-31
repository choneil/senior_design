import struct, zlib, re
MARK = b'\x14\x00\x06\x00\x08\x00'
rot = lambda b: bytes(((x << 4) | (x >> 4)) & 0xff for x in b)
def streams(path):
    return streams_bytes(open(path, "rb").read())
def streams_bytes(data):
    """Return {stream_name: bytes} for a SolidWorks 2015+ file (largest copy wins)."""
    out = {}
    for m in re.finditer(re.escape(MARK), data):
        p = m.start()
        csize, usize, nlen = struct.unpack_from('<III', data, p+14)
        if not 0 < nlen < 512: continue
        name = rot(data[p+26:p+26+nlen]).decode('latin1')
        if not all(32 <= ord(c) < 127 for c in name): continue
        raw = data[p+26+nlen:p+26+nlen+csize]
        try: body = zlib.decompress(raw, -15)
        except Exception: body = raw
        if len(body) > len(out.get(name, b'')): out[name] = body
    return out
