import ast
import logging
import os
import uuid

from openai import OpenAI
from SPARQLWrapper import SPARQLWrapper, POST
from dotenv import load_dotenv
from prompts import system_prompt, generate_user_prompt
from disambiguation.disambiguation import sanitize_entity_name
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam


load_dotenv()

from bulk_relations import _LazyClient  # noqa: E402

# Single-abstract extraction: GPT-4o-mini by default, or any OpenAI-compatible
# endpoint via EXTRACTION_API_BASE_URL / EXTRACTION_API_KEY / EXTRACTION_MODEL
# (e.g. Groq's openai/gpt-oss-120b on the public site).
EXTRACTION_MODEL = os.getenv("EXTRACTION_MODEL") or "gpt-4o-mini"
client = _LazyClient(lambda: OpenAI(
    api_key=os.getenv("EXTRACTION_API_KEY") or os.environ["OPENAI_API_KEY"],
    base_url=os.getenv("EXTRACTION_API_BASE_URL") or None))
GRAPHDB_URL = os.getenv('GRAPHDB_URL', 'http://localhost:7200')


def extraction_model_name():
    return EXTRACTION_MODEL


def generate_relations(text):
    user_prompt = generate_user_prompt(text)

    chat_response = client.chat.completions.create(
        model=EXTRACTION_MODEL,
        # reasoning models (gpt-oss) spend part of the budget thinking
        max_tokens=int(os.getenv("EXTRACTION_MAX_TOKENS", "4000")),
        temperature=0,
        messages=[
            ChatCompletionSystemMessageParam(role="system", content=system_prompt.strip()),
            ChatCompletionUserMessageParam(role="user", content=user_prompt.strip())
        ]
    )

    return chat_response


REQUIRED_RELATION_KEYS = {"entity1_name", "entity1_type", "relation_type", "entity2_name", "entity2_type"}


def parse_relation_line(relation_string):
    """Safely parse one model-generated relation line into a dict.

    The model is asked to return Python-dict-like lines. `ast.literal_eval`
    only evaluates literals (no function calls / imports), unlike `eval`, so a
    malicious or malformed model output cannot execute code.
    """
    try:
        value = ast.literal_eval(relation_string)
    except (ValueError, SyntaxError) as exc:
        logging.warning("Skipping unparsable relation line %r: %s", relation_string[:120], exc)
        return None
    if not isinstance(value, dict) or not REQUIRED_RELATION_KEYS.issubset(value):
        logging.warning("Skipping relation with missing keys: %r", relation_string[:120])
        return None
    return value


def convert_relations(response):
    relations = []
    relation_strings = response.choices[0].message.content.strip().split('\n')
    for relation_string in relation_strings:
        relation_string = relation_string.strip()
        if relation_string == '':
            continue
        relation_dict = parse_relation_line(relation_string)
        if relation_dict is not None:
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