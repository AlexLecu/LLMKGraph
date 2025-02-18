SPARQL_QUERY_ENTITIES = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX c: <http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#>

SELECT DISTINCT ?entity ?label ?comment ?entityType
WHERE {
  ?entity a ?entityType .
  
  FILTER NOT EXISTS {
    ?subClass rdfs:subClassOf+ ?entityType .
    ?entity a ?subClass .
  }
  
  ?entityType rdfs:subClassOf* c:Entity .

  OPTIONAL { ?entity rdfs:label ?label }
  OPTIONAL { ?entity rdfs:comment ?comment }
}
"""

SPARQL_QUERY_PUBLICATIONS = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX c: <http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#>
SELECT ?pub ?label ?comment
WHERE {
  ?pub a c:PUBLICATION .
  OPTIONAL { ?pub rdfs:label ?label . }
  OPTIONAL { ?pub rdfs:comment ?comment . }
}
"""

SPARQL_QUERY_RELATIONS = """
PREFIX c: <http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX prov: <http://www.w3.org/ns/prov#>

SELECT ?subj ?pred ?obj ?publication ?subjLabel ?objLabel ?relLabel ?relComment
WHERE {
  {
    SELECT ?subj ?pred ?obj ?publication
    WHERE {
      VALUES ?pred { 
        c:cause c:affect c:prevent c:aggravate c:diagnose c:improve 
        c:present c:progression c:test c:treat
      }
      ?subj ?pred ?obj .
      OPTIONAL { ?subj prov:wasDerivedFrom ?publication . }
    }
  }
  UNION
  {
    ?rel a c:RELATION .
    OPTIONAL { ?rel c:relation_subject   ?subj . }
    OPTIONAL { ?rel c:relation_predicate ?pred . }
    OPTIONAL { ?rel c:relation_object    ?obj . }
    OPTIONAL { ?rel prov:wasDerivedFrom ?publication . }
  }

  OPTIONAL { ?subj rdfs:label ?subjLabel . }
  OPTIONAL { ?obj  rdfs:label ?objLabel . }
  OPTIONAL {
    ?pred rdfs:label ?relLabel ;
          rdfs:comment ?relComment .
  }
}
"""