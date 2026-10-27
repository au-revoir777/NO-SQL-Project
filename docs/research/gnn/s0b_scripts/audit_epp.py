"""Hub audit for Elliptic++ actors. Usage: python3 -I audit_epp.py <dir>"""
import sys
import numpy as np
import pandas as pd

D = sys.argv[1]
wc = pd.read_csv(f'{D}/wallets_classes.csv')
print('wallet class counts (address rows):', wc['class'].value_counts().to_dict(), 'unique addresses', wc['address'].nunique())
cls = wc.drop_duplicates('address').set_index('address')['class']
tx_cls = pd.read_csv(f'{D}/txs_classes.csv').set_index('txId')['class']


def report(name, df, addr_col, grp_col):
    df = df.drop_duplicates([addr_col, grp_col])
    sz = df.groupby(grp_col)[addr_col].size()
    df = df.assign(k=df[grp_col].map(sz).values)
    sz2 = sz[sz >= 2]
    pairs = sz2 * (sz2 - 1) / 2
    print(f"\n== {name}: groups={len(sz)} groups(size>=2)={len(sz2)} memberships={len(df)} size q(>=2)="
          f"{ {p: float(np.percentile(sz2, p)) for p in (50, 90, 99)} } max={int(sz.max())} projected_pairs={pairs.sum():.3e}")
    c = df[addr_col].map(cls)
    for T in (27, 250):
        big = df['k'] > T
        hub_addr = set(df.loc[big, addr_col])
        oth_addr = set(df.loc[(~big) & (df['k'] >= 2), addr_col]) - hub_addr
        ch = cls.reindex(list(hub_addr)); co = cls.reindex(list(oth_addr))
        rate = lambda s: ((s == 1).sum() / s.isin([1, 2]).sum()) if s.isin([1, 2]).any() else float('nan')
        print(f"  size>{T}: groups={int((sz>T).sum())} share_memberships={big.mean():.4f} share_projected_pairs={pairs[sz2.index.isin(sz[sz>T].index)].sum()/pairs.sum():.4f} "
              f"hub_addrs={len(hub_addr)} illicit_rate_labelled_hub={rate(ch):.4f} other_grouped={rate(co):.4f} labelled_frac_hub={ch.isin([1,2]).mean():.3f}")
        gl = tx_cls.reindex(sz[sz > T].index)
        print(f"    hub-group txs class counts: {gl.value_counts(dropna=False).to_dict()}")


at = pd.read_csv(f'{D}/AddrTx_edgelist.csv')
report('co-input (addresses grouped by spending tx)', at, 'input_address', 'txId')
ta = pd.read_csv(f'{D}/TxAddr_edgelist.csv')
report('co-output (addresses grouped by paying tx)', ta, 'output_address', 'txId')
aa = pd.read_csv(f'{D}/AddrAddr_edgelist.csv')
aa = aa[aa.iloc[:, 0] != aa.iloc[:, 1]].drop_duplicates()
deg = pd.concat([aa.iloc[:, 0], aa.iloc[:, 1]]).value_counts()
print(f"\n== addr-addr (money flow): distinct non-self pairs={len(aa)} nodes={len(deg)} degree q={ {p: float(np.percentile(deg, p)) for p in (50,90,99)} } max={int(deg.max())}")
