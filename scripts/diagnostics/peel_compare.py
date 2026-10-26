"""Diagnostic: compare thresholded components and peel output in the incremental region view vs the full view at one batch.

    python scripts/diagnostics/peel_compare.py none 1.0 1004 ring_in_hub 74
"""
import sys, logging, structlog, json
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))
sys.path.insert(0, __import__('os').path.dirname(__file__))
from trace_region import build, jac
from fraudsim.experiments.harness import make_stream, DEFAULT_MODEL
from fraudsim.experiments.large_hubs import overrides
from fraudsim.scoring.scorer import RingScorer
from fraudsim.metrics.evaluation import all_members, true_rings
from fraudsim.detectors.hubaware import _components
weight, edge, seed, ringname, stop = sys.argv[1], float(sys.argv[2]), int(sys.argv[3]), sys.argv[4], int(sys.argv[5])
st=make_stream("hub_heavy",seed,overrides(500)); sc=RingScorer.load(DEFAULT_MODEL)
inc,hi,li=build(weight,edge,True,sc); full,hf,lf=build(weight,edge,False,sc)
mem={r.ring_id:all_members(r) for r in true_rings(st.generator.ledger)}[ringname]
for b,batch in enumerate(inc.batches(st.events)):
    inc.process(batch); full.process(batch)
    if b==stop: break
def adj_of(h,view):
    adj={}
    for (u,v),pw in h.pair_weights(view).items():
        if pw.attr>0 and pw.total>=edge:
            adj.setdefault(u,{})[v]=pw.total; adj.setdefault(v,{})[u]=pw.total
    return adj
for name,h,l in (("inc",hi,li),("full",hf,lf)):
    view=l["view"][-1]; adj=adj_of(h,view)
    comps=[g for g in _components(adj,set(adj)) if g & mem]
    print(name,"view users",len(view.users),"ring members in view",len(mem & set(view.users)))
    for g in comps:
        print("  component size",len(g),"ring members in it",len(g&mem))
    print("  candidates touching ring:",[ (len(c), round(jac(set(c),mem),2)) for c in l["cands"][-1] if c & mem])
