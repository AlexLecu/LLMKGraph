import logging
from owlready2 import get_ontology, sync_reasoner
import requests
import os

GRAPHDB_URL = os.getenv('GRAPHDB_URL', 'http://localhost:7200')
RUN_MODE = os.getenv('RUN_MODE', 'local').lower()


def get_ontology_from_graphdb(repo_id, ontology_path):
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
        with open(ontology_path, "wb") as f:
            f.write(response.content)
        logging.info(f"RDF exported successfully to {ontology_path}!")
    else:
        error_msg = f"Failed to retrieve data: {response.status_code} {response.text}"
        logging.error(error_msg)
        raise Exception(error_msg)


def reason_ontology(ontology_path, reasoned_ont_path):
    if not os.path.exists(ontology_path):
        error_msg = f"Input ontology file not found at {ontology_path}"
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)

    logging.info("Loading ontology for reasoning...")
    ont = get_ontology(f"file://{os.path.abspath(ontology_path)}").load()

    logging.info("Running reasoner...")
    with ont:
        sync_reasoner()

    ont.save(file=reasoned_ont_path, format="rdfxml")
    logging.info(f"Reasoned ontology saved to {reasoned_ont_path}.")


def update_graph(repo_id, reasoned_ont_path):
    update_endpoint = f"{GRAPHDB_URL}/repositories/{repo_id}/statements"
    named_graph_uri = "http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD/"
    drop_query = "CLEAR ALL"

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
    logging.info(f"Uploading reasoned ontology from {reasoned_ont_path} into graph {named_graph_uri}...")
    if not os.path.exists(reasoned_ont_path):
        error_msg = f"Reasoned ontology file not found at {reasoned_ont_path}"
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)

    with open(reasoned_ont_path, "rb") as f:
        headers = {"Content-Type": "application/rdf+xml"}
        response = requests.post(named_graph_endpoint, data=f, headers=headers)

    if response.status_code == 204:
        logging.info(f"Ontology successfully imported into the named graph {named_graph_uri}!")
    else:
        error_msg = f"Failed to import ontology into named graph {named_graph_uri}: {response.status_code} {response.text}"
        logging.error(error_msg)
        raise Exception(error_msg)


def reason_and_update(repo_id):
    if RUN_MODE == 'docker':
        ontology_path = f"/app/data/amd_ontology_{repo_id}.rdf"
        reasoned_ont_path = f"/app/data/amd_ontology_reasoned_{repo_id}.rdf"
    else:
        ontology_path = f"amd_ontology_{repo_id}.rdf"
        reasoned_ont_path = f"amd_ontology_reasoned_{repo_id}.rdf"

    get_ontology_from_graphdb(repo_id, ontology_path)
    reason_ontology(ontology_path, reasoned_ont_path)
    update_graph(repo_id, reasoned_ont_path)
