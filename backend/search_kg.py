from SPARQLWrapper import SPARQLWrapper, POST, JSON
import re
import os

ONT_NAMESPACE = 'http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#'
GRAPHDB_URL = os.getenv('GRAPHDB_URL', 'http://localhost:7200')

def construct_sparql_query(query_text, filter_type):
    pattern = re.escape(query_text)

    if filter_type == 'node':
            sparql_query = f"""
            PREFIX ont: <{ONT_NAMESPACE}>
            PREFIX prov: <http://www.w3.org/ns/prov#>
            SELECT ?relation ?subject ?predicate ?object ?publication WHERE {{
                ?relation a ont:RELATION ;
                        ont:relation_subject ?subject ;
                        ont:relation_predicate ?predicate ;
                        ont:relation_object ?object ;
                        OPTIONAL {{ ?relation prov:wasDerivedFrom ?publication . }}
                FILTER regex(str(?subject), "{pattern}", "i")
            }} LIMIT 100
            """
    elif filter_type == 'relation':
        sparql_query = f"""
        PREFIX ont: <{ONT_NAMESPACE}>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        SELECT ?relation ?subject ?predicate ?object ?publication WHERE {{
            ?relation a ont:RELATION ;
                    ont:relation_subject ?subject ;
                    ont:relation_predicate ?predicate ;
                    ont:relation_object ?object ;
                    OPTIONAL {{ ?relation prov:wasDerivedFrom ?publication . }}
            FILTER regex(str(?predicate), "{pattern}", "i")
        }} LIMIT 100
        """
    elif filter_type == 'entity':
        sparql_query = f"""
        PREFIX ont: <{ONT_NAMESPACE}>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        SELECT ?relation ?subject ?predicate ?object ?publication WHERE {{
            ?relation a ont:RELATION ;
                    ont:relation_subject ?subject ;
                    ont:relation_predicate ?predicate ;
                    ont:relation_object ?object ;
                   OPTIONAL {{ ?relation prov:wasDerivedFrom ?publication . }}
            FILTER regex(str(?object), "{pattern}", "i")
        }} LIMIT 100
        """
    else:
        # No specific filter type: search in all fields.
        sparql_query = f"""
        PREFIX ont: <{ONT_NAMESPACE}>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        SELECT ?relation ?subject ?predicate ?object ?publication WHERE {{
            ?relation a ont:RELATION ;
                    ont:relation_subject ?subject ;
                    ont:relation_predicate ?predicate ;
                    ont:relation_object ?object ;
                    OPTIONAL {{ ?relation prov:wasDerivedFrom ?publication . }}
            FILTER (
                regex(str(?subject), "{pattern}", "i") ||
                regex(str(?predicate), "{pattern}", "i") ||
                regex(str(?object), "{pattern}", "i")
            )
        }} LIMIT 100
        """
    return sparql_query

def query_knowledge_graph(query_text, filter_type, repo_id):
    sparql = SPARQLWrapper(f"{GRAPHDB_URL}/repositories/{repo_id}")
    sparql_query = construct_sparql_query(query_text, filter_type)
    
    sparql.setQuery(sparql_query)
    sparql.setReturnFormat(JSON)
    
    data = []
    try:
        results = sparql.query().convert()
    except Exception as e:
        print(f"Error executing SPARQL query: {e}")
        return data

    for result in results["results"]["bindings"]:
        relation = result.get("relation", {}).get("value", "")
        subject = result.get("subject", {}).get("value", "")
        predicate = result.get("predicate", {}).get("value", "")
        object_ = result.get("object", {}).get("value", "")
        publication = result.get("publication", {}).get("value", None)
        if publication and publication.startswith("PUB_"):
            publication = publication.replace("PUB_", "")
        data.append({
            "relation": relation,
            "subject": subject,
            "predicate": predicate,
            "object": object_,
            "publicationId": publication
        })

    return data


def delete_relation_kg(subject, predicate, object_, repo_id):
    print(f"Deleting relation: {subject} {predicate} {object_}")
    sparql_post = SPARQLWrapper(f"{GRAPHDB_URL}/repositories/{repo_id}/statements")
    
    delete_query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX ont: <{ONT_NAMESPACE}>
        DELETE WHERE {{
            ont:{subject} ont:{predicate} ont:{object_} .
        }}
    """
    print(delete_query)
    sparql_post.setQuery(delete_query)
    sparql_post.setMethod(POST)
    sparql_post.query()
