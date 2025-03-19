from dotenv import load_dotenv
import weaviate
from weaviate import WeaviateClient
from typing import List, Dict
import logging
from weaviate.classes.query import QueryReference
from weaviate.collections.classes.filters import Filter

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


    @staticmethod
    def _trim_context(context_str: str, max_length: int = 4000) -> str:
        """Simple context trimming that keeps complete relations."""
        if len(context_str) <= max_length:
            return context_str

        relations = context_str.split("\n\n")

        result = []
        current_length = 0

        for relation in relations:
            relation_length = len(relation) + 2
            if current_length + relation_length > max_length:
                break

            result.append(relation)
            current_length += relation_length

        return "\n\n".join(result)


    def query(self, question: str, max_context_length: int = 4000, max_entities: int = 10) -> Dict:
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
                context_data = self._hybrid_search(client, question, top_k=30)
                if not context_data:
                    result["error"] = "No relevant information found"
                    return result

                relevant_context = self._select_relevant_context(context_data, max_entities)

                # Format context
                context_str = self._format_context(relevant_context)

                # Trim to max length if needed
                if len(context_str) > max_context_length:
                    logger.info(f"Trimming context from {len(context_str)} to {max_context_length} chars")
                    context_str = self._trim_context(context_str, max_context_length)

                # Update results with KG context
                result.update({
                    "context": context_str,
                    "sources": self._extract_sources(relevant_context),
                    "context_entities": sum(
                        1 for item in relevant_context if isinstance(item, dict) and item.get("type") == "entity"),
                    "context_relations": sum(
                        1 for item in relevant_context if isinstance(item, dict) and item.get("type") == "relation")
                })

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Query failed: {str(e)}", exc_info=True)

        return result


    @staticmethod
    def _select_relevant_context(context_data: List[Dict], max_entities: int) -> List[Dict]:
        """Select the most relevant entities and their relations."""

        entities = [item for item in context_data if item["type"] == "entity"]
        relations = [item for item in context_data if item["type"] == "relation"]

        selected_entities = entities[:max_entities]
        selected_entity_ids = {entity["id"] for entity in selected_entities}

        relation_scores = {}

        for i, relation in enumerate(relations):
            subject_id = relation.get("subject", {}).get("id")
            object_id = relation.get("object", {}).get("id")

            if subject_id not in selected_entity_ids and object_id not in selected_entity_ids:
                continue

            try:
                subject_rank = next((i for i, e in enumerate(selected_entities)
                                     if e["id"] == subject_id), len(selected_entities))
                object_rank = next((i for i, e in enumerate(selected_entities)
                                    if e["id"] == object_id), len(selected_entities))

                relation_score = min(subject_rank, object_rank) + (i * 0.01)
                relation_scores[relation["id"]] = (relation_score, relation)
            except Exception:
                continue

        entity_relations = {entity_id: [] for entity_id in selected_entity_ids}

        sorted_relations = [r for _, r in sorted(relation_scores.values(), key=lambda x: x[0])]

        for relation in sorted_relations:
            subject_id = relation.get("subject", {}).get("id")
            object_id = relation.get("object", {}).get("id")

            if subject_id in selected_entity_ids and len(entity_relations[subject_id]) < 3:
                entity_relations[subject_id].append(relation)
                continue

            if object_id in selected_entity_ids and len(entity_relations[object_id]) < 3:
                entity_relations[object_id].append(relation)

        selected_relations = [rel for rels in entity_relations.values() for rel in rels]

        final_context = []
        for entity in selected_entities:
            final_context.append(entity)
            # Add this entity's relations
            entity_id = entity["id"]
            final_context.extend([r for r in selected_relations if
                                  r.get("subject", {}).get("id") == entity_id or
                                  r.get("object", {}).get("id") == entity_id])

        return final_context


    def _hybrid_search(self, client: WeaviateClient, query: str, top_k: int = 30) -> List[Dict]:
        """Perform hybrid search with simple AMD normalization."""
        try:
            if "amd" in query.lower():
                expanded_query = query.replace("AMD", "age-related macular degeneration")
                expanded_query = expanded_query.replace("amd", "age-related macular degeneration")
                logger.info(f"Using expanded query: {expanded_query}")

                query = expanded_query

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

                context.append({
                    "type": "entity",
                    "id": entity_id,
                    "name": obj.properties.get("name", "Unknown"),
                    "entity_type": obj.properties.get("type", "Unknown")
                })

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
            try:
                result = relations_collection.query.fetch_objects(
                    limit=5,
                    return_references=base_refs,
                    filters=filter_cond
                )
                relations.extend(self._process_relation_objects(result.objects, entity_id))
            except Exception as e:
                logger.error(f"Error fetching relations: {str(e)}")
                continue

        return relations


    def _process_relation_objects(self, relations: list, entity_id: str) -> List[Dict]:
        """Process Weaviate relation objects into standardized dictionaries."""
        processed = []

        for rel in relations:
            try:
                # Get subject, object and publication information
                subject = self._get_reference_data(rel, "relation_subject")
                obj = self._get_reference_data(rel, "relation_object")

                # Get publications (default to empty if none found)
                pubs = []
                pub_refs = rel.references.get("hasPublication")
                if pub_refs and pub_refs.objects:
                    for pub_obj in pub_refs.objects:
                        pub_name = self._clean_pub_name(pub_obj.properties.get("name", "Unknown"))
                        pubs.append({"name": pub_name})

                processed.append({
                    "type": "relation",
                    "id": rel.uuid,
                    "entity_id": entity_id,
                    "predicate": rel.properties.get("relation_predicate", "Unknown"),
                    "subject": subject,
                    "object": obj,
                    "publications": pubs
                })
            except Exception as e:
                logger.error(f"Error processing relation: {str(e)}")
                continue

        return processed


    @staticmethod
    def _get_reference_data(rel, ref_name: str) -> Dict:
        """Safe extraction of reference data with defaults."""
        ref = rel.references.get(ref_name)
        if not ref or not ref.objects:
            return {"name": "Unknown", "type": "Unknown"}

        return {
            "id": ref.objects[0].uuid,  # Store ID for filtering
            "name": ref.objects[0].properties.get("name", "Unknown"),
            "type": ref.objects[0].properties.get("type", "Unknown")
        }


    @staticmethod
    def _clean_pub_name(pub_name: str) -> str:
        """Remove 'PUB_' prefix from publication names if present."""
        return pub_name[4:] if pub_name.startswith("PUB_") else pub_name


    @staticmethod
    def _format_context(context: List[Dict]) -> str:
        """Format context with a simple, natural language pattern for all relations."""
        formatted = []
        base_url_ct = "https://app.dimensions.ai/details/clinical_trial/"
        base_url_pub = "https://app.dimensions.ai/details/publication/"

        for item in context:
            try:
                if item["type"] == "relation":
                    rel = item
                    predicate = rel["predicate"].replace('_', ' ').lower()

                    subject_name = rel['subject']['name'].replace('_', ' ')
                    subject_type = rel['subject']['type'].lower()

                    object_name = rel['object']['name'].replace('_', ' ')
                    object_type = rel['object']['type'].lower()

                    # Format publications
                    pub_links = []
                    for pub in rel["publications"]:
                        pub_name = pub.get('name', 'Unnamed Publication')

                        if pub_name.startswith("pub"):
                            base_url = base_url_pub
                            formatted_pub_id = pub_name.replace('_', '.')
                        else:
                            base_url = base_url_ct
                            formatted_pub_id = pub_name

                        pub_links.append(f"[{formatted_pub_id}]({base_url}{formatted_pub_id})")

                    rel_str = f"{subject_name} ({subject_type}) {predicate} {object_name} ({object_type}), according to {', '.join(pub_links) if pub_links else 'research'}."
                    formatted.append(rel_str)

                elif item["type"] == "entity":
                    continue

            except Exception as e:
                logger.error(f"Error formatting context item: {str(e)}")
                continue

        return "\n\n".join(formatted)


    @staticmethod
    def _extract_sources(context: List[Dict]) -> List[str]:
        sources = set()
        try:
            for item in context or []:
                if isinstance(item, dict) and item.get("type") == "relation":
                    for pub in item.get("publications", []):
                        if isinstance(pub, dict) and "name" in pub:
                            sources.add(pub["name"].replace('_', '.'))
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
            print(f"Context: {result['context']}")
            if result["sources"]:
                print("\nSources:")
                for source in result["sources"]:
                    print(f"- {source}")
            print(f"\nEntities: {result['context_entities']}, Relations: {result['context_relations']}")
            print("=" * 40)

    except Exception as e:
        logger.critical(f"Application failed: {str(e)}")
