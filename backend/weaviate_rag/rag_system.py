import weaviate
from weaviate.classes.query import Filter, QueryReference
import itertools
import tempfile
import atexit
import shutil
from ollama import Client
from weaviate_rag.query_analyzer import analyze_query

class GraphRAGSystem:
    def __init__(self, question):
        """Initialize the analyzer with a question and set up Weaviate and Ollama clients."""
        self.question = question
        self.acronyms = {"AMD": "age-related macular degeneration"}
        self.temp_dir = tempfile.mkdtemp()
        atexit.register(shutil.rmtree, self.temp_dir, ignore_errors=True)
        self.client = weaviate.connect_to_local()
        self.ollama_client = Client()
        self.entity_collection = self.client.collections.get("Entity")
        self.relation_collection = self.client.collections.get("Relation")
        self.entity_id_to_name = {}

    def expand_terms(self, terms):
        """Replace acronyms with their full forms in the list of terms."""
        return [self.acronyms.get(term, term) for term in terms]

    def retrieve_entities(self):
        """Retrieve entities based on predefined noun phrases from the question."""
        query_analysis = analyze_query(self.question)
        expanded_noun_phrases = self.expand_terms(query_analysis['noun_phrases'])
        entity_results = {}
        for noun_phrase in expanded_noun_phrases:
            entity_search_res = self.entity_collection.query.bm25(
                query=noun_phrase,
                limit=5,
                return_properties=["name", "type"]
            )
            if entity_search_res.objects:
                entity_results[noun_phrase] = entity_search_res.objects
        return entity_results

    def get_entity_ids_and_names(self, entity_results):
        """Extract entity IDs and names from search results."""
        entity_ids = []
        entity_names = []
        for noun_phrase, entity_objects in entity_results.items():
            for entity_obj in entity_objects:
                entity_ids.append(entity_obj.uuid)
                entity_names.append(entity_obj.properties['name'])
                self.entity_id_to_name[entity_obj.uuid] = entity_obj.properties['name']
        return entity_ids, entity_names

    def retrieve_pairwise_relations(self, entity_ids):
        """Retrieve pairwise relationships between entities."""
        entity_pairs = set(itertools.permutations(entity_ids, 2))
        combined_filter = (
                Filter.by_ref("relation_subject").by_id().contains_any(entity_ids) &
                Filter.by_ref("relation_object").by_id().contains_any(entity_ids)
        )
        references = [
            QueryReference(link_on="relation_subject", return_properties=["name", "type"]),
            QueryReference(link_on="relation_object", return_properties=["name", "type"]),
            QueryReference(link_on="hasPublication", return_properties=["name", "content"])
        ]
        try:
            relations = self.relation_collection.query.fetch_objects(
                filters=combined_filter,
                return_properties=["relation_predicate"],
                return_references=references,
                limit=100
            )
        except Exception as e:
            print(f"Error executing pairwise query: {e}")
            relations = []

        seen = set()
        pairwise_relations = []
        involved_entities = set()
        for o in relations.objects:
            subject_id = o.references["relation_subject"].objects[0].uuid
            object_id = o.references["relation_object"].objects[0].uuid
            if (subject_id, object_id) in entity_pairs:
                predicate = o.properties["relation_predicate"]
                triple = (subject_id, predicate, object_id)
                if triple not in seen:
                    seen.add(triple)
                    subject_name = o.references["relation_subject"].objects[0].properties["name"]
                    object_name = o.references["relation_object"].objects[0].properties["name"]
                    pairwise_relations.append((subject_name, predicate, object_name))
                    involved_entities.add(subject_id)
                    involved_entities.add(object_id)
        return pairwise_relations, involved_entities

    def retrieve_individual_relations(self, entity_ids, involved_entities):
        """Retrieve individual relations for entities not in pairwise relations."""
        entities_to_check = [eid for eid in entity_ids if eid not in involved_entities]
        if not entities_to_check and involved_entities:
            return {}

        entity_relations = {eid: [] for eid in entity_ids}
        seen = set()
        for eid in entity_ids:
            entity_filter = (
                    Filter.by_ref("relation_subject").by_id().equal(eid) |
                    Filter.by_ref("relation_object").by_id().equal(eid)
            )
            try:
                relations = self.relation_collection.query.fetch_objects(
                    filters=entity_filter,
                    return_properties=["relation_predicate"],
                    return_references=[
                        QueryReference(link_on="relation_subject", return_properties=["name", "type"]),
                        QueryReference(link_on="relation_object", return_properties=["name", "type"]),
                        QueryReference(link_on="hasPublication", return_properties=["name", "content"])
                    ],
                    limit=50
                )
                for o in relations.objects:
                    subject_id = o.references["relation_subject"].objects[0].uuid
                    object_id = o.references["relation_object"].objects[0].uuid
                    predicate = o.properties["relation_predicate"]
                    triple = (subject_id, predicate, object_id)
                    if triple not in seen:
                        seen.add(triple)
                        subject_name = o.references["relation_subject"].objects[0].properties["name"]
                        object_name = o.references["relation_object"].objects[0].properties["name"]
                        entity_relations[eid].append((subject_name, predicate, object_name))
            except Exception as e:
                print(f"Error querying relations for entity {self.entity_id_to_name.get(eid, 'unknown')}: {e}")
        return entity_relations

    def build_relation_string(self, pairwise_relations, entity_relations):
        """Construct a string of all relations for summary generation."""
        relation_string = ""
        relation_counter = 1

        for subj, pred, obj in pairwise_relations:
            relation_string += f"{relation_counter}. {subj} {pred} {obj}\n"
            relation_counter += 1

        for eid, rels in entity_relations.items():
            entity_name = self.entity_id_to_name.get(eid, "unknown")
            if rels:
                for subj, pred, obj in rels:
                    relation_string += f"{relation_counter}. {subj} {pred} {obj}\n"
                    relation_counter += 1
            else:
                relation_string += f"No relations found for {entity_name}\n"
        return relation_string

    def generate_summary(self, relation_string):
        """Generate a summary of relevant relationships using Ollama."""
        prompt = (
            f"Given the question: '{self.question}'\n\n"
            f"Below is a list of relationship descriptions:\n{relation_string}\n\n"
            f"Select the most relevant relationships that help answer the question. "
            f"Instead of listing the relationships individually, provide a single concise paragraph "
            f"summarizing how these relationships collectively demonstrate their relevance to the question. "
            f"Focus on their combined significance and avoid directly quoting the relationships. "
            f"Present the response as plain text without JSON or numbered lists."
        )
        try:
            response = self.ollama_client.generate(model='llama3.2', prompt=prompt)
            response_text = response.get('response', '')
            if not response_text:
                raise ValueError("Empty response from Ollama")
            return response_text.strip()
        except Exception as e:
            return f"Error processing Ollama response: {e}"

    def analyze(self):
        """Orchestrate the analysis process and return the summary."""
        entity_results = self.retrieve_entities()
        entity_ids, entity_names = self.get_entity_ids_and_names(entity_results)
        pairwise_relations, involved_entities = self.retrieve_pairwise_relations(entity_ids)
        entity_relations = self.retrieve_individual_relations(entity_ids, involved_entities)
        relation_string = self.build_relation_string(pairwise_relations, entity_relations)
        summary = self.generate_summary(relation_string)
        self.client.close()
        return summary


# Example usage
if __name__ == "__main__":
    question = "Does dry AMD progress slowly because it avoids retinal pigment epithelial regeneration? a) Yes b) No c) Sometimes d) Only early stages"
    # question = "What is AMD?"
    analyzer = GraphRAGSystem(question)
    summary = analyzer.analyze()
    print("Summary of relevant relationships:\n", summary)