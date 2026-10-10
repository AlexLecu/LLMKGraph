"""Load extracted relations straight from JSON into Weaviate, bypassing GraphDB.

Input: one or more JSON files with a list of
  {"relation_type", "entity1_type", "entity1_name", "entity2_type", "entity2_name", "pub_id"}
(the format produced by bulk_relations.py / enrich_kg_gpt.py).

The same cleaning as the GraphDB path is applied (`refine_relations`: name
normalisation, de-duplication, majority-vote entity typing). Run
`create_schema.py` first.

Usage:
  python ingest_from_json.py ../100_clinical_trials_extracted_relations_gpt/all_relations.json [more.json ...]
"""
import json
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/
from disambiguation.disambiguation import refine_relations  # noqa: E402
from weaviate_client import get_weaviate_client  # noqa: E402

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger("disambiguation").setLevel(logging.WARNING)
logger = logging.getLogger("ingest_from_json")


def load_relations(paths):
    relations = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get("relations", [])
        logger.info("%s: %d raw relations", p, len(data))
        relations.extend(r for r in data if isinstance(r, dict))
    return relations


def main(paths):
    raw = load_relations(paths)
    logging.getLogger().setLevel(logging.WARNING)  # refine_relations is chatty
    relations = refine_relations(raw)
    logging.getLogger().setLevel(logging.INFO)
    logger.info("%d relations after cleaning and de-duplication", len(relations))

    client = get_weaviate_client()
    try:
        entities = client.collections.get("Entity")
        publications = client.collections.get("Publication")
        rel_col = client.collections.get("Relation")

        entity_uuid, pub_uuid = {}, {}

        # Entities: one object per (normalised) name; type resolved by refine_relations
        with entities.batch.dynamic() as batch:
            for r in relations:
                for name, etype in ((r["entity1_name"], r["entity1_type"]), (r["entity2_name"], r["entity2_type"])):
                    if name in entity_uuid:
                        continue
                    entity_uuid[name] = batch.add_object({"name": name, "type": str(etype or "entity").upper()})
        logger.info("%d entities", len(entity_uuid))

        with publications.batch.dynamic() as batch:
            for r in relations:
                pub = r.get("pub_id")
                if pub and pub not in pub_uuid:
                    pub_uuid[pub] = batch.add_object({"name": pub})
        logger.info("%d publications", len(pub_uuid))

        with rel_col.batch.dynamic() as batch:
            for r in relations:
                refs = {
                    "relation_subject": entity_uuid[r["entity1_name"]],
                    "relation_object": entity_uuid[r["entity2_name"]],
                }
                if r.get("pub_id") in pub_uuid:
                    refs["hasPublication"] = pub_uuid[r["pub_id"]]
                batch.add_object({"relation_predicate": r["relation_type"]}, references=refs)
        failed = len(rel_col.batch.failed_objects) + len(entities.batch.failed_objects) + len(publications.batch.failed_objects)
        logger.info("%d relations written, %d batch failures", len(relations), failed)
        if failed:
            for err in rel_col.batch.failed_objects[:3]:
                logger.error("example failure: %s", err.message)

        for name, col in (("Entity", entities), ("Relation", rel_col), ("Publication", publications)):
            logger.info("Weaviate %s count: %d", name, col.aggregate.over_all(total_count=True).total_count)
    finally:
        client.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
