"""
Entity and graph explorer (P6): hand-built micro-graphs and the course seed graph.

The k-hop neighbourhood must return exactly the users the detector's
dirty-region expansion (GraphStore.expand) returns for the same seeds and caps,
and say where it stopped at a hub.
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from auth_fixtures import setup_app_db, sign_in
from fastapi.testclient import TestClient

from fraudsim.api.main import app
from fraudsim.api.v1.routers.explorer import course_store
from fraudsim.graph.explore import Explorer, MemoryReads, Window
from fraudsim.graph.store import InMemoryGraphStore
from fraudsim.simulator.event_generator import EventGenerator
from fraudsim.types import Event, EventType

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def ev(seq: int, etype: EventType, at: float = 0.0, **payload: object) -> Event:
    return Event(f"e{seq}", etype, T0 + timedelta(seconds=at), dict(payload), "test", seq)


def build(events: list[Event]) -> tuple[InMemoryGraphStore, Explorer]:
    store = InMemoryGraphStore()
    store.apply(events)
    return store, Explorer(MemoryReads(store))


def micro() -> list[Event]:
    """
    u1 -dev d1- u2 -card c1- u3 ; u3 sends 100 to u4 at t=50 ;
    hub ip h1 shared by u1, u5, u6, u7, u8 (degree 5) ; u9 isolated.
    """
    e: list[Event] = []
    n = 0

    def add(etype: EventType, at: float = 0.0, **p: object) -> None:
        nonlocal n
        n += 1
        e.append(ev(n, etype, at, **p))

    for u in ("u1", "u2", "u3", "u4", "u5", "u6", "u7", "u8", "u9"):
        add(EventType.USER_JOIN, user_id=u, name=u)
    add(EventType.DEVICE_LINK, 10, user_id="u1", device_id="d1")
    add(EventType.DEVICE_LINK, 11, user_id="u2", device_id="d1")
    add(EventType.CARD_LINK, 20, user_id="u2", card_id="c1")
    add(EventType.CARD_LINK, 21, user_id="u3", card_id="c1")
    for i, u in enumerate(("u1", "u5", "u6", "u7", "u8")):
        add(EventType.IP_LINK, 30 + i, user_id=u, ip="h1")
    add(EventType.TRANSACTION, 50, txn_id="x1", sender="u3", receiver="u4", amount=100.0)
    return e


def users_of(nb_dict: dict[str, object]) -> set[str]:
    return {n["id"] for n in nb_dict["nodes"] if n["kind"] == "user"}  # type: ignore[index, attr-defined]


def test_micro_graph_exact_nodes_and_edges() -> None:
    _, ex = build(micro())
    nb = ex.neighbourhood([("user", "u1")], k=1, max_fanout=4, far_fanout=4).to_dict({})
    nodes = {n["key"]: n for n in nb["nodes"]}
    # Hop 1 crosses d1 (degree 2) to u2; the hub h1 (5 > cap 4) is shown but not crossed.
    assert set(nodes) == {"user:u1", "user:u2", "device:d1", "ip:h1", "card:c1"}
    assert nodes["user:u1"]["hop"] == 0 and nodes["user:u1"]["seed"]
    assert nodes["user:u2"]["hop"] == 1
    assert nodes["ip:h1"]["stop"]["reason"] == "hub: 5 active users > cap 4 at hop 1"
    assert nodes["ip:h1"]["degree"] == 5
    # c1 belongs to the region user u2 but lies beyond k=1.
    assert nodes["card:c1"]["stop"]["reason"] == "depth limit k=1"
    assert nodes["device:d1"]["stop"] is None
    edges = {(e["source"], e["target"], e["kind"]) for e in nb["edges"]}
    assert edges == {
        ("user:u1", "device:d1", "device"),
        ("user:u2", "device:d1", "device"),
        ("user:u1", "ip:h1", "ip"),
        ("user:u2", "card:c1", "card"),
    }
    weights = {e["target"]: e["weight"] for e in nb["edges"]}
    assert weights["device:d1"] == round(1 / math.log(3), 4)  # inverse log degree
    assert weights["ip:h1"] < weights["device:d1"]  # hubs weigh less
    assert not nb["truncated"]


def test_micro_graph_k3_reaches_the_transfer_and_hub_users_with_a_higher_cap() -> None:
    _, ex = build(micro())
    nb = ex.neighbourhood([("user", "u1")], k=3, max_fanout=10, far_fanout=1).to_dict({})
    # First hop may cross the hub (5 <= 10); later hops only cross degree <= 1, so
    # c1 (degree 2) stops the walk at hop 2 and u3/u4 are not reached.
    assert users_of(nb) == {"u1", "u2", "u5", "u6", "u7", "u8"}
    nodes = {n["key"]: n for n in nb["nodes"]}
    assert nodes["card:c1"]["stop"]["reason"] == "hub: 2 active users > cap 1 at hop 2"
    nb = ex.neighbourhood([("user", "u1")], k=3, max_fanout=10, far_fanout=2).to_dict({})
    assert users_of(nb) == {"u1", "u2", "u3", "u4", "u5", "u6", "u7", "u8"}
    transfer = [e for e in nb["edges"] if e["kind"] == "transfer"]
    assert transfer == [
        {
            "id": "txn:x1",
            "source": "user:u3",
            "target": "user:u4",
            "kind": "transfer",
            "t": T0.timestamp() + 50,
            "amount": 100.0,
            "txn_id": "x1",
        }
    ]


def test_relationship_and_time_filters() -> None:
    _, ex = build(micro())
    only_cards = ex.neighbourhood([("user", "u2")], k=2, rels=("card",)).to_dict({})
    assert users_of(only_cards) == {"u2", "u3"}
    assert {e["kind"] for e in only_cards["edges"]} == {"card"}
    # Links made before t0+15 (d1 links at 10 and 11) are outside the window.
    late = ex.neighbourhood(
        [("user", "u2")], k=1, window=Window(since_t=T0.timestamp() + 15)
    ).to_dict({})
    assert users_of(late) == {"u2", "u3"}


def test_attribute_seed_and_node_cap() -> None:
    _, ex = build(micro())
    nb = ex.neighbourhood([("ip", "h1")], k=0).to_dict({})
    assert users_of(nb) == {"u1", "u5", "u6", "u7", "u8"}
    assert {n["key"] for n in nb["nodes"] if n["seed"]} == {"ip:h1"}
    capped = ex.neighbourhood([("ip", "h1")], k=2, max_nodes=3).to_dict({})
    assert capped["truncated"]
    assert len(users_of(capped)) == 3


def test_entity_details() -> None:
    _, ex = build(micro())
    u3 = ex.entity("user", "u3")
    assert u3 is not None
    assert u3["degree"] == 1
    assert u3["attributes"] == [
        {"kind": "card", "id": "c1", "t": T0.timestamp() + 21, "degree": 2, "hub_weight": 0.9102}
    ]
    assert u3["transactions"]["sent"] == 1 and u3["transactions"]["amount_sent"] == 100.0
    assert [e["type"] for e in u3["timeline"]] == ["joined", "linked", "sent"]
    h1 = ex.entity("ip", "h1")
    assert h1 is not None and h1["degree"] == 5
    assert [u["id"] for u in h1["users"]] == ["u1", "u5", "u6", "u7", "u8"]
    assert ex.entity("device", "nope") is None


# ─── Course seed graph (seed.py through the EventGenerator bridge) ─────


@pytest.fixture(scope="module")
def course() -> tuple[InMemoryGraphStore, Explorer]:
    return build(EventGenerator(seed=42, run_id="seed").generate_seed_events())


def test_course_graph_rings_as_in_the_readme(course: tuple[InMemoryGraphStore, Explorer]) -> None:
    _, ex = course
    assert ex.search("device_007") == [{"kind": "device", "id": "device_007", "degree": 4}]
    dev = ex.entity("device", "device_007")
    assert dev is not None and [u["id"] for u in dev["users"]] == ["u01", "u02", "u03", "u04"]
    card = ex.entity("card", "card_005")
    assert card is not None and [u["id"] for u in card["users"]] == ["u10", "u11", "u12"]
    hub = ex.entity("ip", "ip_001")
    assert hub is not None and hub["degree"] == 12
    assert [h["kind"] for h in ex.search("u0", limit=3)] == ["user"] * 3
    assert {h["kind"] for h in ex.search("ip_00", kinds=("ip",))} == {"ip"}


@pytest.mark.parametrize(("max_fanout", "far_fanout"), [(250, 20), (10, 3), (2, 2), (1, 1)])
@pytest.mark.parametrize("k", [1, 2, 3])
def test_neighbourhood_users_equal_the_detector_expansion(
    course: tuple[InMemoryGraphStore, Explorer], k: int, max_fanout: int, far_fanout: int
) -> None:
    store, ex = course
    for u in sorted(u for u, active in store.active.items() if active):
        expected = store.expand({u}, k, max_fanout, float("-inf"), far_fanout=far_fanout)
        nb = ex.neighbourhood([("user", u)], k, max_fanout, far_fanout).to_dict({})
        assert users_of(nb) == expected, (u, k, max_fanout, far_fanout)
        # Every attribute over the cap that the walk reached says so.
        for n in nb["nodes"]:
            if n["kind"] != "user" and n["stop"] and n["stop"]["cap"] is not None:
                assert n["degree"] > n["stop"]["cap"]


# ─── API ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def api(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    tmp = tmp_path_factory.mktemp("p6")
    mp = pytest.MonkeyPatch()
    mp.setenv("FRAUDSIM_RUNS_DIR", str(tmp / "runs"))
    users = setup_app_db(tmp, mp)
    with TestClient(app, base_url="https://testserver") as c:
        sign_in(c, *users["analyst"])
        yield {"c": c, "tmp": tmp}
    mp.undo()


def test_api_course_graph_search_entity_and_neighbourhood(api: dict[str, Any]) -> None:
    c = api["c"]
    hits = c.get("/api/v1/entities/search", params={"q": "device_007", "source": "course"}).json()
    assert hits == [{"kind": "device", "id": "device_007", "degree": 4}]
    dev = c.get("/api/v1/entities/device/device_007", params={"source": "course"}).json()
    assert [u["id"] for u in dev["users"]] == ["u01", "u02", "u03", "u04"]
    assert dev["is_hub"] is False and dev["hub_weight"] == round(1 / math.log(5), 4)
    hub = c.get("/api/v1/entities/ip/ip_001", params={"source": "course"}).json()
    assert hub["degree"] == 12 and hub["is_hub"] is False  # far_fanout default is 20
    nb = c.get(
        "/api/v1/graph/neighbourhood",
        params={"seed": "user:u01", "k": 2, "source": "course", "far_fanout": 3},
    ).json()
    keys = {n["key"]: n for n in nb["nodes"]}
    assert {"user:u02", "user:u03", "user:u04", "device:device_007"} <= set(keys)
    assert nb["params"]["far_fanout"] == 3 and nb["params"]["max_fanout"] == 250
    # Same users as the detector's expansion with those caps.
    store = course_store()
    assert {n["id"] for n in nb["nodes"] if n["kind"] == "user"} == store.expand(
        {"u01"}, 2, 250, float("-inf"), far_fanout=3
    )


def test_api_errors(api: dict[str, Any]) -> None:
    c = api["c"]
    r = c.get("/api/v1/entities/device/nope", params={"source": "course"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = c.get("/api/v1/graph/neighbourhood", params={"seed": "bogus", "source": "course"})
    assert r.status_code == 422
    r = c.get("/api/v1/graph/neighbourhood", params={"seed": "user:u01", "k": 4})
    assert r.status_code == 422
    r = c.get("/api/v1/entities/search", params={"q": "u", "source": "neo4j"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "source_unavailable"


def test_api_run_source_links_alerts_and_shows_rings_over_time(api: dict[str, Any]) -> None:
    c = api["c"]
    c.post("/api/v1/runs", json={"scenario": "baseline", "seed": 7, "speed_multiplier": 0})
    deadline = time.monotonic() + 120
    while c.get("/api/v1/runs/current").json()["status"] != "finished":
        assert time.monotonic() < deadline
        time.sleep(0.2)
    alert = c.get("/api/v1/alerts").json()["items"][0]
    detail = c.get(f"/api/v1/alerts/{alert['id']}").json()
    member = detail["members"][0]
    ent = c.get(f"/api/v1/entities/user/{member}").json()
    assert alert["id"] in {a["id"] for a in ent["alerts"]}
    assert alert["alert_ref"] in {r["ring_id"] for r in ent["rings"]}
    assert ent["transactions"] is not None and ent["timeline"][0]["type"] == "joined"

    ring = c.get(f"/api/v1/graph/rings/{alert['alert_ref']}").json()
    assert ring["members"] == sorted(detail["members"])
    assert ring["timeline"][0]["change"] == "created"
    assert ring["timeline"][-1]["members"] == ring["members"]
    for before, after in zip(ring["timeline"], ring["timeline"][1:], strict=False):
        assert set(after["members"]) == (set(before["members"]) | set(after["added"])) - set(
            after["removed"]
        )
    assert all(len(a["members"]) >= 2 for a in ring["shared_attributes"])
    assert c.get("/api/v1/graph/rings/R999999").status_code == 404
