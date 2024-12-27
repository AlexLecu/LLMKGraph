import os
import requests
import logging
import pandas as pd

GRAPHDB_URL = os.getenv('GRAPHDB_URL', 'http://localhost:7200')
REPO_ID = "amd_repo_gpt_4o1_mini"


def execute_sparql_query(repo_id, sparql_query):
    endpoint_url = f"{GRAPHDB_URL}/repositories/{repo_id}"

    headers = {
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    params = {
        "query": sparql_query
    }

    logging.info("Executing SPARQL SELECT query...")
    response = requests.post(endpoint_url, data=params, headers=headers)

    if response.status_code != 200:
        logging.error(f"Failed to execute SPARQL query: {response.status_code} - {response.text}")
        response.raise_for_status()

    logging.info("SPARQL query executed successfully.")
    return response.json()


def process_sparql_results(sparql_results):
    data = []
    for result in sparql_results["results"]["bindings"]:
        entity1_type = extract_fragment(result.get("entity1_type", {}).get("value", ""))
        entity1 = extract_fragment(result.get("entity1", {}).get("value", ""))
        predicate = extract_fragment(result.get("predicate", {}).get("value", ""))
        entity2_type = extract_fragment(result.get("entity2_type", {}).get("value", ""))
        entity2 = extract_fragment(result.get("entity2", {}).get("value", ""))
        publication = extract_fragment(
            result.get("publication", {}).get("value", "")) if "publication" in result else None

        data.append({
            'Subject Type': entity1_type,
            'Subject': entity1,
            'Relation': predicate,
            'Object Type': entity2_type,
            'Object': entity2,
            'Source Publication': publication
        })
    return data


def extract_fragment(uri):
    if not uri:
        return ""
    if "#" in uri:
        return uri.split("#")[-1]
    else:
        return uri.rstrip("/").split("/")[-1]


def main():
    sparql_query = """
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX : <http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#>

    SELECT DISTINCT
        ?entity1_type 
        ?entity1 
        ?predicate 
        ?entity2_type 
        ?entity2 
        ?publication
    WHERE {
        # Match any relation
        ?relation :relation_subject ?entity1 ;
                  :relation_predicate ?predicate ;
                  :relation_object ?entity2 .

        # Get the specific type of entity1
        ?entity1 rdf:type ?entity1_type .

        # Ensure entity1_type is not the general 'Entity'
        FILTER (?entity1_type != :Entity)

        # Get the specific type of entity2
        ?entity2 rdf:type ?entity2_type .

        # Ensure entity2_type is not the general 'Entity'
        FILTER (?entity2_type != :Entity)

        # Retrieve publication information if available
        OPTIONAL {
            ?relation prov:wasDerivedFrom ?publication .
        }
    }
    ORDER BY ?entity1 ?predicate ?entity2
    """

    try:
        sparql_results = execute_sparql_query(REPO_ID, sparql_query)

        data = process_sparql_results(sparql_results)

        df = pd.DataFrame(data)

        df.to_csv('knowledge_graph_relations.csv', index=False)
        logging.info("DataFrame successfully created and saved to 'knowledge_graph_relations.csv'.")

    except Exception as e:
        logging.error(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
