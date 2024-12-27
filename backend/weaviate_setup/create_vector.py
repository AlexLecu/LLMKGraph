import pandas as pd
import weaviate
import weaviate.classes as wvc
from dotenv import load_dotenv
import os

load_dotenv()

huggingface_key = os.getenv("HUGGINGFACEHUB_API_TOKEN")
headers = {
    "X-HuggingFace-Api-Key": huggingface_key,
}

client = weaviate.connect_to_local(
    headers=headers
)


def create_schema():
    try:
        causal_amd = client.collections.create(
            name="CausalAMD",
            vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_huggingface(
                model="sentence-transformers/all-MiniLM-L6-v2",
            ),
            generative_config=wvc.config.Configure.Generative.openai(),
            properties=[
                wvc.config.Property(
                    name="text",
                    data_type=wvc.config.DataType.TEXT,
                ),
                wvc.config.Property(
                    name="subject",
                    data_type=wvc.config.DataType.TEXT,
                ),
                wvc.config.Property(
                    name="subjectType",
                    data_type=wvc.config.DataType.TEXT,
                ),
                wvc.config.Property(
                    name="relation",
                    data_type=wvc.config.DataType.TEXT,
                ),
                wvc.config.Property(
                    name="object",
                    data_type=wvc.config.DataType.TEXT,
                ),
                wvc.config.Property(
                    name="objectType",
                    data_type=wvc.config.DataType.TEXT,
                ),
                wvc.config.Property(
                    name="publication",
                    data_type=wvc.config.DataType.TEXT,
                )
            ]
        )

        print(causal_amd.config.get(simple=False))
    finally:
        client.close()


def make_text_snippet(relation):
    snippet = (
        f"Relation: {relation['Relation']}\n"
        f"Subject: {relation['Subject']} (Type: {relation['Subject Type']})\n"
        f"Object: {relation['Object']} (Type: {relation['Object Type']})\n"
        f"Source Publication: {relation['Source Publication']}\n"
    )

    return snippet


def ingest_relations():
    relations = pd.read_csv('knowledge_graph_relations.csv')

    collection = client.collections.get("CausalAMD")

    with collection.batch.dynamic() as batch:
        for index, row in relations.iterrows():
            snippet = make_text_snippet(row)

            data = {
                "text": snippet,
                "subject": row['Subject'],
                "subjectType": row['Subject Type'],
                "relation": row['Relation'],
                "object": row['Object'],
                "objectType": row['Object Type'],
                "publication": row['Source Publication']
            }

            batch.add_object(
                properties=data
            )


if __name__ == "__main__":
    ingest_relations()
