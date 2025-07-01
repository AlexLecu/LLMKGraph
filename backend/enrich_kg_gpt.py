import os
import uuid

from openai import OpenAI
from SPARQLWrapper import SPARQLWrapper, POST
from dotenv import load_dotenv
from prompts import system_prompt, generate_user_prompt
from disambiguation.disambiguation import sanitize_entity_name
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam


load_dotenv()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
GRAPHDB_URL = os.getenv('GRAPHDB_URL', 'http://localhost:7200')


def generate_relations(text):
    user_prompt = generate_user_prompt(text)

    chat_response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=2000,
        temperature=0,
        messages=[
            ChatCompletionSystemMessageParam(role="system", content=system_prompt.strip()),
            ChatCompletionUserMessageParam(role="user", content=user_prompt.strip())
        ]
    )

    return chat_response


def convert_relations(response):
    relations = []
    relation_strings = response.choices[0].message.content.strip().split('\n')
    for relation_string in relation_strings:
        if relation_string != '':
            relation_dict = eval(relation_string)
            relations.append(relation_dict)

    return relations


def create_sparql_query(relations):
    prefixes = f"""
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX ont: <http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    """

    query = prefixes + f"INSERT DATA {{ GRAPH <http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD/> {{\n"

    for relation in relations:
        # Sanitize entity names and types
        subject_name = sanitize_entity_name(relation["entity1_name"])
        object_name = sanitize_entity_name(relation["entity2_name"])
        relation_type = sanitize_entity_name(relation["relation_type"])
        entity1_type = sanitize_entity_name(relation["entity1_type"]).upper()
        entity2_type = sanitize_entity_name(relation["entity2_type"]).upper()

        # Generate a unique URI for the relation
        relation_id = f"REL_{uuid.uuid4()}"
        relation_uri = f"ont:{relation_id}"

        # Define URIs
        subject_uri = f"ont:{subject_name}"
        predicate_uri = f"ont:{relation_type}"
        object_uri = f"ont:{object_name}"

        # Start constructing the triple
        triple = (
            f"{relation_uri} rdf:type ont:RELATION ;\n"
            f"  ont:relation_subject {subject_uri} ;\n"
            f"  ont:relation_predicate {predicate_uri} ;\n"
            f"  ont:relation_object {object_uri} ;\n"
        )

        # Check if 'pub_id' exists and is not empty
        pub_id = relation.get("pub_id")
        if pub_id:
            publication_uri = f"ont:PUB_{sanitize_entity_name(pub_id)}"
            triple += f"  prov:wasDerivedFrom {publication_uri} .\n"
            # Create the publication instance
            triple += f"{publication_uri} rdf:type ont:PUBLICATION .\n"
        else:
            # Remove the trailing ';' and replace with '.'
            triple = triple.rstrip(' ;\n') + ' .\n'

        # Add type declarations for entities
        triple += (
            f"{subject_uri} rdf:type ont:{entity1_type} .\n"
            f"{object_uri} rdf:type ont:{entity2_type} .\n"
        )

        query += triple + "\n"

    query += "}}"

    return query


def return_relations(text):
    gpt_response = generate_relations(text)
    relations = convert_relations(gpt_response)

    return relations


def add_relations_to_kg(relations, repo_id):
    query = create_sparql_query(relations)
    sparql = SPARQLWrapper(f"{GRAPHDB_URL}/repositories/{repo_id}/statements")
    sparql.setMethod(POST)
    sparql.setQuery(query)
    sparql.query()