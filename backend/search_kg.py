from SPARQLWrapper import SPARQLWrapper, POST, JSON
sparql = SPARQLWrapper("http://graphdb:7200/repositories/amd_repo")


def construct_sparql_query(query_text, filter_type):
    if filter_type == 'node':
        sparql_query = f"""
        SELECT ?s ?p ?o WHERE {{
            ?s ?p ?o .
            FILTER regex(str(?s), "{query_text}", "i")
        }} LIMIT 100
        """
    elif filter_type == 'relation':
        sparql_query = f"""
        SELECT ?s ?p ?o WHERE {{
            ?s ?p ?o .
            FILTER regex(str(?p), "{query_text}", "i")
        }} LIMIT 100
        """
    elif filter_type == 'entity':
        sparql_query = f"""
        SELECT ?s ?p ?o WHERE {{
            ?s ?p ?o .
            FILTER regex(str(?o), "{query_text}", "i")
        }} LIMIT 100
        """
    else:
        sparql_query = f"""
        SELECT ?s ?p ?o WHERE {{
            ?s ?p ?o .
            FILTER (
                regex(str(?s), "{query_text}", "i") ||
                regex(str(?p), "{query_text}", "i") ||
                regex(str(?o), "{query_text}", "i")
            )
        }} LIMIT 100
        """

    return sparql_query


def query_knowledge_graph(query_text, filter_type):
    data = []
    sparql_query = construct_sparql_query(query_text, filter_type)

    sparql.setQuery(sparql_query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    for result in results["results"]["bindings"]:
        s = result["s"]["value"]
        p = result["p"]["value"]
        o = result["o"]["value"]
        data.append({"subject": s, "predicate": p, "object": o})

    return data


def delete_relation_kg(subject, predicate, object):
    delete_query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX ont: <http://www.semanticweb.org/lecualexandru/ontologies/2024/1/untitled-ontology-6#>

        DELETE WHERE {{
            <{subject}> <{predicate}> <{object}> .
        }}
        """

    sparql.setQuery(delete_query)
    sparql.setMethod(POST)
    sparql.query()
