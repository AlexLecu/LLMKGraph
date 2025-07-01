import re
import logging
from collections import defaultdict

synonyms_map = {
    "wet amd": "wet age-related macular degeneration",
    "early amd": "early age-related macular degeneration",
    "cnv": "choroidal neovascularization",
    "amd": "age-related macular degeneration",
    "wet age-related macular degeneration amd": "wet age-related macular degeneration",
    "early age related macular degeneration amd": "early age-related macular degeneration",
    "wet armd": "wet age-related macular degeneration",
    "ga": "geographic atrophy",
    "oct": "optical coherence tomography",
    "pdt": "photodynamic therapy",
    "pcv": "polypoidal choroidal vasculopathy",
    "vma": "vitreomacular adhesion",
    "me": "macular edema",
    "namd": "neovascular age-related macular degeneration",
    "neovascular amd": "neovascular age-related macular degeneration",
}

trailing_words = {"cnv", "ga"}


def get_most_frequent_type(type_counts):
    type_priority = {
        'disease': 12,
        'body_part': 11,
        'treatment': 10,
        'symptom': 9,
        'complication': 8,
        'comorbidity': 7,
        'risk_factor': 6,
        'biomarker': 5,
        'progression': 4,
        'test': 3,
        'gene': 2,
        'prognosis': 1
    }

    if not type_counts:
        return None

    max_count = max(type_counts.values())

    candidates = [type_label for type_label, count in type_counts.items() if count == max_count]

    if len(candidates) == 1:
        return candidates[0]
    else:
        candidates.sort(key=lambda x: type_priority.get(x, 0), reverse=True)
        return candidates[0]


def resolve_entity_types(relations):
    entity_type_counts = defaultdict(lambda: defaultdict(int))

    for rel in relations:
        e1_name = rel['entity1_name'].lower()
        e1_type = rel['entity1_type']
        e2_name = rel['entity2_name'].lower()
        e2_type = rel['entity2_type']

        entity_type_counts[e1_name][e1_type] += 1
        entity_type_counts[e2_name][e2_type] += 1

    resolved_entity_types = {}
    for entity, types in entity_type_counts.items():
        if len(types) > 1:
            resolved_type = get_most_frequent_type(types)
            resolved_entity_types[entity] = resolved_type
            logging.info(f"Resolved entity '{entity}' to type '{resolved_type}' based on counts: {types}")

    for rel in relations:
        e1_name = rel['entity1_name'].lower()
        e2_name = rel['entity2_name'].lower()

        if e1_name in resolved_entity_types:
            old_type = rel['entity1_type']
            rel['entity1_type'] = resolved_entity_types[e1_name]
            logging.debug(f"Updated entity1 '{e1_name}' type from '{old_type}' to '{resolved_entity_types[e1_name]}'")

        if e2_name in resolved_entity_types:
            old_type = rel['entity2_type']
            rel['entity2_type'] = resolved_entity_types[e2_name]
            logging.debug(f"Updated entity2 '{e2_name}' type from '{old_type}' to '{resolved_entity_types[e2_name]}'")

    return relations


def normalize_entity_name(name):
    if not isinstance(name, str):
        return ""

    # Lowercase and trim whitespace
    name = name.lower().strip()

    # Replace multiple spaces with a single space
    name = ' '.join(name.split())

    # Split into words
    words = name.split()

    if len(words) > 2:
        # Remove trailing meaningless words
        while words and words[-1] in trailing_words:
            words.pop()
        name = ' '.join(words)

        # Remove embedded acronyms
        name = re.sub(r'\bamd\b', '', name).strip()
        name = re.sub(r'\bcnv\b', '', name).strip()

        name = ' '.join(name.split())

    # Apply domain-specific synonyms mapping
    if name in synonyms_map:
        name = synonyms_map[name]

    return name


def refine_relations(relations):
    unique_relations_set = set()
    refined_relations = []

    for rel in relations:
        entity1_name = normalize_entity_name(rel.get("entity1_name", ""))
        entity2_name = normalize_entity_name(rel.get("entity2_name", ""))

        # Check if names are empty after normalization
        if not entity1_name or not entity2_name:
            logging.warning(f"Empty entity names after normalization in relation: {rel}")
            continue

        # Check for self-relations if not desired
        if entity1_name == entity2_name:
            logging.warning(f"Self-relation detected and skipped: {rel}")
            continue

        rel_tuple = (
            rel.get("relation_type"),
            rel.get("entity1_type"),
            entity1_name,
            rel.get("entity2_type"),
            entity2_name,
            rel.get("pub_id")
        )

        if rel_tuple not in unique_relations_set:
            unique_relations_set.add(rel_tuple)
            refined_relations.append({
                "relation_type": rel.get("relation_type"),
                "entity1_type": rel.get("entity1_type"),
                "entity1_name": entity1_name,
                "entity2_type": rel.get("entity2_type"),
                "entity2_name": entity2_name,
                "pub_id": rel.get("pub_id")
            })
        else:
            logging.info(f"Duplicate relation skipped: {rel}")

    refined_relations = resolve_entity_types(refined_relations)

    return refined_relations


def sanitize_entity_name(name):
    # Replace spaces and special characters with underscores
    name = re.sub(r'[\s\W]+', '_', name)
    # Remove leading and trailing underscores
    name = name.strip('_')
    return name
