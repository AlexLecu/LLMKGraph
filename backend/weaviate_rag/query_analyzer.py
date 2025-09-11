import spacy
from typing import Dict, Any
import time


nlp = spacy.load("en_core_web_sm")


def analyze_query(query: str) -> Dict[str, Any]:
    start_time = time.time()

    doc = nlp(query)

    entities = [ent.text for ent in doc.ents]

    noun_phrases = [chunk.text for chunk in doc.noun_chunks]

    keywords = []
    for token in doc:
        if (token.pos_ in ["NOUN", "PROPN"] or
                (token.pos_ == "ADJ" and token.text.lower() not in nlp.Defaults.stop_words)):
            keywords.append(token.text)

    relationships = []
    for token in doc:
        if token.pos_ == "VERB":
            subjects = [subj.text for subj in token.lefts if subj.dep_ in ("nsubj", "nsubjpass")]
            objects = [obj.text for obj in token.rights if obj.dep_ in ("dobj", "pobj")]

            if subjects and objects:
                relationships.append({
                    "subject": subjects[0],
                    "verb": token.lemma_,
                    "object": objects[0]
                })

    has_negation = any(token.dep_ == "neg" for token in doc)

    processing_time = time.time() - start_time

    return {
        "entities": entities,
        "noun_phrases": noun_phrases,
        "keywords": keywords,
        "relationships": relationships,
        "has_negation": has_negation,
        "processing_time": processing_time
    }


if __name__ == "__main__":
    user_query = "Can wet AMD lead to complete blindness?"

    total_start = time.time()

    analysis_result = analyze_query(user_query)

    print(f"Analysis completed in {analysis_result['processing_time']:.3f} seconds")
    print(f"Entities: {analysis_result['entities']}")
    print(f"Keywords: {analysis_result['keywords']}")
    print(f"Noun phrases: {analysis_result['noun_phrases']}")
    print(f"Relationships: {analysis_result['relationships']}")
    print(f"Has negation: {analysis_result['has_negation']}")

    print(f"Total execution time: {time.time() - total_start:.3f} seconds")
