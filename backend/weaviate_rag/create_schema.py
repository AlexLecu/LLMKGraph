import weaviate
import logging
from dotenv import load_dotenv
from weaviate.classes.config import Property, DataType, Configure, ReferenceProperty

logger = logging.getLogger(__name__)

load_dotenv()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    client = weaviate.connect_to_local()

    try:
        client.collections.delete_all()
        logger.info("Deleted existing schema.")
    except Exception as e:
        logger.error(f"Error deleting schema: {e}")

    try:
        client.collections.create(
            name="Entity",
            properties=[
                Property(name="name", data_type=DataType.TEXT),
                Property(name="type", data_type=DataType.TEXT),
            ],
            vectorizer_config=Configure.Vectorizer.text2vec_transformers()
        )
        logger.info("Created class: Entity")

        client.collections.create(
            name="Publication",
            properties=[
                Property(name="name", data_type=DataType.TEXT),
            ],
            vectorizer_config=Configure.Vectorizer.text2vec_transformers()
        )
        logger.info("Created class: Publication")

        client.collections.create(
            name="Relation",
            properties=[
                Property(name="relation_predicate", data_type=DataType.TEXT),
            ],
            references=[
                ReferenceProperty(name="relation_subject", target_collection="Entity"),
                ReferenceProperty(name="relation_object", target_collection="Entity"),
                ReferenceProperty(name="hasPublication", target_collection="Publication")
            ],
            vectorizer_config=Configure.Vectorizer.text2vec_transformers()
        )
        logger.info("Created class: Relation")

    except Exception as e:
        logger.error(f"Error creating classes: {e}")

    try:
        final_schema = client.collections.list_all()
        logger.info("\nFinal schema in Weaviate:\n%s", final_schema)
    except Exception as e:
        logger.error(f"Error retrieving schema: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
