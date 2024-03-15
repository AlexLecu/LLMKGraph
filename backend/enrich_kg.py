import os

from openai import OpenAI
from SPARQLWrapper import SPARQLWrapper, POST

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def generate_relations(text):
    prompt = f"""
           Given the text:

           {text}

           Please identify entities belonging to the following labels: disease, symptom, treatment, risk_factor, test, gene, biomarker, complication, prognosis, comorbidity, progression, body_part. Then, extract relationships among these entities based on the following relations: cause, treat, present, diagnose, aggravate, prevent, improve, affect. When presenting entity names, ensure the names do not contain parentheses. If an entity's common name typically includes parentheses, rephrase or abbreviate the name without using parentheses. Entity names must not contain commas. Instead, split entity and create separate relations.

           Present only the relationships extracted, in the specified format, without any introductory text, summary, or enumeration. Use the format:
           {{'relation_type': 'relation type', 'entity1_type': 'entity1_type', 'entity1_name': 'entity1_name', 'entity2_type': 'entity2_type', 'entity2_name': 'entity2_name'}}

           IMPORTANT: Output must contain only the relations in the specified format, with no other text or numbers included.
       """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Extract causal relations from text using specific labels and relations."},
            {"role": "user", "content": prompt}
        ]
    )

    return response


def convert_relations(response):
    relations = []
    relation_strings = response.choices[0].message.content.strip().split('\n')
    for relation_string in relation_strings:
        if relation_string != '':
            relation_dict = eval(relation_string)
            relations.append(relation_dict)

    return relations


def create_sparql_query(relations):
    prefixes = """
    PREFIX ont: <http://www.semanticweb.org/lecualexandru/ontologies/2024/1/untitled-ontology-6#>
    """

    # Start constructing the query
    query = prefixes + "INSERT DATA { GRAPH <http://amddata.org/amd/> { "

    # Dynamically add each relation to the query
    for relation in relations:
        # Assuming subject and obj are instances of ont:Entity and predicate is a direct property
        # Convert the subject, predicate, and object into a more URI-friendly format
        # This is a simple conversion, consider a more robust method for actual use
        subject_type_uri = "ont:" + relation["entity1_name"].replace(" ", "_") + " rdf:type " + "ont:" + relation[
            "entity1_type"].upper() + " . "
        object_type_uri = "ont:" + relation["entity2_name"].replace(" ", "_") + " rdf:type " + "ont:" + relation[
            "entity2_type"].upper() + " . "
        subject_uri = "ont:" + relation["entity1_name"].replace(" ", "_")
        predicate_uri = "ont:" + relation["relation_type"]
        object_uri = "ont:" + relation["entity2_name"].replace(" ", "_")

        # Add the triple to the query
        query += subject_type_uri
        query += object_type_uri
        query += f"{subject_uri} {predicate_uri} {object_uri} . "

    query += " } }"

    return query


def return_relations(text):
    gpt_response = generate_relations(text)
    relations = convert_relations(gpt_response)

    return relations


def add_relations_to_kg(relations):
    query = create_sparql_query(relations)

    sparql = SPARQLWrapper("http://localhost:7200/repositories/amd_repo/statements")
    sparql.setMethod(POST)
    sparql.setQuery(query)
    sparql.query()
