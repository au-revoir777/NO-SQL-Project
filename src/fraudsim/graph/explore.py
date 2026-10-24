"""
Entity and graph explorer (P6): search, entity details and bounded k-hop
neighbourhoods over a GraphStore.

The neighbourhood walk is written once, on top of a few read primitives that
each backend implements (`MemoryReads` for InMemoryGraphStore, `Neo4jReads`
for Neo4jGraphStore), so both backends give the same answer. It is the
detector's dirty-region expansion (`GraphStore.expand`) made visible:

- one hop = sharing an attribute, or a transfer in either direction;
- the first hop crosses attributes with at most `max_fanout` active users,
  later hops at most `far_fanout`;
- an attribute over the cap is still shown (it is linked to a region user),
  but it is not crossed, and the node says why (`stop`).

With no relationship or time filter, the users returned are exactly the
users `GraphStore.expand` returns for the same seeds and caps (tested). The
response is bounded: at most `max_nodes` nodes, with `truncated` set when the
walk had to stop early. Nothing unbounded is sent to the browser.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Protocol

from fraudsim.detectors.hubaware import hub_weight
from fraudsim.graph.store import ATTR_KINDS, Attr, InMemoryGraphStore, Link, Txn

KINDS = ("user", *ATTR_KINDS)  # user, device, card, ip
RELS = (*ATTR_KINDS, "transfer")
_NEO4J_LABEL = {"user": "User", "device": "Device", "card": "CreditCard", "ip": "IPAddress"}
_NEO4J_KEY = {"user": "user_id", "device": "device_id", "card": "card_id", "ip": "ip"}
_NEO4J_REL = {"device": "USED_DEVICE", "card": "HAS_CARD", "ip": "LOGGED_IN_FROM"}
_KIND_OF_REL = {v: k for k, v in _NEO4J_REL.items()}


class Reads(Protocol):
    """Read primitives the explorer needs from a backend."""

    def search(self, prefix: str, kinds: tuple[str, ...], limit: int) -> list[tuple[str, str]]: ...

    def user_info(self, users: set[str]) -> dict[str, tuple[bool, float | None]]:
        """(active, joined_t) of the users that exist."""
        ...

    def links_of(self, users: set[str]) -> list[Link]:
        """Attribute links of the given (active) users."""
        ...

    def users_of(self, attrs: set[Attr]) -> list[Link]:
        """Links from active users to the given attributes."""
        ...

    def degree(self, attrs: set[Attr]) -> dict[Attr, int]:
        """Active users per attribute (the degree the detector caps on)."""
        ...

    def txns_of(self, users: set[str]) -> list[Txn]:
        """Transfers sent or received by the users (both ends active)."""
        ...

    def exists(self, kind: str, entity_id: str) -> bool: ...


# ─── Backends ─────────────────────────────────────────────────────────


class MemoryReads:
    def __init__(self, store: InMemoryGraphStore) -> None:
        self.s = store

    def search(self, prefix: str, kinds: tuple[str, ...], limit: int) -> list[tuple[str, str]]:
        p = prefix.lower()
        out: list[tuple[str, str]] = []
        if "user" in kinds:
            out += [("user", u) for u, a in self.s.active.items() if a and u.lower().startswith(p)]
        out += [
            (k, a)
            for (k, a), users in self.s.attr_users.items()
            if k in kinds and users and a.lower().startswith(p)
        ]
        return sorted(out, key=lambda x: (x[1], x[0]))[:limit]

    def user_info(self, users: set[str]) -> dict[str, tuple[bool, float | None]]:
        return {u: (self.s.active[u], self.s.joined_t.get(u)) for u in users if u in self.s.active}

    def links_of(self, users: set[str]) -> list[Link]:
        return [
            Link(u, k, a, t)
            for u in users
            if self.s.active.get(u)
            for (k, a), t in self.s.user_links.get(u, {}).items()
        ]

    def users_of(self, attrs: set[Attr]) -> list[Link]:
        return [
            Link(u, k, a, t)
            for (k, a) in attrs
            for u, t in self.s.attr_users.get((k, a), {}).items()
            if self.s.active.get(u)
        ]

    def degree(self, attrs: set[Attr]) -> dict[Attr, int]:
        return {a: self.s._degree(a) for a in attrs}

    def txns_of(self, users: set[str]) -> list[Txn]:
        seen: dict[str, Txn] = {}
        for u in users:
            for t in (*self.s.out_txns.get(u, ()), *self.s.in_txns.get(u, ())):
                if self.s.active.get(t.sender) and self.s.active.get(t.receiver):
                    seen[t.txn_id] = t
        return list(seen.values())

    def exists(self, kind: str, entity_id: str) -> bool:
        if kind == "user":
            return entity_id in self.s.active
        return bool(self.s.attr_users.get((kind, entity_id)))


class Neo4jReads:
    """The same primitives in Cypher (one round trip each, indexed lookups)."""

    def __init__(self, client: Any) -> None:
        self.c = client

    def _q(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = self.c.run_query(cypher, **params)
        return rows

    def search(self, prefix: str, kinds: tuple[str, ...], limit: int) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for kind in kinds:
            label, key = _NEO4J_LABEL[kind], _NEO4J_KEY[kind]
            where = "n.active" if kind == "user" else "EXISTS { (n)<--(:User) }"
            rows = self._q(
                # Prefix match on the uniqueness-constraint index (STARTS WITH uses it);
                # lower-case prefixes match ids as generated (lower case).
                f"MATCH (n:{label}) WHERE n.{key} STARTS WITH $p AND {where} "
                f"RETURN n.{key} AS id ORDER BY id LIMIT $limit",
                p=prefix.lower(),
                limit=limit,
            )
            out += [(kind, str(r["id"])) for r in rows]
        return sorted(out, key=lambda x: (x[1], x[0]))[:limit]

    def user_info(self, users: set[str]) -> dict[str, tuple[bool, float | None]]:
        rows = self._q(
            "UNWIND $ids AS uid MATCH (u:User {user_id: uid}) "
            "RETURN u.user_id AS u, coalesce(u.active, true) AS active, u.joined_t AS t",
            ids=sorted(users),
        )
        return {
            str(r["u"]): (bool(r["active"]), None if r["t"] is None else float(r["t"]))
            for r in rows
        }

    def links_of(self, users: set[str]) -> list[Link]:
        rows = self._q(
            "UNWIND $ids AS uid "
            "MATCH (u:User {user_id: uid})-[r:USED_DEVICE|HAS_CARD|LOGGED_IN_FROM]->(a) "
            "WHERE coalesce(u.active, true) "
            "RETURN u.user_id AS u, type(r) AS rel, coalesce(a.device_id, a.card_id, a.ip) AS a, "
            "coalesce(r.t, 0.0) AS t",
            ids=sorted(users),
        )
        return [
            Link(str(r["u"]), _KIND_OF_REL[str(r["rel"])], str(r["a"]), float(r["t"])) for r in rows
        ]

    def users_of(self, attrs: set[Attr]) -> list[Link]:
        out: list[Link] = []
        for kind in ATTR_KINDS:
            ids = sorted(a for k, a in attrs if k == kind)
            if not ids:
                continue
            label, key, rel = _NEO4J_LABEL[kind], _NEO4J_KEY[kind], _NEO4J_REL[kind]
            rows = self._q(
                f"UNWIND $ids AS aid MATCH (a:{label} {{{key}: aid}})<-[r:{rel}]-(u:User) "
                "WHERE coalesce(u.active, true) "
                "RETURN u.user_id AS u, aid AS a, coalesce(r.t, 0.0) AS t",
                ids=ids,
            )
            out += [Link(str(r["u"]), kind, str(r["a"]), float(r["t"])) for r in rows]
        return out

    def degree(self, attrs: set[Attr]) -> dict[Attr, int]:
        deg = {a: 0 for a in attrs}
        for lk in self.users_of(attrs):
            deg[(lk.kind, lk.attr)] += 1
        return deg

    def txns_of(self, users: set[str]) -> list[Txn]:
        rows = self._q(
            "UNWIND $ids AS uid "
            "CALL (uid) { "
            "  MATCH (s:User {user_id: uid})-[:PERFORMED]->(t:Transaction)-[:SENT_TO]->(r:User) "
            "  RETURN s, t, r "
            "  UNION "
            "  MATCH (s:User)-[:PERFORMED]->(t:Transaction)-[:SENT_TO]->(r:User {user_id: uid}) "
            "  RETURN s, t, r "
            "} "
            "WITH DISTINCT s, t, r WHERE coalesce(s.active, true) AND coalesce(r.active, true) "
            "RETURN t.txn_id AS id, s.user_id AS s, r.user_id AS r, "
            "t.amount AS amount, coalesce(t.t, 0.0) AS t",
            ids=sorted(users),
        )
        return [
            Txn(str(r["id"]), str(r["s"]), str(r["r"]), float(r["amount"]), float(r["t"]))
            for r in rows
        ]

    def exists(self, kind: str, entity_id: str) -> bool:
        label, key = _NEO4J_LABEL[kind], _NEO4J_KEY[kind]
        # An attribute exists while some user links to it (as in the memory store).
        linked = "" if kind == "user" else " WHERE EXISTS { (n)<--(:User) }"
        rows = self._q(
            f"MATCH (n:{label} {{{key}: $id}}){linked} RETURN count(n) AS n", id=entity_id
        )
        return bool(rows and int(rows[0]["n"]))


# ─── Explorer ─────────────────────────────────────────────────────────


@dataclass(slots=True)
class Window:
    """Time filter in simulated seconds; None = open."""

    since_t: float | None = None
    until_t: float | None = None

    def ok(self, t: float) -> bool:
        return (self.since_t is None or t >= self.since_t) and (
            self.until_t is None or t <= self.until_t
        )


@dataclass(slots=True)
class Neighbourhood:
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: dict[str, dict[str, Any]] = field(default_factory=dict)
    truncated: bool = False

    def to_dict(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "params": params,
            "nodes": sorted(self.nodes.values(), key=lambda n: (n["hop"], n["kind"], n["id"])),
            "edges": sorted(self.edges.values(), key=lambda e: e["id"]),
            "truncated": self.truncated,
        }


def node_key(kind: str, entity_id: str) -> str:
    return f"{kind}:{entity_id}"


class Explorer:
    def __init__(self, reads: Reads, weight_method: str = "inverse_log_degree") -> None:
        self.r = reads
        self.weight_method = weight_method

    def weight(self, degree: int) -> float:
        return round(hub_weight(degree, self.weight_method), 4)

    def search(
        self, q: str, kinds: tuple[str, ...] = KINDS, limit: int = 20
    ) -> list[dict[str, Any]]:
        hits = self.r.search(q.strip(), kinds, limit)
        users = {i for k, i in hits if k == "user"}
        attrs = {(k, i) for k, i in hits if k != "user"}
        deg = self.r.degree(attrs) if attrs else {}
        n_links: dict[str, int] = defaultdict(int)
        for lk in self.r.links_of(users) if users else []:
            n_links[lk.user] += 1
        return [
            {
                "kind": k,
                "id": i,
                "degree": n_links[i] if k == "user" else deg.get((k, i), 0),
            }
            for k, i in hits
        ]

    def neighbourhood(
        self,
        seeds: list[tuple[str, str]],
        k: int = 1,
        max_fanout: int = 250,
        far_fanout: int = 20,
        rels: tuple[str, ...] = RELS,
        window: Window | None = None,
        max_nodes: int = 400,
    ) -> Neighbourhood:
        """
        Users within k user-hops of the seeds, the attributes linking them and
        the transfers among them. Seeds may be users or attributes (an
        attribute seed starts from its active users, whatever its degree).
        """
        win = window or Window()
        out = Neighbourhood()
        region: dict[str, int] = {}  # user -> hop it was reached at
        attr_hop: dict[Attr, int] = {}
        degree_cache: dict[Attr, int] = {}

        def deg(attrs: set[Attr]) -> None:
            todo = attrs - degree_cache.keys()
            if todo:
                degree_cache.update(self.r.degree(todo))

        def add_users(users: set[str], hop: int) -> set[str]:
            new = sorted(u for u in users if u not in region)
            room = max_nodes - len(region)
            if len(new) > room:
                out.truncated = True
                new = new[: max(room, 0)]
            for u in new:
                region[u] = hop
            return set(new)

        seed_users: set[str] = set()
        seed_attrs: set[Attr] = set()
        for kind, ident in seeds:
            if kind == "user":
                seed_users.add(ident)
            else:
                seed_attrs.add((kind, ident))
        info = self.r.user_info(seed_users) if seed_users else {}
        frontier = add_users({u for u in seed_users if info.get(u, (False, None))[0]}, 0)
        if seed_attrs:
            deg(seed_attrs)
            for a in seed_attrs:
                attr_hop[a] = 0
            frontier |= add_users({lk.user for lk in self.r.users_of(seed_attrs)}, 0)
        for hop in range(k):
            if not frontier:
                break
            cap = max_fanout if hop == 0 else far_fanout
            nxt: set[str] = set()
            links = [lk for lk in self.r.links_of(frontier) if lk.kind in rels and win.ok(lk.t)]
            attrs = {(lk.kind, lk.attr) for lk in links}
            deg(attrs)
            crossable: set[Attr] = set()
            for a in attrs:
                attr_hop.setdefault(a, hop + 1)
                if degree_cache[a] > cap:
                    node = out.nodes.setdefault(node_key(*a), {})
                    node.setdefault(
                        "stop",
                        {
                            "hop": hop + 1,
                            "degree": degree_cache[a],
                            "cap": cap,
                            "reason": (
                                f"hub: {degree_cache[a]} active users > cap {cap} at hop {hop + 1}"
                            ),
                        },
                    )
                else:
                    crossable.add(a)
            if crossable:
                nxt |= {lk.user for lk in self.r.users_of(crossable) if win.ok(lk.t)}
            if "transfer" in rels:
                for t in self.r.txns_of(frontier):
                    if win.ok(t.t):
                        nxt |= {t.sender, t.receiver}
            frontier = add_users(nxt, hop + 1)

        # Nodes and edges of the region (as GraphStore.view: every link of a region
        # user, and transfers with both ends in the region).
        users = set(region)
        uinfo = self.r.user_info(users) if users else {}
        for u in sorted(users):
            active, joined = uinfo.get(u, (True, None))
            out.nodes[node_key("user", u)] = {
                "key": node_key("user", u),
                "kind": "user",
                "id": u,
                "hop": region[u],
                "seed": u in seed_users,
                "active": active,
                "joined_t": joined,
            }
        links = [lk for lk in self.r.links_of(users) if lk.kind in rels and win.ok(lk.t)]
        attrs = {(lk.kind, lk.attr) for lk in links} | seed_attrs
        deg(attrs)
        for a in sorted(attrs):
            key = node_key(*a)
            d = degree_cache.get(a, 0)
            hop_a = attr_hop.get(a, k + 1)
            node = out.nodes.setdefault(key, {})
            node.update(
                {
                    "key": key,
                    "kind": a[0],
                    "id": a[1],
                    "hop": hop_a,
                    "seed": a in seed_attrs,
                    "degree": d,
                    "hub_weight": self.weight(d),
                    "hub": d > far_fanout,
                }
            )
            if "stop" not in node and hop_a > k and a not in seed_attrs:
                node["stop"] = {
                    "hop": hop_a,
                    "degree": d,
                    "cap": None,
                    "reason": f"depth limit k={k}",
                }
            node.setdefault("stop", None)
        if len(out.nodes) > max_nodes:
            out.truncated = True
        for lk in links:
            eid = f"link:{lk.user}:{lk.kind}:{lk.attr}"
            out.edges[eid] = {
                "id": eid,
                "source": node_key("user", lk.user),
                "target": node_key(lk.kind, lk.attr),
                "kind": lk.kind,
                "t": lk.t,
                "weight": self.weight(degree_cache.get((lk.kind, lk.attr), 0)),
            }
        if "transfer" in rels:
            for t in self.r.txns_of(users) if users else []:
                if t.sender in users and t.receiver in users and win.ok(t.t):
                    eid = f"txn:{t.txn_id}"
                    out.edges[eid] = {
                        "id": eid,
                        "source": node_key("user", t.sender),
                        "target": node_key("user", t.receiver),
                        "kind": "transfer",
                        "t": t.t,
                        "amount": t.amount,
                        "txn_id": t.txn_id,
                    }
        return out

    def entity(self, kind: str, entity_id: str, txn_limit: int = 200) -> dict[str, Any] | None:
        """Attributes, degree, links and transfers of one entity, with a timeline."""
        if not self.r.exists(kind, entity_id):
            return None
        timeline: list[dict[str, Any]] = []
        if kind == "user":
            active, joined = self.r.user_info({entity_id}).get(entity_id, (False, None))
            links = sorted(self.r.links_of({entity_id}), key=lambda lk: (lk.kind, lk.attr))
            deg = self.r.degree({(lk.kind, lk.attr) for lk in links})
            txns = sorted(self.r.txns_of({entity_id}), key=lambda t: (t.t, t.txn_id))
            sent = [t for t in txns if t.sender == entity_id]
            received = [t for t in txns if t.receiver == entity_id]
            if joined is not None:
                timeline.append({"t": joined, "type": "joined"})
            timeline += [
                {"t": lk.t, "type": "linked", "kind": lk.kind, "id": lk.attr} for lk in links
            ]
            timeline += [
                {
                    "t": t.t,
                    "type": "sent" if t.sender == entity_id else "received",
                    "amount": t.amount,
                    "counterparty": t.receiver if t.sender == entity_id else t.sender,
                    "txn_id": t.txn_id,
                }
                for t in txns
            ]
            return {
                "kind": kind,
                "id": entity_id,
                "active": active,
                "joined_t": joined,
                "degree": len(links),
                "attributes": [
                    {
                        "kind": lk.kind,
                        "id": lk.attr,
                        "t": lk.t,
                        "degree": deg[(lk.kind, lk.attr)],
                        "hub_weight": self.weight(deg[(lk.kind, lk.attr)]),
                    }
                    for lk in links
                ],
                "transactions": {
                    "sent": len(sent),
                    "received": len(received),
                    "amount_sent": round(sum(t.amount for t in sent), 2),
                    "amount_received": round(sum(t.amount for t in received), 2),
                    "items": [_txn(t, entity_id) for t in txns[-txn_limit:]],
                    "truncated": len(txns) > txn_limit,
                },
                "timeline": sorted(timeline, key=lambda e: (e["t"], e["type"]))[-txn_limit:],
            }
        attr = (kind, entity_id)
        holders = sorted(self.r.users_of({attr}), key=lambda lk: (lk.t, lk.user))
        d = len(holders)
        timeline += [{"t": lk.t, "type": "linked", "kind": "user", "id": lk.user} for lk in holders]
        return {
            "kind": kind,
            "id": entity_id,
            "degree": d,
            "hub_weight": self.weight(d),
            "hub_weight_method": self.weight_method,
            "users": [{"id": lk.user, "t": lk.t} for lk in holders],
            "timeline": timeline,
        }


def _txn(t: Txn, me: str) -> dict[str, Any]:
    return {
        "txn_id": t.txn_id,
        "t": t.t,
        "direction": "out" if t.sender == me else "in",
        "counterparty": t.receiver if t.sender == me else t.sender,
        "amount": t.amount,
    }
