import weaviate
import logging
from SPARQLWrapper import SPARQLWrapper, JSON
from dotenv import load_dotenv
from queries import SPARQL_QUERY_ENTITIES, SPARQL_QUERY_RELATIONS, SPARQL_QUERY_PUBLICATIONS

logger = logging.getLogger(__name__)


GRAPHDB_SPARQL_ENDPOINT = "http://localhost:7200/repositories/amd_repo_gpt_4o_mini"
WEAVIATE_URL = "http://localhost:8080"

load_dotenv()

client = weaviate.connect_to_local()

sparql = SPARQLWrapper(GRAPHDB_SPARQL_ENDPOINT)
sparql.setReturnFormat(JSON)

entity_uuid_map = {}
publication_uuid_map = {}


def uri_to_local_name(uri: str) -> str:
    """Extract local name or suffix from a URI."""
    if "#" in uri:
        return uri.split("#")[-1]
    else:
        return uri.rsplit("/", 1)[-1]


def create_entity(iri: str, label: str, type_: str, comment: str) -> str:
    """
    Create an 'Entity' object in Weaviate, returning its UUID.
    """
    try:
        name_val = label if label else uri_to_local_name(iri)
        type_val = type_ if type_ else "Entity"

        data = {
            "name": name_val,
            "type": type_val
        }

        entity = client.collections.get("Entity")
        result = entity.data.insert(data)
        return result
    except Exception as e:
        logger.error(f"Failed to create entity {iri}: {e}")
        raise


def create_publication(iri: str, label: str, comment: str) -> str:
    """
    Create a 'Publication' object in Weaviate, returning its UUID.
    """
    try:
        name_val = label if label else uri_to_local_name(iri)

        data = {
            "name": name_val
        }

        publication = client.collections.get("Publication")
        result = publication.data.insert(data)
        return result
    except Exception as e:
        logger.error(f"Failed to create publication {iri}: {e}")
        raise


def create_relation(subj_uuid: str, pred_str: str, obj_uuid: str, pub_uuid: str = None) -> str:
    """
    Create a 'Relation' with proper cross-references
    """
    try:
        relations = client.collections.get("Relation")
        result = relations.data.insert(
            properties={"relation_predicate": pred_str},
            references={
                "relation_subject": subj_uuid,
                "relation_object": obj_uuid,
                "hasPublication": pub_uuid
            }
        )
        return result
    except Exception as e:
        logger.error(f"Failed to create relation {subj_uuid}-{pred_str}-{obj_uuid}: {e}")
        raise


def ingest_entities():
    """Ingest entities from SPARQL endpoint into Weaviate"""
    try:
        logger.info("Starting entity ingestion...")
        sparql.setQuery(SPARQL_QUERY_ENTITIES)
        results = sparql.queryAndConvert()
        bindings = results["results"]["bindings"]

        for row in bindings:
            try:
                entity_iri = row["entity"]["value"]
                entity_type_iri = row["entityType"]["value"]
                label = row.get("label", {}).get("value", "")
                comment = row.get("comment", {}).get("value", "")

                entity_subclass = uri_to_local_name(entity_type_iri)

                w_uuid = create_entity(
                    iri=entity_iri,
                    label=label,
                    type_=entity_subclass,
                    comment=comment
                )

                entity_uuid_map[entity_iri] = w_uuid
            except Exception as e:
                logger.error(f"Skipping entity {entity_iri} due to error: {e}")

        logger.info("Successfully ingested %d Entities into Weaviate.", len(bindings))
    except Exception as e:
        logger.error("Entity ingestion failed: %s", e)


def ingest_publications():
    """Ingest publications from SPARQL endpoint into Weaviate"""
    try:
        logger.info("Starting publication ingestion...")
        sparql.setQuery(SPARQL_QUERY_PUBLICATIONS)
        results = sparql.queryAndConvert()
        bindings = results["results"]["bindings"]

        for row in bindings:
            try:
                pub_iri = row["pub"]["value"]
                label = row.get("label", {}).get("value", "")
                comment = row.get("comment", {}).get("value", "")

                w_uuid = create_publication(pub_iri, label, comment)
                publication_uuid_map[pub_iri] = w_uuid
            except Exception as e:
                logger.error(f"Skipping publication {pub_iri} due to error: {e}")

        logger.info("Successfully ingested %d Publications into Weaviate.", len(bindings))
    except Exception as e:
        logger.error("Publication ingestion failed: %s", e)


def ingest_relations():
    """Ingest relations from SPARQL endpoint into Weaviate"""
    try:
        logger.info("Starting relation ingestion...")
        sparql.setQuery(SPARQL_QUERY_RELATIONS)
        results = sparql.queryAndConvert()
        bindings = results["results"]["bindings"]

        count = 0
        for row in bindings:
            try:
                subj_iri = row["subj"]["value"]
                pred_iri = row["pred"]["value"]
                obj_iri = row["obj"]["value"]
                publication_iri = row.get("publication", {}).get("value", "")

                subj_uuid = entity_uuid_map.get(subj_iri)
                obj_uuid = entity_uuid_map.get(obj_iri)
                pub_uuid = publication_uuid_map.get(publication_iri, None)

                if not subj_uuid or not obj_uuid:
                    logger.warning("Skipping relation %s-%s-%s (missing references)",
                                   subj_iri, pred_iri, obj_iri)
                    continue

                relation_name = uri_to_local_name(pred_iri)
                create_relation(
                    subj_uuid=subj_uuid,
                    pred_str=relation_name,
                    obj_uuid=obj_uuid,
                    pub_uuid=pub_uuid
                )
                count += 1
            except Exception as e:
                logger.error("Failed to process relation: %s", e)

        logger.info("Successfully ingested %d Relations with proper references.", count)
    except Exception as e:
        logger.error("Relation ingestion failed: %s", e)


def main():
    """Main ingestion workflow"""
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )

    app_logger = logging.getLogger(__name__)
    app_logger.setLevel(logging.INFO)

    try:
        ingest_entities()
        ingest_publications()
        ingest_relations()
        logger.info("All data ingested successfully from GraphDB to Weaviate!")
    except Exception as e:
        logger.error("Main ingestion process failed: %s", e)
    finally:
        client.close()


if __name__ == "__main__":
    main()
