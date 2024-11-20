from owlready2 import *
from SPARQLWrapper import SPARQLWrapper, JSON, POST
import rdflib

ONTOLOGY_PATH = "/app/data/amd_ontology.rdf"
REASONED_ONT_PATH = "/app/data/amd_ontology_reasoned.rdf"


def get_ontology_from_graphdb(repo_id):
    sparql = SPARQLWrapper(f"http://graphdb:7200/repositories/{repo_id}")
    sparql.setQuery("""
        SELECT ?subject ?predicate ?object
        WHERE {
            ?subject ?predicate ?object .
        }
    """)

    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    ont = rdflib.Graph()

    for result in results["results"]["bindings"]:
        s = rdflib.URIRef(result["subject"]["value"])
        p = rdflib.URIRef(result["predicate"]["value"])
        o = rdflib.URIRef(result["object"]["value"])

        ont.add((s, p, o))

    ont.serialize(destination=ONTOLOGY_PATH, format="application/rdf+xml")


def reason_ontology():
    ont = get_ontology(ONTOLOGY_PATH).load()

    with ont:
        sync_reasoner(ont)
    ont.save(file=REASONED_ONT_PATH, format="rdfxml")


def update_graph(repo_id):
    sparql = SPARQLWrapper(f"http://graphdb:7200/repositories/{repo_id}/statements")
    clear_graph_query = "CLEAR GRAPH <http://amddata.org/amd/>"

    sparql.setQuery(clear_graph_query)
    sparql.setMethod(POST)
    sparql.query()

    g = rdflib.Graph()
    g.parse(REASONED_ONT_PATH, format="application/rdf+xml")
    triples = g.serialize(format='nt')

    sparql_query = "INSERT DATA { GRAPH <http://amddata.org/amd/> { " + triples + " } }"

    sparql.setQuery(sparql_query)
    sparql.query()


def reason_and_update(repo_id):
    get_ontology_from_graphdb(repo_id)
    reason_ontology()
    update_graph(repo_id)
