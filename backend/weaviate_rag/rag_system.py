import os
from dotenv import load_dotenv
import weaviate
from weaviate import WeaviateClient
from typing import List, Dict
import logging
from weaviate.classes.query import QueryReference
from weaviate.collections.classes.filters import Filter
from openai import OpenAI

load_dotenv()

WEAVIATE_URL = "http://localhost:8080"
KG_CLASS_NAME = "Entity"
RELATION_CLASS = "Relation"
PUBLICATION_CLASS = "Publication"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KGRAG")


class KGRAGSystem:
    def __init__(self):
        self.client: WeaviateClient = None
        try:
            self.client = weaviate.connect_to_local()
            self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self._verify_schema()
        except Exception as e:
            logger.error(f"Initialization failed: {str(e)}")
            raise
        finally:
            if self.client is not None:
                self.client.close()

    def _verify_schema(self):
        """Verify required classes exist in Weaviate schema (v4)."""
        with self.client as client:
            collections = client.collections.list_all(simple=False)
            existing_collections = [col for col in collections]

            required_classes = {KG_CLASS_NAME, RELATION_CLASS, PUBLICATION_CLASS}
            missing = required_classes - set(existing_collections)

            if missing:
                raise ValueError(
                    f"Missing required collections in Weaviate: {missing}. "
                    "Please create them first."
                )

    def query(self, question: str, max_context_length: int = 3000) -> Dict:
        """Main query pipeline with proper connection handling."""
        result = {
            "question": question,
            "context": "No context found",
            "sources": [],
            "context_entities": 0,
            "context_relations": 0,
            "error": None
        }

        try:
            with self.client as client:
                context_data = self._hybrid_search(client, question)
                context_str = self._format_context(client, context_data)[:max_context_length]

                # Update results with KG context
                result.update({
                    "context": context_str,
                    "sources": self._extract_sources(context_data),
                    "context_entities": sum(
                        1 for item in context_data if isinstance(item, dict) and item.get("type") == "entity"),
                    "context_relations": sum(
                        1 for item in context_data if isinstance(item, dict) and item.get("type") == "relation")
                })

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Query failed: {str(e)}", exc_info=True)

        return result

    def _hybrid_search(self, client: WeaviateClient, query: str, top_k: int = 5) -> List[Dict]:
        """Perform hybrid search."""
        try:
            logger.info(f"Starting hybrid search for: {query}")

            entities_collection = client.collections.get(KG_CLASS_NAME)
            vector_result = entities_collection.query.near_text(
                query=query,
                limit=top_k,
                return_properties=["name", "type"]
            )

            context = []
            seen_entities = set()
            for obj in vector_result.objects:
                entity_id = obj.uuid
                if entity_id in seen_entities:
                    continue

                seen_entities.add(entity_id)

                relations = self._get_relations_for_entity(client, entity_id)
                context.extend(relations)

            return context

        except Exception as e:
            logger.error(f"Hybrid search failed: {str(e)}", exc_info=True)
            return []

    def _get_relations_for_entity(self, client: WeaviateClient, entity_id: str) -> List[Dict]:
        """Get relations using cross-references."""
        relations_collection = client.collections.get(RELATION_CLASS)
        relations = []

        base_refs = [
            QueryReference(link_on="relation_subject", return_properties=["name", "type"]),
            QueryReference(link_on="relation_object", return_properties=["name", "type"]),
            QueryReference(link_on="hasPublication", return_properties=["name"]),
        ]

        # Process both directions
        for filter_cond in [
            Filter.by_ref("relation_subject").by_id().equal(entity_id),  # Outgoing
            Filter.by_ref("relation_object").by_id().equal(entity_id)  # Incoming
        ]:
            result = relations_collection.query.fetch_objects(
                limit=5,
                return_references=base_refs,
                filters=filter_cond
            )
            relations.extend(self._process_relation_objects(result.objects))

        return relations

    def _process_relation_objects(self, relations: list) -> List[Dict]:
        """Process Weaviate relation objects into standardized dictionaries."""
        processed = []

        for rel in relations:

            subject = self._get_reference_data(rel, "relation_subject")
            obj = self._get_reference_data(rel, "relation_object")
            pubs = [{"name" : self._clean_pub_name(rel.references.get("hasPublication").objects[0].properties.get("name", "Unknown"))}]

            processed.append({
                "type": "relation",
                "predicate": rel.properties.get("relation_predicate"),
                "subject": subject,
                "object": obj,
                "publications": pubs
            })

        return processed

    def _get_reference_data(self, rel, ref_name: str) -> Dict:
        """Safe extraction of reference data with defaults."""
        ref = rel.references.get(ref_name)
        if not ref or not ref.objects:
            return {"name": "Unknown", "type": "Unknown"}

        return {
            "name": ref.objects[0].properties.get("name", "Unknown"),
            "type": ref.objects[0].properties.get("type", "Unknown")
        }

    def _clean_pub_name(self, pub_name: str) -> str:
        """Remove 'PUB_' prefix from publication names if present."""
        return pub_name[4:] if pub_name.startswith("PUB_") else pub_name


    def _format_context(self, client: WeaviateClient, context: List[Dict]) -> str:
        """Format context."""
        formatted = []
        base_url = "https://app.dimensions.ai/details/clinical_trial/"

        for item in context:
            if item["type"] == "relation":
                rel = item
                predicate = rel["predicate"].replace('_', ' ').title()

                # Extract names directly from subject/object
                subject_name = f"{rel['subject']['name']} ({rel['subject']['type']})"
                object_name = f"{rel['object']['name']} ({rel['object']['type']})"

                # Format publications
                pub_links = []
                for pub in rel["publications"]:
                    pub_name = pub.get('name', 'Unnamed Publication')
                    pub_links.append(f"[{pub_name}]({base_url}{pub_name})")  # Use name as ID for demo

                rel_str = (
                    f"{subject_name} → {predicate} → {object_name}\n"
                    f"  - Supported by: {', '.join(pub_links) if pub_links else 'No publications'}"
                )
                formatted.append(rel_str)

            elif item["type"] == "entity":
                e_name = item.get("name", "Unknown Entity")
                e_type = item.get("type", "Unknown Type")
                formatted.append(f"Entity: {e_name} ({e_type})")

        return "\n\n".join(formatted)

    def _get_entity_name(self, client: WeaviateClient, entity_id: str) -> str:
        """Get entity name."""
        try:
            entity = client.collections.get(KG_CLASS_NAME).get(uuid=entity_id)
            return entity.properties.get("name", "Unknown Entity")
        except Exception as e:
            logger.error(f"Error getting entity name: {str(e)}")
            return "Unknown Entity"

    def _extract_sources(self, context: List[Dict]) -> List[str]:
        sources = set()
        try:
            for item in context or []:
                if isinstance(item, dict) and item.get("type") == "relation":
                    pubs = item.get("data", {}).get("hasPublication", [])
                    sources.update(
                        f"{pub.get('name', 'Unnamed Publication')}: {pub.get('description', 'No description')}"
                        for pub in pubs if isinstance(pub, dict)
                    )
        except Exception as e:
            logger.error(f"Source extraction error: {str(e)}")
        return list(sources)


if __name__ == "__main__":
    try:
        rag = KGRAGSystem()
        questions = [
            "What are the causes of AMD?"
        ]

        for q in questions:
            print(f"\n{'=' * 40}\nQuestion: {q}")
            result = rag.query(q)
            print(f"Answer: {result['answer']}")
            if result["sources"]:
                print("\nSources:")
                for source in result["sources"]:
                    print(f"- {source}")
            print(f"\nContext: {result['context_relations']} relations")
            print("=" * 40)

    except Exception as e:
        logger.critical(f"Application failed: {str(e)}")
