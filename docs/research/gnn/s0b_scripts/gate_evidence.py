"""Second-evidence availability for hub-mediated pairs. Usage: python3 -I gate_evidence.py <datasets_dir>"""
import sys
import numpy as np
import pandas as pd
import scipy.io as sio
import scipy.sparse as sp

D = sys.argv[1]


def sym(M):
    M = sp.csr_matrix(M); M.setdiag(0); M.eliminate_zeros()
    return sp.triu(((M + M.T) > 0).astype(np.int8), 1).tocsr()

# YelpChi: R-S-R pairs inside groups >250, how many also R-T-R or R-U-R
if False:
  m = sio.loadmat(f'{D}/caregnn_yelp_amazon/YelpChi.mat')
  y = m['label'].ravel()
  rsr, rtr, rur = sym(m['net_rsr']), sym(m['net_rtr']), sym(m['net_rur'])
  from scipy.sparse.csgraph import connected_components
  _, comp = connected_components(rsr + rsr.T, directed=False)
  sz = np.bincount(comp)
  r, c = rsr.nonzero()
  other = ((rtr + rur) > 0).tocsr()
  has2 = np.asarray(other[r, c]).ravel() > 0
  for T in (27, 250):
      big = sz[comp[r]] > T
      print(f"YelpChi R-S-R pairs in groups>{T}: {int(big.sum())}; with 2nd relation (R-T-R or R-U-R): {has2[big].mean():.4f}; "
            f"both-fraud among 2nd-evidence pairs={((y[r]==1)&(y[c]==1))[big & has2].mean():.4f} vs no-2nd={((y[r]==1)&(y[c]==1))[big & ~has2].mean():.4f}")
  print(f"YelpChi R-S-R pairs in groups<=27 with 2nd relation: {has2[sz[comp[r]] <= 27].mean():.4f}")

# Elliptic++: co-input pairs sharing >=2 spending txs, or also co-output
at = pd.read_csv(f'{D}/ellipticpp/AddrTx_edgelist.csv').drop_duplicates()
ta = pd.read_csv(f'{D}/ellipticpp/TxAddr_edgelist.csv').drop_duplicates()
addr, _ = pd.factorize(pd.concat([at.input_address, ta.output_address]))
na = addr.max() + 1
tx_codes, tx_u = pd.factorize(pd.concat([at.txId, ta.txId]))
ntx = tx_codes.max() + 1
Bi = sp.csr_matrix((np.ones(len(at), np.int32), (addr[:len(at)], tx_codes[:len(at)])), shape=(na, ntx))
Bo = sp.csr_matrix((np.ones(len(ta), np.int32), (addr[len(at):], tx_codes[len(at):])), shape=(na, ntx))
gsize = np.asarray(Bi.sum(0)).ravel()
for T in (27, 250):
    keep = sp.diags((gsize > T).astype(np.int32))
    Ci = sp.triu(Bi @ keep @ Bi.T, 1).tocsr()  # pairs co-inputting in hub txs
    Call = sp.triu(Bi @ Bi.T, 1).tocsr()
    rr, cc = Ci.nonzero()
    multi = np.asarray(Call[rr, cc]).ravel() >= 2
    coout = np.zeros(len(rr), bool)
    for k in range(0, len(rr), 1_000_000):
        coout[k:k+1_000_000] = np.asarray(Bo[rr[k:k+1_000_000]].multiply(Bo[cc[k:k+1_000_000]]).sum(1)).ravel() > 0
    print(f"Elliptic++ co-input pairs via txs>{T}: {len(rr)}; share in >=2 co-input txs={multi.mean():.4f}; also co-output={coout.mean():.4f}; any 2nd={(multi|coout).mean():.4f}")
