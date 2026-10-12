"""Create the LLMKGraph repositories in GraphDB and fill them from the public JSON files.

Runs inside the API image, with the repository's data/ folder mounted at /data:

    docker compose run --rm load

Each repository gets the CausalAMD ontology plus its relations, cleaned with the
same refine_relations as the /api/upload_relations path. A repository that already
holds relations is left untouched, so the script can be re-run safely.
"""
import json
import os
import sys

import requests

from bulk_relations import add_bulk_relations_to_kg

GRAPHDB_URL = os.getenv("GRAPHDB_URL", "http://graphdb:7200").rstrip("/")
DATA_DIR = os.getenv("DATA_DIR", "/data")
ONTOLOGY = "CausalAMD_ont.rdf"

# (id, title, relation files relative to data/) -- all of them ship with the repository
REPOSITORIES = [
    ("amd_abstracts", "AMD - 999 PubMed abstracts (DeepSeek V3)",
     ["Extracted_Relations/2025-03-12/Deepseek_V3_Relations_pubs.json"]),
    ("amd_clinical_trials", "AMD - 100 clinical trials (DeepSeek V3)",
     ["Extracted_Relations/2025-03-12/Deepseek_V3_Relations_ct.json"]),
    ("amd_repo_gpt_35", "AMD - LLM comparison: GPT-3.5",
     ["Extracted_Relations/2024-12-05/GPT3.5_Relations.json"]),
    ("amd_repo_gpt_4o1_mini", "AMD - LLM comparison: GPT-4o1-mini",
     ["Extracted_Relations/2024-12-05/GPT4-o1_mini_Relations.json"]),
    ("amd_repo_mistral", "AMD - LLM comparison: Mistral",
     ["Extracted_Relations/2024-12-05/Mistral_Relations.json"]),
    # Empty graph (ontology only) that visitors of the public site may write to
    ("amd_playground", "AMD - Playground (public, writable)", []),
]

# Legacy RDF4J config vocabulary: understood by GraphDB 10.x and 11.x alike
REPO_CONFIG = """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix rep: <http://www.openrdf.org/config/repository#> .
@prefix sr: <http://www.openrdf.org/config/repository/sail#> .
@prefix sail: <http://www.openrdf.org/config/sail#> .
@prefix graphdb: <http://www.ontotext.com/config/graphdb#> .

[] a rep:Repository ;
  rep:repositoryID "{id}" ;
  rdfs:label "{title}" ;
  rep:repositoryImpl [
      rep:repositoryType "graphdb:SailRepository" ;
      sr:sailImpl [
          sail:sailType "graphdb:Sail" ;
          graphdb:ruleset "rdfsplus-optimized"
        ]
    ] .
"""

COUNT_QUERY = ("PREFIX ont: <http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#> "
               "SELECT (COUNT(?r) AS ?n) WHERE { ?r a ont:RELATION }")


def existing_repositories():
    r = requests.get(f"{GRAPHDB_URL}/rest/repositories", headers={"Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    return {repo["id"] for repo in r.json()}


def create_repository(repo_id, title):
    config = REPO_CONFIG.format(id=repo_id, title=title)
    r = requests.post(f"{GRAPHDB_URL}/rest/repositories",
                      files={"config": ("config.ttl", config, "text/turtle")}, timeout=60)
    r.raise_for_status()


def relation_count(repo_id):
    r = requests.get(f"{GRAPHDB_URL}/repositories/{repo_id}", params={"query": COUNT_QUERY},
                     headers={"Accept": "application/sparql-results+json"}, timeout=60)
    r.raise_for_status()
    return int(r.json()["results"]["bindings"][0]["n"]["value"])


def load_ontology(repo_id):
    with open(os.path.join(DATA_DIR, ONTOLOGY), "rb") as f:
        r = requests.post(f"{GRAPHDB_URL}/repositories/{repo_id}/statements", data=f,
                          headers={"Content-Type": "application/rdf+xml"}, timeout=300)
    r.raise_for_status()


def read_relations(path):
    with open(os.path.join(DATA_DIR, path), encoding="utf-8") as f:
        data = json.load(f)
    return data.get("relations", []) if isinstance(data, dict) else data


def main():
    present = existing_repositories()
    for repo_id, title, files in REPOSITORIES:
        if repo_id not in present:
            print(f"[{repo_id}] creating repository", flush=True)
            create_repository(repo_id, title)
        elif relation_count(repo_id) > 0:
            print(f"[{repo_id}] already loaded ({relation_count(repo_id)} relations), skipping", flush=True)
            continue
        load_ontology(repo_id)
        for path in files:
            relations = read_relations(path)
            print(f"[{repo_id}] loading {len(relations)} raw relations from {path}", flush=True)
            add_bulk_relations_to_kg(relations, repo_id)
        print(f"[{repo_id}] done: {relation_count(repo_id)} relations", flush=True)


if __name__ == "__main__":
    sys.exit(main())
