import os
from openai import OpenAI
from mistralai import Mistral
from dotenv import load_dotenv
import re
import ast
import logging
import uuid
from SPARQLWrapper import SPARQLWrapper, POST
from prompts import generate_user_prompt, system_prompt
from disambiguation.disambiguation import sanitize_entity_name, refine_relations
import json

load_dotenv()

GRAPHDB_URL = os.getenv('GRAPHDB_URL', 'http://localhost:7200')
client_gpt = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
client_mistral = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
client_deepseek = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")

# logging.basicConfig(
#     filename='../data/Logs/2024-12-05/Log_Extraction_GPT3.5.log',
#     filemode='w',
#     level=logging.WARNING,
#     format='%(asctime)s - %(levelname)s - %(message)s'
# )


def generate_relations_mistral(text):
    model = "ft:open-mistral-nemo:6606d669:20241028:e2b83ddc"
    user_prompt = generate_user_prompt(text)

    chat_response = client_mistral.chat.complete(
        model=model,
        max_tokens=2000,
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()}
        ]
    )

    return chat_response


def generate_relations_gpt_35_turbo(text):
    model = "ft:gpt-3.5-turbo-1106:personal::8ouriq0i"
    user_prompt = generate_user_prompt(text)

    chat_response = client_gpt.chat.completions.create(
        model=model,
        max_tokens=2000,
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()}
        ]
    )

    return chat_response


def generate_relations_gpt_o1_mini(text):
    model = "gpt-4o-mini"
    user_prompt = generate_user_prompt(text)

    chat_response = client_gpt.chat.completions.create(
        model=model,
        max_tokens=2000,
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()}
        ]
    )

    return chat_response


def generate_relations_deepseek_r1(text):
        model = "deepseek-chat"
        user_prompt = generate_user_prompt(text)
        chat_response = client_deepseek.chat.completions.create(
            model=model,
            max_tokens=2000,
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()}
            ]
        )
        return chat_response


def is_valid_relation(data):
    valid_entity_types = {'disease', 'symptom', 'treatment', 'risk_factor', 'test', 'gene', 'biomarker', 'complication',
                          'prognosis', 'comorbidity', 'progression', 'body_part'}
    valid_relation_types = {'cause', 'treat', 'present', 'diagnose', 'aggravate', 'prevent', 'improve', 'affect'}

    return (
            data.get('relation_type') in valid_relation_types and
            data.get('entity1_type') in valid_entity_types and
            data.get('entity2_type') in valid_entity_types and
            isinstance(data.get('entity1_name'), str) and
            isinstance(data.get('entity2_name'), str)
    )


def validate_output(output):
    pattern = r"\{'relation_type': '.*?', 'entity1_type': '.*?', 'entity1_name': '.*?', 'entity2_type': '.*?', 'entity2_name': '.*?'\}"
    matches = re.findall(pattern, output)
    dicts = []
    for match in matches:
        try:
            data = ast.literal_eval(match)
            if is_valid_relation(data):
                dicts.append(data)
            else:
                logging.warning(f"Invalid data fields in: {data}")
        except (SyntaxError, ValueError) as e:
            logging.warning(f"Failed to parse match: {match}. Error: {e}")
    return dicts

# Needs more testing
def convert_relations(response):
    try:
        raw_content = response['message']['content']

        matches = re.findall(r'\{.*?\}', raw_content, re.DOTALL)
        if not matches:
            print("No JSON-like content found in the response")
            return []

        relations = []
        for match in matches:
            try:
                relation = json.loads(match.replace("'", '"'))

                if isinstance(relation, dict) and {'relation_type', 'entity1_type', 'entity1_name', 'entity2_type',
                                                   'entity2_name'}.issubset(relation.keys()):
                    relations.append(relation)
                else:
                    print(f"Invalid relation structure: {relation}")
            except json.JSONDecodeError as e:
                print(f"JSON parsing failed for match: {match} - Error: {e}")

        return relations

    except KeyError as e:
        print(f"Invalid response format: {e}")
        return []

def generate_response_mistral(abstracts):
    relations = []
    i = 0
    for abstract in abstracts:
        i += 1
        print(i)
        response = generate_relations_mistral(abstract['text'])
        matches = validate_output(str(response))

        pub_id = {
            'pub_id': abstract.get('id', None)
        }

        for match in matches:
            match.update(pub_id)

        relations.extend(matches)

    return relations


def generate_responses_gpt_35_turbo(abstracts):
    relations = []
    i = 0
    for abstract in abstracts:
        i += 1
        print(i)
        response = generate_relations_gpt_35_turbo(abstract["text"])
        matches = validate_output(str(response))

        pub_id = {
            'pub_id': abstract.get('id', None)
        }

        for match in matches:
            match.update(pub_id)

        relations.extend(matches)

    return relations


def generate_responses_gpt_4o1_mini(abstracts):
    relations = []
    i = 0
    for abstract in abstracts:
        i += 1
        print(i)
        response = generate_relations_gpt_o1_mini(abstract["text"])
        matches = validate_output(str(response))

        pub_id = {
            'pub_id': abstract.get('id', None)
        }

        for match in matches:
            match.update(pub_id)

        relations.extend(matches)

    return relations


def generate_responses_deepseek_r1(abstracts):
    relations = []
    i = 0
    for abstract in abstracts:
        i += 1
        print(i)
        response = generate_relations_deepseek_r1(abstract["text"])
        matches = validate_output(str(response))

        pub_id = {
            'pub_id': abstract.get('id', None)
        }

        for match in matches:
            match.update(pub_id)

        relations.extend(matches)

    return relations


def extract_relations(content, model):
    if model == "model_a":
        relations = generate_responses_gpt_35_turbo(content)

        return relations
    elif model == "model_b":
        relations = generate_response_mistral(content)

        return relations
    elif model == "model_c":
        relations = generate_responses_gpt_4o1_mini(content)

        return relations
    elif model == "model_d":
        relations = generate_responses_deepseek_r1(content)

        return relations


def create_sparql_queries_for_bulk_import(relations, batch_size=200):
    prefixes = f"""
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX ont: <http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    """
    sparql_queries = []

    # Split the relations into batches
    for i in range(0, len(relations), batch_size):
        batch_relations = relations[i:i+batch_size]
        query = prefixes + f"INSERT DATA {{ GRAPH <http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD/> {{\n"

        for relation in batch_relations:
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
                publication_uri = f"ont:{sanitize_entity_name(pub_id)}"
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
        sparql_queries.append(query)

    return sparql_queries


def add_bulk_relations_to_kg(relations, repo_id):
    sparql = SPARQLWrapper(f"{GRAPHDB_URL}/repositories/{repo_id}/statements")
    refined_relations = refine_relations(relations)
    queries = create_sparql_queries_for_bulk_import(refined_relations)
    for query in queries:
        sparql.setMethod(POST)
        sparql.setQuery(query)
        sparql.query()
