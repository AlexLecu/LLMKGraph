import spacy
from transformers import pipeline
from typing import Dict, Any, List
import time
from functools import lru_cache

# Load spaCy model - using the small model for speed
nlp = spacy.load("en_core_web_sm")

# Configure the transformer pipeline with optimizations
intent_classifier = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli",
    device=0  # Use GPU if available (0), otherwise use CPU (-1)
)


@lru_cache(maxsize=128)
def classify_intent(query: str, candidate_intents: tuple) -> str:
    """
    Classify the intent using the transformer pipeline with caching for repeated queries.
    Using tuple for candidate_intents to make it hashable for caching.
    """
    result = intent_classifier(query, list(candidate_intents))
    return result["labels"][0]


def analyze_query(query: str) -> Dict[str, Any]:
    """
    Efficiently analyze the user's query to extract entities and intent.
    Args:
        query (str): User's natural language query.
    Returns:
        Dict[str, Any]: A dictionary containing extracted entities, keywords, and intent.
    """
    start_time = time.time()

    # Process with spaCy
    doc = nlp(query)

    # Extract entities (named entities recognized by spaCy)
    entities = [ent.text for ent in doc.ents]

    # Extract important noun phrases (potential KG nodes)
    noun_phrases = [chunk.text for chunk in doc.noun_chunks]

    # Extract keywords (important words that might be nodes in KG)
    keywords = []
    for token in doc:
        # Include nouns, proper nouns, and adjectives that aren't stopwords
        if (token.pos_ in ["NOUN", "PROPN"] or
                (token.pos_ == "ADJ" and token.text.lower() not in nlp.Defaults.stop_words)):
            keywords.append(token.text)

    # Extract potential relationships from verbs
    relationships = []
    for token in doc:
        if token.pos_ == "VERB":
            # Find subject and object connected to this verb
            subjects = [subj.text for subj in token.lefts if subj.dep_ in ("nsubj", "nsubjpass")]
            objects = [obj.text for obj in token.rights if obj.dep_ in ("dobj", "pobj")]

            if subjects and objects:
                relationships.append({
                    "subject": subjects[0],
                    "verb": token.lemma_,
                    "object": objects[0]
                })

    # Check for negation
    has_negation = any(token.dep_ == "neg" for token in doc)

    # Fast rule-based intent detection for common patterns
    intent = None

    # Only use the transformer if we couldn't identify intent through rules
    if not intent:
        candidate_intents = ("diagnosis", "prevention", "treatment", "cause", "symptom")
        intent = classify_intent(query, candidate_intents)

    # Calculate processing time
    processing_time = time.time() - start_time

    return {
        "entities": entities,
        "noun_phrases": noun_phrases,
        "keywords": keywords,
        "intent": intent,
        "relationships": relationships,
        "has_negation": has_negation,
        "processing_time": processing_time
    }


def retrieve_from_knowledge_graph(query_analysis, kg_client):
    """
    Retrieve relevant relations from the knowledge graph based on the query analysis.
    This is a template function - implement based on your specific KG technology.

    Args:
        query_analysis: Result from analyze_query()
        kg_client: Your knowledge graph client

    Returns:
        List of relevant relations
    """
    # Combine all potential terms that could be nodes in your KG
    potential_nodes = set()
    potential_nodes.update(query_analysis["entities"])
    potential_nodes.update(query_analysis["noun_phrases"])
    potential_nodes.update(query_analysis["keywords"])

    # Extract the intent (relation type)
    intent = query_analysis["intent"]

    # Get any explicit relationships found in the query
    explicit_relationships = query_analysis["relationships"]

    # Step 1: If we have explicit relationships, query those first
    results = []
    if explicit_relationships:
        for rel in explicit_relationships:
            # Search KG for this specific relationship
            # Example (replace with your actual KG query syntax):
            # kg_results = kg_client.query_relationship(rel["subject"], rel["verb"], rel["object"])
            # results.extend(kg_results)
            pass

    # Step 2: If no results yet, search based on entities and intent
    if not results and potential_nodes:
        # Example query using the entities and intent:
        # For each entity, find relations of the given intent type
        for node in potential_nodes:
            # kg_results = kg_client.query_by_node_and_relation_type(node, intent)
            # results.extend(kg_results)
            pass

    # Step 3: If still no results, do a broader search
    if not results:
        # Fallback to a more general search
        # kg_results = kg_client.general_search(list(potential_nodes))
        # results.extend(kg_results)
        pass

    # Return the top N most relevant results
    # In a real implementation, you'd rank these by relevance
    return results


def optimize_kg_query(query_analysis):
    """
    Optimize a query for your knowledge graph based on the analysis.
    This generates an efficient query pattern based on the extracted information.

    Args:
        query_analysis: Result from analyze_query()

    Returns:
        A query object/string optimized for your specific KG
    """
    # This function would be customized for your specific KG technology
    # For example, it might generate a SPARQL query, a Cypher query, etc.
    intent = query_analysis["intent"]
    entities = query_analysis["entities"]
    relationships = query_analysis["relationships"]

    # Example pseudocode for building a graph query
    if relationships:
        # We have explicit subject-verb-object
        # Build a specific pattern query
        subject = relationships[0]["subject"]
        verb = relationships[0]["verb"]
        obj = relationships[0]["object"]
        return f"MATCH (s:Entity {{name: '{subject}'}})-[r:{verb}]->(o:Entity {{name: '{obj}'}}) RETURN *"
    elif entities and intent:
    # We have entities and an intent but no explicit relationship
    # Build a query that looks for the intent relation between entities
        return f"MATCH (s:Entity)-[r:{intent}]->(o:Entity) WHERE s.name IN {entities} OR o.name IN {entities} RETURN *"
    else:
        # Fallback to a broader search
        all_terms = query_analysis["entities"] + query_analysis["keywords"]
        return f"MATCH (n:Entity) WHERE n.name IN {all_terms} RETURN n"

    # This is just a placeholder - return an appropriate query for your KG
    return {"intent": intent, "entities": entities}


# Example usage
if __name__ == "__main__":
    user_query = "Does hypertension worsen AMD by elevating choroidal pressure?"

    # Measure total execution time
    total_start = time.time()

    # Analyze the query
    analysis_result = analyze_query(user_query)

    # Generate optimized KG query
    kg_query = optimize_kg_query(analysis_result)

    # Print results
    print(f"Analysis completed in {analysis_result['processing_time']:.3f} seconds")
    print(f"Entities: {analysis_result['entities']}")
    print(f"Keywords: {analysis_result['keywords']}")
    print(f"Noun phrases: {analysis_result['noun_phrases']}")
    print(f"Intent: {analysis_result['intent']}")
    print(f"Relationships: {analysis_result['relationships']}")
    print(f"Has negation: {analysis_result['has_negation']}")
    print(f"Optimized KG query: {kg_query}")

    print(f"Total execution time: {time.time() - total_start:.3f} seconds")