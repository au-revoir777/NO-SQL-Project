"""Hub audit for CARE-GNN YelpChi.mat / Amazon.mat. Usage: python3 -I audit_mat.py <file.mat> <rel1,rel2,...>"""
import sys
import numpy as np
import scipy.io as sio
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

path, rels = sys.argv[1], sys.argv[2].split(',')
m = sio.loadmat(path)
y = np.asarray(m['label']).ravel().astype(int)
n = y.shape[0]
print(f"file={path.split('/')[-1]} n={n} labels: {dict(zip(*np.unique(y, return_counts=True)))} pos_rate={y.mean():.4f}")
q = lambda a: {p: float(np.percentile(a, p)) for p in (50, 90, 99)} | {'max': int(a.max()) if a.size else 0}

for r in rels:
    A = sp.csr_matrix(m[r])
    A.setdiag(0); A.eliminate_zeros()
    A = ((A + A.T) > 0).astype(np.int8).tocsr()
    und_edges = A.nnz // 2
    deg = np.asarray(A.sum(1)).ravel()
    iso = int((deg == 0).sum())
    print(f"\n== {r}: undirected edges={und_edges} isolated_nodes={iso} node-degree q(non-isolated)={q(deg[deg>0])}")
    ncomp, comp = connected_components(A, directed=False)
    sizes = np.bincount(comp)
    # clique test: each component's internal undirected edge count == k(k-1)/2
    e_per_comp = np.bincount(comp, weights=deg) / 2
    full = sizes * (sizes - 1) / 2
    nontriv = sizes >= 2
    clique_frac = float((e_per_comp[nontriv] == full[nontriv]).mean())
    print(f"components(size>=2)={int(nontriv.sum())} frac_components_that_are_cliques={clique_frac:.4f} "
          f"edges_in_clique_components={e_per_comp[nontriv & (e_per_comp==full)].sum()/max(und_edges,1):.4f}")
    gs = sizes[nontriv]
    print(f"group(component) size q={q(gs)}")
    for T in (27, 250):
        big = sizes > T
        e_big = e_per_comp[big].sum()
        mem = big[comp] & (deg > 0)
        other = (~big[comp]) & (deg > 0)
        print(f"  groups>{T}: n_groups={int(big.sum())} members={int(mem.sum())} share_edges={e_big/max(und_edges,1):.4f} "
              f"pos_rate_members={y[mem].mean() if mem.any() else float('nan'):.4f} pos_rate_other_nonisolated={y[other].mean() if other.any() else float('nan'):.4f}")
    # node-degree based (valid when not clique-decomposable): share of edges incident to nodes with degree > T
    for T in (27, 250):
        hi = deg > T
        rows, cols = A.nonzero()
        inc = (hi[rows] | hi[cols]).sum() / 2
        print(f"  node-degree>{T}: nodes={int(hi.sum())} share_edges_incident={inc/max(und_edges,1):.4f} "
              f"pos_rate_hi={y[hi].mean() if hi.any() else float('nan'):.4f} pos_rate_lo_nonisolated={y[(~hi)&(deg>0)].mean():.4f}")
