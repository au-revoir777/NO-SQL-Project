"""
P6 integration: the explorer gives the same answers from Neo4j (Cypher) as from
the in-memory store, on the course seed graph. Skipped without Neo4j.

Run with: pytest -m integration tests/test_integration_explorer.py
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from fraudsim.graph.explore import Explorer, MemoryReads, Neo4jReads, Window
from fraudsim.graph.neo4j_client import Neo4jClient
from fraudsim.graph.store import InMemoryGraphStore
from fraudsim.simulator.event_generator import EventGenerator

pytestmark = pytest.mark.integration

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")


@pytest.fixture(scope="module")
def explorers() -> Iterator[tuple[Explorer, Explorer, InMemoryGraphStore]]:
    if not NEO4J_PASSWORD:
        pytest.skip("NEO4J_PASSWORD is not set (see .env.example)")
    client = Neo4jClient(uri=NEO4J_URI, password=NEO4J_PASSWORD)
    try:
        client._driver.verify_connectivity()
    except Exception as e:  # pragma: no cover - environment dependent
        pytest.skip(f"Neo4j not reachable at {NEO4J_URI}: {e}")
    client.wipe()
    client.ensure_schema()
    events = EventGenerator(seed=42, run_id="course").generate_seed_events()
    client.write_events_batch(events)
    store = InMemoryGraphStore()
    store.apply(events)
    yield Explorer(MemoryReads(store)), Explorer(Neo4jReads(client)), store
    client.wipe()
    client.close()


def test_search_and_entities_match(
    explorers: tuple[Explorer, Explorer, InMemoryGraphStore],
) -> None:
    mem, neo, _ = explorers
    for q in ("u0", "u2", "device_00", "card_005", "ip_0", "nothing"):
        assert neo.search(q) == mem.search(q), q
    for kind, ident in [
        ("user", "u01"),
        ("user", "u21"),
        ("device", "device_007"),
        ("card", "card_005"),
        ("ip", "ip_001"),
        ("ip", "ip_004"),
    ]:
        assert neo.entity(kind, ident) == mem.entity(kind, ident), (kind, ident)
    assert neo.entity("device", "device_999") is None


@pytest.mark.parametrize(("max_fanout", "far_fanout"), [(250, 20), (10, 3), (2, 2)])
@pytest.mark.parametrize("k", [1, 2, 3])
def test_neighbourhoods_match(
    explorers: tuple[Explorer, Explorer, InMemoryGraphStore],
    k: int,
    max_fanout: int,
    far_fanout: int,
) -> None:
    mem, neo, store = explorers
    seeds = [("user", u) for u in sorted(store.active)] + [
        ("device", "device_007"),
        ("ip", "ip_001"),
    ]
    for seed in seeds:
        a = mem.neighbourhood([seed], k, max_fanout, far_fanout).to_dict({})
        b = neo.neighbourhood([seed], k, max_fanout, far_fanout).to_dict({})
        assert b == a, seed


def test_filtered_neighbourhoods_match(
    explorers: tuple[Explorer, Explorer, InMemoryGraphStore],
) -> None:
    mem, neo, store = explorers
    times = sorted({t for links in store.user_links.values() for t in links.values()})
    mid = times[len(times) // 2]
    for rels in (("device",), ("card", "transfer"), ("ip",)):
        for window in (Window(), Window(since_t=mid), Window(until_t=mid)):
            a = mem.neighbourhood([("user", "u13")], 2, rels=rels, window=window).to_dict({})
            b = neo.neighbourhood([("user", "u13")], 2, rels=rels, window=window).to_dict({})
            assert b == a, (rels, window)
