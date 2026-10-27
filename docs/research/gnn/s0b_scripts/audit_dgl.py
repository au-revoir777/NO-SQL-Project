"""Hub audit for homogeneous GADBench DGL graphs, read via dgl_scan (no DGL).
Usage: python3 -I audit_dgl.py <file>"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components
from dgl_scan import scan

path = sys.argv[1]
mm, arrs = scan(path, verbose=False)
dt = {(0, 64): np.int64, (0, 32): np.int32, (2, 32): np.float32, (1, 8): np.uint8}


def get(a):
    return np.frombuffer(mm, dtype=dt[(a['code'], a['bits'])], count=int(np.prod(a['shape'])), offset=a['off']).reshape(a['shape'])

big = [a for a in arrs if len(a['shape']) == 1 and a['shape'][0] > 100 and not a['ctx']]
src, dst = get(big[0]), get(big[1])
lab = [a for a in arrs if a['ctx'] == ['label']][0]
y = get(lab).astype(int)
tm = get([a for a in arrs if a['ctx'] == ['train_masks']][0])
n = y.shape[0]
print(f"file={os.path.basename(path)} n={n} stored_directed_edges={src.size} labels={dict(zip(*np.unique(y, return_counts=True)))} pos_rate={y.mean():.4f}")
print(f"train_mask sizes (fully-sup trial0, semi-sup trial10): {int(tm[:,0].sum())}, {int(tm[:,10].sum())}")
m = src != dst
A = sp.coo_matrix((np.ones(m.sum(), dtype=np.int8), (src[m], dst[m])), shape=(n, n)).tocsr()
A = ((A + A.T) > 0).astype(np.int8).tocsr()
E = A.nnz // 2
deg = np.asarray(A.sum(1)).ravel()
print(f"self_loops={int((~m).sum())} undirected_simple_edges={E} isolated={int((deg==0).sum())}")
nz = deg[deg > 0]
print("node degree q:", {p: float(np.percentile(nz, p)) for p in (50, 90, 99)}, "max", int(nz.max()))
rows, cols = A.nonzero()
for T in (27, 250):
    hi = deg > T
    inc = (hi[rows] | hi[cols]).sum() / 2
    lo = (~hi) & (deg > 0)
    print(f"  deg>{T}: nodes={int(hi.sum())} share_edges_incident={inc/E:.4f} pos_rate_hi={y[hi].mean() if hi.any() else float('nan'):.4f} pos_rate_lo={y[lo].mean():.4f}")
ncomp, comp = connected_components(A, directed=False)
sizes = np.bincount(comp)
e_c = np.bincount(comp, weights=deg) / 2
k = sizes >= 2
print(f"components(size>=2)={int(k.sum())} largest={int(sizes.max())} frac_comp_cliques={float((e_c[k]==sizes[k]*(sizes[k]-1)/2).mean()):.3f}")
# sampled local clustering coefficient (clique-projection signature)
rng = np.random.default_rng(0)
cand = np.where(deg >= 2)[0]
samp = rng.choice(cand, size=min(300, cand.size), replace=False)
cc = []
for v in samp:
    N = A.indices[A.indptr[v]:A.indptr[v+1]]
    if N.size > 5000:
        N = rng.choice(N, 5000, replace=False)
    sub = A[N][:, N]
    d = N.size
    cc.append(sub.nnz / (d * (d - 1)))
cc = np.array(cc)
print(f"sampled local clustering (n={cc.size}): mean={cc.mean():.3f} median={np.median(cc):.3f}")
