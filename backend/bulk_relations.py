import os
from openai import OpenAI
from mistralai import Mistral
from dotenv import load_dotenv
import re
import ast
import logging
import uuid
from SPARQLWrapper import SPARQLWrapper, POST

load_dotenv()

client_gpt = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
client_mistral = Mistral(api_key=os.environ["MISTRAL_API_KEY"])


system_prompt = """
You are an AI language model tasked with:

1. **Entity Identification**:
   - Identify entities in the text labeled **only** as:
     - **disease**, **symptom**, **treatment**, **risk_factor**, **test**, **gene**, **biomarker**, **complication**, **prognosis**, **comorbidity**, **progression**, **body_part**
   - **Use these exact labels; do not introduce new labels or synonyms.**
   
    **Entity Type Definitions**:
    - **disease**: A specific illness or medical condition that negatively affects the structure or function of part or all of an organism.
    - **symptom**: A physical or mental feature indicating a condition or disease, experienced by the patient.
    - **treatment**: Medical care or therapy provided to manage or cure a disease or symptom.
    - **risk_factor**: An attribute, characteristic, or exposure that increases the likelihood of developing a disease or injury.
    - **test**: A medical examination or procedure performed to detect, diagnose, or monitor diseases, disease processes, susceptibility, or to determine a course of treatment.
    - **gene**: A unit of heredity in a living organism; a segment of DNA or RNA.
    - **biomarker**: A measurable indicator of some biological state or condition.
    - **complication**: An unfavorable evolution or consequence of a disease, health condition, or therapy.
    - **prognosis**: The likely course or outcome of a disease; the chance of recovery.
    - **comorbidity**: The simultaneous presence of two or more diseases or medical conditions in a patient.
    - **progression**: The process of a disease becoming worse or spreading in the body.
    - **body_part**: Any part of the human anatomy.

2. **Relationship Extraction**:
   - Extract relationships among these entities based on the relations **only**:
     - **cause**, **treat**, **present**, **diagnose**, **aggravate**, **prevent**, **improve**, **affect**
   - **Use these exact labels; do not introduce new labels or synonyms.**
   
   **Relation Type Definitions**:
    - **cause**: Entity1 results in or is the reason for Entity2.
    - **treat**: Entity1 is used to manage or cure Entity2.
    - **present**: Entity1 exhibits or shows signs of Entity2.
    - **diagnose**: Entity1 identifies the presence of Entity2.
    - **aggravate**: Entity1 worsens or intensifies Entity2.
    - **prevent**: Entity1 stops or hinders the occurrence of Entity2.
    - **improve**: Entity1 enhances or makes Entity2 better.
    - **affect**: Entity1 influences or has an impact on Entity2.

**Instructions**:

- **Consistency Rule**: Assign the same entity type to an entity whenever it appears, based on the definitions provided.
- **Ambiguous Entities**: If an entity could belong to multiple types, refer to the definitions and choose the most appropriate type based on context.
- **Important**: Use **only** the specified labels for entity and relation types. Do not use synonyms, variations, or introduce new labels.

**Output Format**:

Present each relationship in the following exact format (including single quotes and braces):

{'relation_type': 'relation_type_value', 'entity1_type': 'entity1_type_value', 'entity1_name': 'entity1_name_value', 'entity2_type': 'entity2_type_value', 'entity2_name': 'entity2_name_value'}

**Output Only the Relationships**:
    - Replace placeholders with appropriate values from the text.
    - **Ensure 'entity1_type' and 'entity2_type' are **only** from the specified labels.**
    - **Do not include any additional text, explanations, or numbers.**
    - Exclude parentheses and special characters in 'entity1_name' and 'entity2_name'.
    - For enumerations and complex sentences, extract each relationship separately as per the examples.
  
**Examples**:

Text: "AMD affects the retina and causes vision loss."

Output:
{'relation_type': 'affect', 'entity1_type': 'disease', 'entity1_name': 'AMD', 'entity2_type': 'body_part', 'entity2_name': 'retina'}
{'relation_type': 'cause', 'entity1_type': 'disease', 'entity1_name': 'AMD', 'entity2_type': 'symptom', 'entity2_name': 'vision loss'}

Text: "Smoking is a risk factor that aggravates AMD progression."

Output:
{'relation_type': 'aggravate', 'entity1_type': 'risk_factor', 'entity1_name': 'Smoking', 'entity2_type': 'progression', 'entity2_name': 'AMD progression'}

Text: "Anti-VEGF therapy treats wet AMD and improves vision."

Output:
{'relation_type': 'treat', 'entity1_type': 'treatment', 'entity1_name': 'Anti-VEGF therapy', 'entity2_type': 'disease', 'entity2_name': 'wet AMD'}
{'relation_type': 'improve', 'entity1_type': 'treatment', 'entity1_name': 'Anti-VEGF therapy', 'entity2_type': 'symptom', 'entity2_name': 'vision'}

Text: "The CFH gene is linked to a higher risk of developing AMD."

Output:
{'relation_type': 'cause', 'entity1_type': 'gene', 'entity1_name': 'CFH gene', 'entity2_type': 'risk_factor', 'entity2_name': 'higher risk of developing AMD'}

Text: "Patients with AMD often present blurred vision and drusen in the macula."

Output:
{'relation_type': 'present', 'entity1_type': 'disease', 'entity1_name': 'AMD', 'entity2_type': 'symptom', 'entity2_name': 'blurred vision'}
{'relation_type': 'present', 'entity1_type': 'disease', 'entity1_name': 'AMD', 'entity2_type': 'biomarker', 'entity2_name': 'drusen'}
{'relation_type': 'affect', 'entity1_type': 'disease', 'entity1_name': 'AMD', 'entity2_type': 'body_part', 'entity2_name': 'macula'}
"""


def generate_user_prompt(text):
    return f"Extract all relationships from the following text and present them exactly in the specified format:\n\n{text}"


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


def convert_relations_gpt(response):
    relations = []
    relation_strings = response.choices[0].message.content.strip().split('\n')
    for relation_string in relation_strings:
        if relation_string != '':
            relation_dict = eval(relation_string)
            relations.append(relation_dict)

    return relations


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


def sanitize_entity_name(name):
    # Replace spaces and special characters with underscores
    name = re.sub(r'[\s\W]+', '_', name)
    # Remove leading and trailing underscores
    name = name.strip('_')
    return name


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
        sparql_queries.append(query)

    return sparql_queries


def add_bulk_relations_to_kg(relations, repo_id):
    sparql = SPARQLWrapper(f"http://localhost:7200/repositories/{repo_id}/statements")
    queries = create_sparql_queries_for_bulk_import(relations)
    for query in queries:
        sparql.setMethod(POST)
        sparql.setQuery(query)
        sparql.query()

