"""Hub audit for AMLworld (IBM) Small files. Usage: python3 -I audit_aml.py <Trans.csv> <accounts.csv>"""
import sys
import numpy as np
import pandas as pd

tp, ap = sys.argv[1], sys.argv[2]
t = pd.read_csv(tp, dtype=str, usecols=[0, 1, 2, 3, 4, 10], header=0)
t.columns = ['ts', 'fb', 'fa', 'tb', 'ta', 'y']
t['y'] = t['y'].astype(np.int8)
src = (t['fb'] + '|' + t['fa']).values
dst = (t['tb'] + '|' + t['ta']).values
ts = pd.to_datetime(t['ts'], format='%Y/%m/%d %H:%M')
print(f"file={tp.split('/')[-1]} transactions={len(t)} laundering_tx={int(t['y'].sum())} tx_pos_rate={t['y'].mean():.5f}")
print(f"time range {ts.min()} .. {ts.max()} ; distinct timestamps={ts.nunique()} ; self-transactions={(src==dst).sum()}")
codes, uniq = pd.factorize(np.concatenate([src, dst]))
s, d = codes[:len(t)], codes[len(t):]
n = len(uniq)
ill = np.zeros(n, bool)
ill[s[t['y'].values == 1]] = True
ill[d[t['y'].values == 1]] = True
print(f"accounts_in_tx={n} accounts touching a laundering tx={int(ill.sum())} node_pos_rate={ill.mean():.5f}")

acc = pd.read_csv(ap, dtype=str)
acc.columns = ['bank_name', 'bank_id', 'acct', 'entity', 'entity_name']
print(f"accounts file rows={len(acc)} unique acct numbers={acc['acct'].nunique()} unique entities={acc['entity'].nunique()}")
# map account number -> entity (account numbers checked for uniqueness above)
ent_of = dict(zip(acc['acct'], acc['entity']))
acct_num = np.array([u.split('|', 1)[1] for u in uniq])
ent = pd.Series(acct_num).map(ent_of)
print(f"tx accounts with entity match={ent.notna().mean():.4f}")
bank = np.array([u.split('|', 1)[0] for u in uniq])


def report(name, member, group):
    """member: node index array, group: group key array (bipartite memberships, deduped)."""
    df = pd.DataFrame({'m': member, 'g': group}).drop_duplicates()
    sz = df.groupby('g')['m'].size()
    df['k'] = df['g'].map(sz).values
    sz2 = sz[sz >= 2]
    pairs = (sz2 * (sz2 - 1) / 2)
    q = {p: float(np.percentile(sz2, p)) for p in (50, 90, 99)}
    print(f"\n== {name}: groups={len(sz)} groups(size>=2)={len(sz2)} memberships={len(df)} size q(>=2)={q} max={int(sz.max())}")
    for T in (27, 250):
        bigm = df['k'] > T
        hub_nodes = np.zeros(n, bool); hub_nodes[df.loc[bigm, 'm'].values] = True
        nonhub_nodes = np.zeros(n, bool); nonhub_nodes[df.loc[~bigm & (df['k'] >= 2), 'm'].values] = True
        nonhub_nodes &= ~hub_nodes
        print(f"  size>{T}: groups={int((sz>T).sum())} share_memberships={bigm.mean():.4f} share_projected_pairs={pairs[pairs.index.isin(sz[sz>T].index)].sum()/pairs.sum():.4f} "
              f"members={int(hub_nodes.sum())} pos_rate_hub_members={ill[hub_nodes].mean() if hub_nodes.any() else float('nan'):.5f} pos_rate_other_grouped={ill[nonhub_nodes].mean() if nonhub_nodes.any() else float('nan'):.5f}")
    print(f"  projected pairs total={pairs.sum():.3e}")


m = ent.notna().values
report('entity (co-owned accounts)', np.where(m)[0], ent[m].values)
report('common payee (senders grouped by receiver)', s, d)
report('common payer (receivers grouped by sender)', d, s)
report('bank', np.arange(n), bank)
# second-evidence availability: for co-owned account pairs, how many also transact directly
e = pd.factorize(ent.values)[0]
nz = s != d
pairs_tx = pd.DataFrame({'a': np.minimum(s[nz], d[nz]), 'b': np.maximum(s[nz], d[nz]), 'y': t['y'].values[nz]}).drop_duplicates(['a', 'b'])
intra = e[pairs_tx['a'].values] == e[pairs_tx['b'].values]
esz = pd.Series(e).value_counts()
tot_pairs = (esz * (esz - 1) / 2).sum()
print(f"\n== gate evidence: distinct transacting pairs={len(pairs_tx)}; intra-entity transacting pairs={int(intra.sum())} ({intra.mean():.4f} of tx pairs); "
      f"co-owned pairs with a direct transfer={intra.sum()/tot_pairs:.2e} of all co-owned pairs; laundering rate on intra-entity tx pairs={pairs_tx['y'].values[intra].mean():.5f} vs inter={pairs_tx['y'].values[~intra].mean():.5f}")
