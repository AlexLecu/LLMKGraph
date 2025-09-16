import weaviate
from weaviate.classes.query import Filter, QueryReference
import itertools
import tempfile
import atexit
import shutil
from ollama import Client
from together import Together
from openai import OpenAI
from weaviate_rag.query_analyzer import analyze_query


class GraphRAGSystem:

    def __init__(self, question, model_config=None):
        """Initialize the analyzer with a question and set up Weaviate and Ollama clients."""
        self.question = question
        self.model_config = model_config or {'provider': 'ollama', 'model_name': 'llama3.2'}

        # Initialize API clients based on provider
        if self.model_config['provider'] == 'together':
            self.api_client = Together(api_key=self.model_config['api_key'])
        elif self.model_config['provider'] == 'openai':
            self.api_client = OpenAI(api_key=self.model_config['api_key'])
        else:  # ollama
            self.ollama_client = Client()

        self.acronyms = {
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
        }

        self.temp_dir = tempfile.mkdtemp()
        atexit.register(shutil.rmtree, self.temp_dir, ignore_errors=True)
        self.client = weaviate.connect_to_local()
        self.entity_collection = self.client.collections.get("Entity")
        self.relation_collection = self.client.collections.get("Relation")
        self.entity_id_to_name = {}

    def expand_terms(self, terms):
        """Replace acronyms with their full forms in the list of terms or noun phrases, normalizing case."""
        expanded_terms = []
        for term in terms:
            words = term.split()
            expanded_words = [self.acronyms.get(word.lower(), word) for word in words]
            expanded_terms.append(" ".join(expanded_words))
        return expanded_terms

    def retrieve_entities(self):
        """Retrieve entities based on noun phrases AND keywords from the question."""
        query_analysis = analyze_query(self.question)

        terms_to_search = []

        if query_analysis.get('noun_phrases', []):
            terms_to_search.extend(query_analysis['noun_phrases'])

        if query_analysis.get('keywords', []):
            for keyword in query_analysis['keywords']:
                if not any(keyword.lower() in phrase.lower() for phrase in terms_to_search):
                    terms_to_search.append(keyword)

        if not terms_to_search:
            terms_to_search = [self.question]

        expanded_terms = self.expand_terms(terms_to_search)

        entity_results = {}
        for term in expanded_terms:
            entity_search_res = self.entity_collection.query.bm25(
                query=term,
                limit=5,
                return_properties=["name", "type"]
            )
            if entity_search_res.objects:
                entity_results[term] = entity_search_res.objects

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
        return relation_string

    def generate_summary(self, relation_string):
        """Generate a summary using the configured model."""
        prompt = (
            f"Given the question: '{self.question}'\n\n"
            f"Below is a list of relationship descriptions:\n{relation_string}\n\n"
            f"Based on the relationships provided, craft a concise, single-paragraph summary that answers the question. "
            f"Focus on the collective significance of the most relevant relationships without mentioning or referencing specific relationship numbers or indices. "
            f"Do not list relationships individually or quote them directly. "
            f"Present the response as plain text in a natural, narrative style, avoiding technical terms like 'relationships' in the summary itself."
        )
        try:
            if self.model_config['provider'] == 'together':
                response = self.api_client.chat.completions.create(
                    model=self.model_config['model_name'],
                    messages=[
                        {"role": "system", "content": "You are a medical knowledge assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=300
                )
                return response.choices[0].message.content.strip()

            elif self.model_config['provider'] == 'openai':
                response = self.api_client.responses.create(
                    model=self.model_config['model_name'],
                    input=prompt,
                    reasoning={"effort": "medium"},
                    text={"verbosity": "low"},
                )
                return response.output_text

            else:  # ollama
                response = self.ollama_client.generate(
                    model=self.model_config['model_name'],
                    prompt=prompt
                )
                return response.get('response', '').strip()

        except Exception as e:
            return f"Error processing response: {e}"

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
    question = "Can wet AMD lead to complete blindness?"
    analyzer = GraphRAGSystem(question)
    summary = analyzer.analyze()
    print("Summary of relevant relationships:\n", summary)