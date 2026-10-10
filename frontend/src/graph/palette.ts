// Visual vocabulary for the knowledge-graph canvas: one colour per entity type
// from the CausalAMD ontology, plus the structural node kinds (relation,
// predicate, publication). Shared by the graph view and its legend.

export const ONT_NS = 'http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#';

export interface NodeStyle {
  label: string;
  color: string;
  border: string;
  shape: string;
}

/** Entity types written by the extraction pipeline (rdf:type ont:<TYPE>). */
export const ENTITY_STYLES: Record<string, NodeStyle> = {
  DISEASE:      { label: 'Disease',      color: '#fecaca', border: '#dc2626', shape: 'ellipse' },
  SYMPTOM:      { label: 'Symptom',      color: '#fed7aa', border: '#ea580c', shape: 'ellipse' },
  TREATMENT:    { label: 'Treatment',    color: '#bbf7d0', border: '#16a34a', shape: 'ellipse' },
  RISK_FACTOR:  { label: 'Risk factor',  color: '#fde68a', border: '#ca8a04', shape: 'ellipse' },
  TEST:         { label: 'Test',         color: '#bae6fd', border: '#0284c7', shape: 'ellipse' },
  GENE:         { label: 'Gene',         color: '#ddd6fe', border: '#7c3aed', shape: 'ellipse' },
  BIOMARKER:    { label: 'Biomarker',    color: '#c7d2fe', border: '#4f46e5', shape: 'ellipse' },
  COMPLICATION: { label: 'Complication', color: '#fbcfe8', border: '#db2777', shape: 'ellipse' },
  PROGNOSIS:    { label: 'Prognosis',    color: '#99f6e4', border: '#0d9488', shape: 'ellipse' },
  COMORBIDITY:  { label: 'Comorbidity',  color: '#fecdd3', border: '#e11d48', shape: 'ellipse' },
  PROGRESSION:  { label: 'Progression',  color: '#d9f99d', border: '#65a30d', shape: 'ellipse' },
  BODY_PART:    { label: 'Body part',    color: '#a5f3fc', border: '#0891b2', shape: 'ellipse' },
};

const UNTYPED: NodeStyle = { label: 'Entity (untyped)', color: '#e2e8f0', border: '#64748b', shape: 'ellipse' };

export const STRUCTURAL_STYLES: Record<string, NodeStyle> = {
  ENTITY:      UNTYPED,
  RELATION:    { label: 'Relation',         color: '#ffedd5', border: '#f97316', shape: 'diamond' },
  PREDICATE:   { label: 'Relation type',    color: '#ede9fe', border: '#8b5cf6', shape: 'box' },
  PUBLICATION: { label: 'Publication',      color: '#dbeafe', border: '#2563eb', shape: 'square' },
};

export const ALL_STYLES: Record<string, NodeStyle> = { ...ENTITY_STYLES, ...STRUCTURAL_STYLES };

export function localName(uri: string): string {
  const hash = uri.lastIndexOf('#');
  if (hash !== -1) return uri.substring(hash + 1);
  const slash = uri.lastIndexOf('/');
  if (slash !== -1) return uri.substring(slash + 1);
  return uri;
}

/** "age_related_macular_degeneration" -> "age related macular degeneration". */
export function prettyLabel(name: string): string {
  return name.replace(/_+/g, ' ').trim();
}

/** Shorten generated ids such as REL_8f1c...-... to "REL_8f1c…" for display. */
export function shortId(name: string): string {
  const m = /^(REL|PUB)_([0-9a-f]{8})/i.exec(name);
  return m ? `${m[1]}_${m[2]}…` : name;
}

/** Map a type URI (or local name) to a palette key; unknown -> ENTITY. */
export function entityKind(typeUri?: string | null): string {
  if (!typeUri) return 'ENTITY';
  const key = localName(typeUri).toUpperCase();
  return key in ENTITY_STYLES ? key : 'ENTITY';
}

export interface GraphNode {
  id: string;
  label: string;
  title?: string;
  kind: string;
  shape: string;
  color: { background: string; border: string; highlight: { background: string; border: string } };
  font: { color: string; size: number };
}

export function makeNode(id: string, kind: string, rawLabel?: string): GraphNode {
  const style: NodeStyle = ALL_STYLES[kind] ?? UNTYPED;
  const name = rawLabel ?? localName(id);
  const label = kind === 'RELATION' || kind === 'PUBLICATION' ? shortId(name) : prettyLabel(name);
  return {
    id,
    label,
    title: `${style.label}: ${name}`,
    kind,
    shape: style.shape,
    color: {
      background: style.color,
      border: style.border,
      highlight: { background: style.color, border: style.border },
    },
    font: { color: '#1f2937', size: 14 },
  };
}
