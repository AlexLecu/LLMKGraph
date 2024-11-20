import os

from openai import OpenAI
from SPARQLWrapper import SPARQLWrapper, POST
from dotenv import load_dotenv
import re


load_dotenv()

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
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an advanced language model that specializes in analyzing text to identify medical causal relationships."},
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


def sanitize_entity_name(name):
    # Replace spaces and special characters with underscores
    name = re.sub(r'[\s\W]+', '_', name)
    # Remove leading and trailing underscores
    name = name.strip('_')
    return name


def create_sparql_query(relations):
    prefixes = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX ont: <http://www.semanticweb.org/lecualexandru/ontologies/2024/1/>
    """

    query = prefixes + "INSERT DATA { GRAPH <http://amddata.org/amd/> { "

    for relation in relations:
        # Sanitize entity names and types
        subject_name = sanitize_entity_name(relation["entity1_name"])
        object_name = sanitize_entity_name(relation["entity2_name"])
        relation_type = sanitize_entity_name(relation["relation_type"])
        entity1_type = sanitize_entity_name(relation["entity1_type"]).upper()
        entity2_type = sanitize_entity_name(relation["entity2_type"]).upper()

        # Construct URIs and triples
        subject_type_uri_ni = f"ont:{subject_name} rdf:type owl:NamedIndividual . "
        subject_type_uri = f"ont:{subject_name} rdf:type ont:{entity1_type} . "
        object_type_uri_ni = f"ont:{object_name} rdf:type owl:NamedIndividual . "
        object_type_uri = f"ont:{object_name} rdf:type ont:{entity2_type} . "
        subject_uri = f"ont:{subject_name}"
        predicate_uri = f"ont:{relation_type}"
        object_uri = f"ont:{object_name}"

        query += subject_type_uri_ni
        query += subject_type_uri
        query += object_type_uri_ni
        query += object_type_uri
        query += f"{subject_uri} {predicate_uri} {object_uri} . "

    query += " } }"

    return query


def return_relations(text):
    gpt_response = generate_relations(text)
    relations = convert_relations(gpt_response)

    return relations


def add_relations_to_kg(relations, repo_id):
    query = create_sparql_query(relations)
    sparql = SPARQLWrapper(f"http://graphdb:7200/repositories/{repo_id}/statements")
    sparql.setMethod(POST)
    sparql.setQuery(query)
    sparql.query()