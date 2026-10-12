"""Graph-comparison statistics behind /api/evaluation (the Evaluation page).

Compares repositories built from the same abstracts with different extraction
LLMs: size, connectivity, relation and entity-type mix, and how many
(subject, relation, object) triples the models agree on. Same metrics as
streamlit/streamlit_app_evaluation.py, computed once and served as JSON so the
page works over plain HTTP.
"""
import os
import time
from collections import Counter

import networkx as nx
import requests

GRAPHDB_URL = os.getenv("GRAPHDB_URL", "http://localhost:7200").rstrip("/")
DEFAULT_REPOS = [r.strip() for r in os.getenv(
    "EVAL_REPOS", "amd_repo_gpt_35,amd_repo_mistral,amd_repo_gpt_4o1_mini").split(",") if r.strip()]
CACHE_SECONDS = int(os.getenv("EVAL_CACHE_SECONDS", "600"))

PREFIXES = """
PREFIX ont: <http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#>
"""
# One row per stored relation (a triple extracted from several abstracts counts each time)
RELATIONS_QUERY = PREFIXES + """
SELECT ?s ?p ?o WHERE {
  ?r a ont:RELATION ; ont:relation_subject ?s ; ont:relation_predicate ?p ; ont:relation_object ?o .
}"""
# Explicit (not inferred) entity types of the entities taking part in a relation
TYPES_QUERY = PREFIXES + """
SELECT DISTINCT ?e ?t FROM <http://www.ontotext.com/explicit> WHERE {
  ?r a ont:RELATION ; ont:relation_subject|ont:relation_object ?e .
  ?e a ?t .
  FILTER(STRSTARTS(STR(?t), STR(ont:)))
}"""

DEGREE_BUCKETS = [(1, 1, "1"), (2, 2, "2"), (3, 5, "3–5"), (6, 10, "6–10"), (11, 20, "11–20"), (21, None, "21+")]

_cache: dict = {}


def _local(uri):
    return uri.rsplit("#", 1)[-1] if "#" in uri else uri.rstrip("/").rsplit("/", 1)[-1]


def _select(repo_id, query):
    r = requests.post(f"{GRAPHDB_URL}/repositories/{repo_id}", data={"query": query},
                      headers={"Accept": "application/sparql-results+json"}, timeout=120)
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def _repo_stats(repo_id):
    rows = [(_local(b["s"]["value"]), _local(b["p"]["value"]), _local(b["o"]["value"]))
            for b in _select(repo_id, RELATIONS_QUERY)]
    types = _select(repo_id, TYPES_QUERY)

    graph = nx.DiGraph()
    graph.add_edges_from((s, o) for s, _, o in rows)
    degrees = dict(graph.degree())
    n = graph.number_of_nodes()

    buckets = Counter()
    for d in degrees.values():
        for lo, hi, label in DEGREE_BUCKETS:
            if d >= lo and (hi is None or d <= hi):
                buckets[label] += 1
                break

    return {
        "relations": len(rows),
        "triples": set(rows),
        "entities": n,
        "links": graph.number_of_edges(),
        "avg_degree": round(sum(degrees.values()) / n, 2) if n else 0,
        "clustering": round(nx.average_clustering(graph.to_undirected()), 4) if n else 0,
        "relation_types": dict(Counter(p for _, p, _ in rows).most_common()),
        "entity_types": dict(Counter(_local(b["t"]["value"]) for b in types).most_common()),
        "degree_distribution": {label: buckets.get(label, 0) for _, _, label in DEGREE_BUCKETS},
        "top_entities": [{"name": e, "degree": d}
                         for e, d in sorted(degrees.items(), key=lambda kv: (-kv[1], kv[0]))[:10]],
    }


def compare(repo_ids=None):
    repo_ids = tuple(repo_ids or DEFAULT_REPOS)
    hit = _cache.get(repo_ids)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]

    stats = {rid: _repo_stats(rid) for rid in repo_ids}
    triples = {rid: s.pop("triples") for rid, s in stats.items()}
    for rid, s in stats.items():
        others = set().union(*(triples[o] for o in repo_ids if o != rid))
        s["unique_triples"] = len(triples[rid])
        s["only_here"] = len(triples[rid] - others)
    result = {
        "repositories": list(repo_ids),
        "stats": stats,
        "overlap": {a: {b: len(triples[a] & triples[b]) for b in repo_ids} for a in repo_ids},
        "common_to_all": len(set.intersection(*triples.values())) if triples else 0,
    }
    _cache[repo_ids] = (time.time(), result)
    return result
