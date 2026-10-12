// Human-readable names for the GraphDB repositories (ids stay technical).
// Unknown repositories fall back to their id, in the "Other" group.

export interface RepoInfo {
  label: string;
  detail: string;
  group: 'Knowledge graph' | 'LLM comparison' | 'Workspace' | 'Other';
}

export const REPO_INFO: Record<string, RepoInfo> = {
  amd_abstracts: { label: 'PubMed abstracts', detail: '999 AMD abstracts · extracted with DeepSeek V3', group: 'Knowledge graph' },
  amd_clinical_trials: { label: 'Clinical trials', detail: '100 AMD clinical trials · extracted with DeepSeek V3', group: 'Knowledge graph' },
  amd_repo_gpt_35: { label: 'GPT-3.5 Turbo (FT)', detail: '100 abstracts · fine-tuned GPT-3.5 Turbo', group: 'LLM comparison' },
  amd_repo_mistral: { label: 'Mistral Nemo (FT)', detail: '100 abstracts · fine-tuned Mistral Nemo', group: 'LLM comparison' },
  amd_repo_gpt_4o1_mini: { label: 'GPT-4o-mini', detail: '100 abstracts · GPT-4o-mini', group: 'LLM comparison' },
  amd_playground: { label: 'Playground', detail: 'Add your own relations here; the other graphs are read-only', group: 'Workspace' },
};

export const GROUP_ORDER: RepoInfo['group'][] = ['Knowledge graph', 'LLM comparison', 'Workspace', 'Other'];

export function repoInfo(id: string): RepoInfo {
  return REPO_INFO[id] ?? { label: id, detail: id, group: 'Other' };
}

/** Repositories grouped and ordered for display. */
export function groupRepositories(ids: string[]) {
  const known = Object.keys(REPO_INFO);
  const sorted = [...ids].sort((a, b) => {
    const ia = known.indexOf(a), ib = known.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
  });
  return GROUP_ORDER.map((group) => ({ group, ids: sorted.filter((id) => repoInfo(id).group === group) }))
    .filter((g) => g.ids.length);
}
