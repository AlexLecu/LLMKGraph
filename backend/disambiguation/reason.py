import logging
from owlready2 import get_ontology, sync_reasoner
import requests
import os


ONTOLOGY_PATH = "amd_ontology.rdf"
REASONED_ONT_PATH = "amd_ontology_reasoned.rdf"
GRAPHDB_URL = "http://localhost:7200"


def get_ontology_from_graphdb(repo_id):
    endpoint_url = f"{GRAPHDB_URL}/repositories/{repo_id}"
    sparql_query = """
        CONSTRUCT {
          ?s ?p ?o.
        } WHERE {
          ?s ?p ?o.
        }
    """

    headers = {"Accept": "application/rdf+xml"}

    logging.info("Exporting ontology from GraphDB...")
    response = requests.post(endpoint_url, data={"query": sparql_query}, headers=headers)
    if response.status_code == 200:
        with open(ONTOLOGY_PATH, "wb") as f:
            f.write(response.content)
        logging.info(f"RDF exported successfully to {ONTOLOGY_PATH}!")
    else:
        error_msg = f"Failed to retrieve data: {response.status_code} {response.text}"
        logging.error(error_msg)
        raise Exception(error_msg)


def reason_ontology():
    if not os.path.exists(ONTOLOGY_PATH):
        error_msg = f"Input ontology file not found at {ONTOLOGY_PATH}"
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)

    logging.info("Loading ontology for reasoning...")
    ont = get_ontology(f"file://{os.path.abspath(ONTOLOGY_PATH)}").load()

    logging.info("Running reasoner...")
    with ont:
        sync_reasoner()

    ont.save(file=REASONED_ONT_PATH, format="rdfxml")
    logging.info(f"Reasoned ontology saved to {REASONED_ONT_PATH}.")


def update_graph(repo_id):
    update_endpoint = f"{GRAPHDB_URL}/repositories/{repo_id}/statements"
    named_graph_uri = "http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD/"
    drop_query = "DROP ALL"

    logging.info("Clearing the repository...")
    response = requests.post(
        update_endpoint,
        data={"update": drop_query},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    if response.status_code == 204:
        logging.info("Repository cleared successfully.")
    else:
        error_msg = f"Failed to clear repository: {response.status_code} {response.text}"
        logging.error(error_msg)
        raise Exception(error_msg)

    named_graph_endpoint = f"{update_endpoint}?context=<{named_graph_uri}>"
    logging.info(f"Uploading reasoned ontology from {REASONED_ONT_PATH} into graph {named_graph_uri}...")
    if not os.path.exists(REASONED_ONT_PATH):
        error_msg = f"Reasoned ontology file not found at {REASONED_ONT_PATH}"
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)

    with open(REASONED_ONT_PATH, "rb") as f:
        headers = {"Content-Type": "application/rdf+xml"}
        response = requests.post(named_graph_endpoint, data=f, headers=headers)

    if response.status_code == 204:
        logging.info(f"Ontology successfully imported into the named graph {named_graph_uri}!")
    else:
        error_msg = f"Failed to import ontology into named graph {named_graph_uri}: {response.status_code} {response.text}"
        logging.error(error_msg)
        raise Exception(error_msg)


def reason_and_update(repo_id):
    get_ontology_from_graphdb(repo_id)
    reason_ontology()
    update_graph(repo_id)
