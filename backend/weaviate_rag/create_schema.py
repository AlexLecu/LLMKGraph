"""Create (or recreate) the three collections the chatbot uses.

Only `Entity`, `Relation` and `Publication` are touched, so this is safe to run
on a Weaviate instance shared with other projects.

WEAVIATE_VECTORIZER=none (default)  -> no vectors; the chatbot only uses BM25
WEAVIATE_VECTORIZER=transformers    -> text2vec-transformers (needs the t2v service)
"""
import logging
import os

from dotenv import load_dotenv
from weaviate.classes.config import Configure, DataType, Property, ReferenceProperty

from weaviate_client import get_weaviate_client

logger = logging.getLogger(__name__)
load_dotenv()

COLLECTIONS = ("Relation", "Publication", "Entity")  # delete order: references first


def vectorizer_config():
    if os.getenv("WEAVIATE_VECTORIZER", "none").lower() == "transformers":
        return Configure.Vectorizer.text2vec_transformers()
    return Configure.Vectorizer.none()


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    client = get_weaviate_client()
    try:
        for name in COLLECTIONS:
            if client.collections.exists(name):
                client.collections.delete(name)
                logger.info("Deleted existing collection: %s", name)

        client.collections.create(
            name="Entity",
            properties=[
                Property(name="name", data_type=DataType.TEXT),
                Property(name="type", data_type=DataType.TEXT),
            ],
            vectorizer_config=vectorizer_config(),
        )
        logger.info("Created collection: Entity")

        client.collections.create(
            name="Publication",
            properties=[Property(name="name", data_type=DataType.TEXT)],
            vectorizer_config=vectorizer_config(),
        )
        logger.info("Created collection: Publication")

        client.collections.create(
            name="Relation",
            properties=[Property(name="relation_predicate", data_type=DataType.TEXT)],
            references=[
                ReferenceProperty(name="relation_subject", target_collection="Entity"),
                ReferenceProperty(name="relation_object", target_collection="Entity"),
                ReferenceProperty(name="hasPublication", target_collection="Publication"),
            ],
            vectorizer_config=vectorizer_config(),
        )
        logger.info("Created collection: Relation")
    finally:
        client.close()


if __name__ == "__main__":
    main()
