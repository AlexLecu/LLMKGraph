"""In-process triplestore that stands in for GraphDB.

Activated with EMBEDDED_STORE=1. The rest of the backend keeps talking SPARQL
over HTTP (SPARQLWrapper / requests) to GRAPHDB_URL, so this module exposes the
three GraphDB endpoints the code uses, backed by rdflib:

    GET  /rest/repositories                 -> [{"id": ...}]
    GET/POST /repositories/<repo>           -> SPARQL query, JSON results
    POST /repositories/<repo>/statements    -> SPARQL update

Repositories are loaded once at start-up from EMBEDDED_REPOS, a JSON list such as

    [{"id": "amd_demo",
      "ontology": "../data/CausalAMD_ont.rdf",
      "relations": ["../data/Extracted_Relations/2025-03-12/Deepseek_V3_Relations_ct.json"]}]

Relations JSON files use the extraction format (entity1_name, relation_type, ...)
and are cleaned with the same `refine_relations` as the GraphDB import path.
Meant for demos (read-only or single instance); not a replacement for GraphDB.
"""
import json
import logging
import os
import uuid

from flask import Blueprint, Response, jsonify, request
from rdflib import ConjunctiveGraph, Namespace, RDF, URIRef

from disambiguation.disambiguation import refine_relations, sanitize_entity_name

logger = logging.getLogger(__name__)

ONT = Namespace("http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#")
PROV = Namespace("http://www.w3.org/ns/prov#")
DATA_GRAPH = URIRef("http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD/")

_repos: dict[str, ConjunctiveGraph] = {}

bp = Blueprint("embedded_store", __name__)


def _add_relations(graph: ConjunctiveGraph, relations: list[dict]) -> int:
    """Mirror of bulk_relations.create_sparql_queries_for_bulk_import, as triples."""
    g = graph.get_context(DATA_GRAPH)
    count = 0
    for r in refine_relations(relations):
        try:
            subject = ONT[sanitize_entity_name(r["entity1_name"])]
            obj = ONT[sanitize_entity_name(r["entity2_name"])]
            predicate = ONT[sanitize_entity_name(r["relation_type"])]
            s_type = ONT[sanitize_entity_name(r["entity1_type"]).upper()]
            o_type = ONT[sanitize_entity_name(r["entity2_type"]).upper()]
        except (KeyError, TypeError):
            continue
        rel = ONT[f"REL_{uuid.uuid4()}"]
        g.add((rel, RDF.type, ONT.RELATION))
        g.add((rel, ONT.relation_subject, subject))
        g.add((rel, ONT.relation_predicate, predicate))
        g.add((rel, ONT.relation_object, obj))
        pub_id = r.get("pub_id")
        if pub_id:
            pub = ONT[sanitize_entity_name(pub_id)]
            g.add((rel, PROV.wasDerivedFrom, pub))
            g.add((pub, RDF.type, ONT.PUBLICATION))
        g.add((subject, RDF.type, s_type))
        g.add((obj, RDF.type, o_type))
        count += 1
    return count


def load_repositories(spec: list[dict], base_dir: str) -> None:
    for repo in spec:
        graph = ConjunctiveGraph()
        ontology = repo.get("ontology")
        if ontology:
            graph.parse(os.path.join(base_dir, ontology))
        total = 0
        for path in repo.get("relations", []):
            with open(os.path.join(base_dir, path), encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data = data.get("relations", [])
            total += _add_relations(graph, data)
        _repos[repo["id"]] = graph
        logger.info("embedded repository %s: %d relations, %d triples", repo["id"], total, len(graph))


def load_from_env() -> None:
    spec = json.loads(os.environ.get("EMBEDDED_REPOS", "[]"))
    base_dir = os.environ.get("EMBEDDED_BASE_DIR", os.path.dirname(os.path.abspath(__file__)))
    quiet = logging.getLogger("disambiguation").level
    logging.getLogger().setLevel(logging.WARNING)  # refine_relations is chatty
    try:
        load_repositories(spec, base_dir)
    finally:
        logging.getLogger().setLevel(logging.INFO)
        logging.getLogger("disambiguation").setLevel(quiet)


@bp.route("/rest/repositories", methods=["GET"])
def list_repositories():
    return jsonify([{"id": rid, "type": "embedded"} for rid in _repos])


@bp.route("/repositories/<repo_id>", methods=["GET", "POST"])
def query_repository(repo_id):
    graph = _repos.get(repo_id)
    if graph is None:
        return jsonify({"error": f"unknown repository {repo_id}"}), 404
    query = request.values.get("query") or (request.get_data(as_text=True) if request.method == "POST" else "")
    if not query:
        return jsonify({"error": "missing query"}), 400
    try:
        result = graph.query(query)
    except Exception as exc:  # malformed SPARQL
        return jsonify({"error": f"SPARQL error: {exc}"}), 400
    if result.type in ("SELECT", "ASK"):
        return Response(result.serialize(format="json"), mimetype="application/sparql-results+json")
    return Response(result.serialize(format="xml"), mimetype="application/rdf+xml")


@bp.route("/repositories/<repo_id>/statements", methods=["POST"])
def update_repository(repo_id):
    graph = _repos.get(repo_id)
    if graph is None:
        return jsonify({"error": f"unknown repository {repo_id}"}), 404
    update = request.values.get("update") or request.values.get("query") or request.get_data(as_text=True)
    if not update:
        return jsonify({"error": "missing update"}), 400
    try:
        graph.update(update)
    except Exception as exc:
        return jsonify({"error": f"SPARQL update error: {exc}"}), 400
    return "", 204
