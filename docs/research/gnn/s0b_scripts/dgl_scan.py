"""Read-only scanner for DGL save_graphs binary files (no DGL needed).
Finds serialized NDArrays by their magic number and reports dtype/shape/offset.
Usage: python3 -I dgl_scan.py <file>"""
import sys, struct, mmap, re

NDARRAY_MAGIC = struct.pack('<Q', 0xDD5E40F096B4A13F)


def scan(path, verbose=True):
    f = open(path, 'rb')
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    out = []
    pos = 0
    while True:
        i = mm.find(NDARRAY_MAGIC, pos)
        if i < 0:
            break
        p = i + 8 + 8  # magic, reserved
        dev_type, dev_id, ndim = struct.unpack_from('<iii', mm, p); p += 12
        code, bits, lanes = struct.unpack_from('<BBH', mm, p); p += 4
        if not (0 <= ndim <= 4 and bits in (1, 8, 16, 32, 64)):
            pos = i + 8; continue
        shape = struct.unpack_from('<' + 'q' * ndim, mm, p); p += 8 * ndim
        nbytes, = struct.unpack_from('<q', mm, p); p += 8
        # preceding text (names) for context
        ctx = mm[max(0, i - 64):i]
        names = re.findall(rb'[a-z_]{3,}', ctx)
        out.append(dict(off=p, code=code, bits=bits, shape=shape, nbytes=nbytes, ctx=[n.decode() for n in names][-2:]))
        if verbose:
            print(f"off={p} dtype=({code},{bits}) shape={shape} nbytes={nbytes} ctx={out[-1]['ctx']}")
        pos = p + max(nbytes, 0)
    return mm, out


if __name__ == '__main__':
    scan(sys.argv[1])
