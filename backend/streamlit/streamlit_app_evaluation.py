import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
from SPARQLWrapper import SPARQLWrapper, JSON


def main():
    st.title("Graph Comparison App")
    st.write("Compare the graphs generated using the same data but different LLMs, stored across multiple repositories.")

    # Repositories and their SPARQL endpoints with actual names
    repositories = {
        "amd_repo_gpt_35": "http://graphdb:7200/repositories/amd_repo_gpt_35",
        "amd_repo_mistral": "http://graphdb:7200/repositories/amd_repo_mistral",
        "amd_repo_gpt_4o1_mini": "http://graphdb:7200/repositories/amd_repo_gpt_4o1_mini"
    }

    # The graph URI to be used across all repositories
    graph_uri = "http://amddata.org/amd/"

    # Sidebar for evaluation options
    st.sidebar.header("Select Evaluation Metrics")
    evaluation_options = [
        "Node Count",
        "Edge Count",
        "Degree Distribution",
        "Average Degree",
        "Clustering Coefficient",
        "Triple Analysis",
        "Entity Type Analysis"
    ]
    evaluation_metrics = st.sidebar.multiselect(
        "Evaluation Metrics", evaluation_options, default=evaluation_options
    )

    # Fetch data from all repositories
    graphs_data = {}
    data_frames = {}
    for repo_name, endpoint in repositories.items():
        G, df = fetch_graph_data(endpoint, graph_uri)
        if G is not None and df is not None:
            graphs_data[repo_name] = G
            data_frames[repo_name] = df
        else:
            st.error(f"No data found in repository '{repo_name}' for graph '{graph_uri}'.")

    if data_frames:
        if not evaluation_metrics:
            st.warning("Please select at least one evaluation metric.")
        else:
            tabs = st.tabs(evaluation_metrics)
            for tab, metric in zip(tabs, evaluation_metrics):
                with tab:
                    if metric == "Node Count":
                        compare_node_count(graphs_data)
                    elif metric == "Edge Count":
                        compare_edge_count(graphs_data)
                    elif metric == "Degree Distribution":
                        compare_degree_distribution(graphs_data)
                    elif metric == "Average Degree":
                        compare_average_degree(graphs_data)
                    elif metric == "Clustering Coefficient":
                        compare_clustering_coefficient(graphs_data)
                    elif metric == "Triple Analysis":
                        compare_triples(data_frames)
                    elif metric == "Entity Type Analysis":
                        analyze_entity_types(data_frames)
                    else:
                        st.write(f"Unknown metric: {metric}")
    else:
        st.error("No valid data found in any of the repositories.")


def fetch_graph_data(endpoint_url, graph_uri=None):
    # Function to fetch triples from a specific named graph or default graph
    sparql = SPARQLWrapper(endpoint_url)
    if graph_uri:
        query = f"""
        SELECT ?s ?p ?o WHERE {{
          GRAPH <{graph_uri}> {{ ?s ?p ?o }}
        }}
        """
    else:
        query = """
        SELECT ?s ?p ?o WHERE {
          ?s ?p ?o
        }
        """
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    try:
        results = sparql.query().convert()
    except Exception as e:
        st.error(f"Error fetching data from endpoint {endpoint_url}: {e}")
        return None, None

    # Check if results are empty
    if len(results["results"]["bindings"]) == 0:
        return None, None

    # Convert results to a DataFrame
    data = pd.DataFrame([
        {
            'Subject': result['s']['value'],
            'Predicate': result['p']['value'],
            'Object': result['o']['value']
        } for result in results["results"]["bindings"]
    ])

    # Define the get_label function
    def get_label(uri):
        if '#' in uri:
            return uri.split('#')[-1]
        elif '/' in uri:
            return uri.rstrip('/').split('/')[-1]
        else:
            return uri

    # Apply get_label function to extract labels
    data['Subject'] = data['Subject'].apply(get_label)
    data['Predicate'] = data['Predicate'].apply(get_label)
    data['Object'] = data['Object'].apply(get_label)

    # Create a NetworkX graph
    G = nx.DiGraph()
    for idx, row in data.iterrows():
        G.add_edge(row['Subject'], row['Object'], predicate=row['Predicate'])

    return G, data


def compare_node_count(graphs_data):
    st.subheader("Node Count Comparison")
    node_counts = {
        repo_name: G.number_of_nodes()
        for repo_name, G in graphs_data.items()
    }
    for repo_name, count in node_counts.items():
        st.write(f"**{count} nodes** in repository '{repo_name}'")
    # Bar chart comparison
    df = pd.DataFrame.from_dict(node_counts, orient='index', columns=['Node Count'])
    st.bar_chart(df)


def compare_edge_count(graphs_data):
    st.subheader("Edge Count Comparison")
    edge_counts = {
        repo_name: G.number_of_edges()
        for repo_name, G in graphs_data.items()
    }
    for repo_name, count in edge_counts.items():
        st.write(f"**{count} edges** in repository '{repo_name}'")
    # Bar chart comparison
    df = pd.DataFrame.from_dict(edge_counts, orient='index', columns=['Edge Count'])
    st.bar_chart(df)


def compare_degree_distribution(graphs_data):
    st.subheader("Degree Distribution Comparison")
    fig, ax = plt.subplots()
    for repo_name, G in graphs_data.items():
        degrees = [degree for node, degree in G.degree()]
        degree_counts = pd.Series(degrees).value_counts().sort_index()
        ax.plot(degree_counts.index, degree_counts.values, marker='o', linestyle='-', label=repo_name)
    ax.set_xlabel('Degree')
    ax.set_ylabel('Frequency')
    ax.set_yscale('log')
    ax.set_xscale('log')
    ax.legend()
    st.pyplot(fig)


def compare_average_degree(graphs_data):
    st.subheader("Average Degree Comparison")
    avg_degrees = {}
    for repo_name, G in graphs_data.items():
        avg_degree = sum(dict(G.degree()).values()) / G.number_of_nodes()
        avg_degrees[repo_name] = avg_degree
        st.write(f"**{avg_degree:.2f} average degree** in repository '{repo_name}'")
    # Bar chart comparison
    df = pd.DataFrame.from_dict(avg_degrees, orient='index', columns=['Average Degree'])
    st.bar_chart(df)


def compare_clustering_coefficient(graphs_data):
    st.subheader("Clustering Coefficient Comparison")
    clustering_coeffs = {}
    for repo_name, G in graphs_data.items():
        clustering = nx.average_clustering(G.to_undirected())
        clustering_coeffs[repo_name] = clustering
        st.write(f"**{clustering:.4f} average clustering coefficient** in repository '{repo_name}'")
    # Bar chart comparison
    df = pd.DataFrame.from_dict(clustering_coeffs, orient='index', columns=['Average Clustering Coefficient'])
    st.bar_chart(df)


def compare_triples(data_frames):
    st.subheader("Triple Analysis (Subject-Predicate-Object)")

    # Gather triples from each repository
    triples = {}
    stats_list = {}
    for repo_name, df in data_frames.items():
        # Filter out 'type' relations
        df_filtered = df[~df['Predicate'].isin(['type', 'rdf:type'])]

        triples[repo_name] = set(zip(df_filtered['Subject'], df_filtered['Predicate'], df_filtered['Object']))

        # Calculate statistics
        stats = calculate_statistics(df_filtered, repo_name)
        stats_list[repo_name] = stats

        # Display statistics
        st.write(f"### Repository '{repo_name}'")
        st.write(f"**Total Triples (excluding 'type'):** {stats['Total Entries']}")
        st.write(f"**Unique Subjects:** {stats['Unique Subjects']}")
        st.write(f"**Unique Predicates:** {stats['Unique Predicates']}")
        st.write(f"**Unique Objects:** {stats['Unique Objects']}")

        # Display top entities
        st.write("#### Top Subjects")
        st.write(pd.DataFrame.from_dict(stats['Top Subjects'], orient='index', columns=['Count']))

        st.write("#### Top Predicates")
        st.write(pd.DataFrame.from_dict(stats['Top Predicates'], orient='index', columns=['Count']))

        st.write("#### Top Objects")
        st.write(pd.DataFrame.from_dict(stats['Top Objects'], orient='index', columns=['Count']))

        # Plot top entities
        plot_top_entities(df_filtered, 'Subject', f"Top 10 Subjects in Repository '{repo_name}'")
        plot_top_entities(df_filtered, 'Predicate', f"Top 10 Predicates in Repository '{repo_name}'")
        plot_top_entities(df_filtered, 'Object', f"Top 10 Objects in Repository '{repo_name}'")

        # Plot predicate distribution
        plot_relation_distribution(df_filtered, f"Predicate Distribution in Repository '{repo_name}'")

        # Plot co-occurrence heatmap
        plot_cooccurrence_heatmap(df_filtered, f"Subject-Object Co-occurrence Matrix for Repository '{repo_name}'")

    # Existing code for triple comparisons
    st.write("### Triple Comparison Across Repositories")

    all_repos = set(triples.keys())

    # Common triples
    common_triples = set.intersection(*triples.values())
    st.write(f"**{len(common_triples)} triples** are common across all repositories (excluding 'type').")

    # Unique triples
    for repo_name in all_repos:
        unique_triples = triples[repo_name] - set.union(*(triples[r] for r in all_repos - {repo_name}))
        st.write(f"**{len(unique_triples)} unique triples** in repository '{repo_name}' (excluding 'type').")
        if st.checkbox(f"Show unique triples in repository '{repo_name}'", key=f"unique_triples_{repo_name}"):
            unique_triples_df = pd.DataFrame(list(unique_triples), columns=['Subject', 'Predicate', 'Object'])
            st.dataframe(unique_triples_df)

    # Triple overlap matrix
    st.write("### Triple Overlap Matrix")
    repo_list = list(all_repos)
    overlap_matrix = pd.DataFrame(index=repo_list, columns=repo_list, dtype=int)
    for repo1 in repo_list:
        for repo2 in repo_list:
            if repo1 == repo2:
                overlap_matrix.loc[repo1, repo2] = len(triples[repo1])
            else:
                overlap = len(triples[repo1].intersection(triples[repo2]))
                overlap_matrix.loc[repo1, repo2] = overlap
    st.dataframe(overlap_matrix)


def calculate_statistics(df, name):
    stats = {
        'Name': name,
        'Total Entries': len(df),
        'Unique Subjects': df['Subject'].nunique(),
        'Unique Predicates': df['Predicate'].nunique(),
        'Unique Objects': df['Object'].nunique(),
        'Top Subjects': df['Subject'].value_counts().head(5).to_dict(),
        'Top Predicates': df['Predicate'].value_counts().head(5).to_dict(),
        'Top Objects': df['Object'].value_counts().head(5).to_dict(),
    }
    return stats


def plot_top_entities(df, entity, title):
    top_entities = df[entity].value_counts().head(10)
    fig, ax = plt.subplots()
    sns.barplot(y=top_entities.index, x=top_entities.values, palette='viridis', ax=ax)
    ax.set_title(title)
    ax.set_xlabel('Count')
    ax.set_ylabel(entity)
    st.pyplot(fig)


def plot_relation_distribution(df, title):
    relation_dist = df['Predicate'].value_counts()
    fig, ax = plt.subplots()
    ax.pie(relation_dist.values, labels=relation_dist.index, autopct='%1.1f%%', startangle=140,
           colors=sns.color_palette('viridis', len(relation_dist)))
    ax.set_title(title)
    st.pyplot(fig)


def plot_cooccurrence_heatmap(df, title):
    # Limit to top 20 subjects and objects to keep the heatmap readable
    top_subjects = df['Subject'].value_counts().head(20).index
    top_objects = df['Object'].value_counts().head(20).index
    filtered_df = df[df['Subject'].isin(top_subjects) & df['Object'].isin(top_objects)]
    cooccurrence_matrix = pd.crosstab(filtered_df['Subject'], filtered_df['Object'])
    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(cooccurrence_matrix, cmap='viridis', annot=True, fmt='d', ax=ax)
    ax.set_title(title)
    st.pyplot(fig)


def analyze_entity_types(data_frames):
    st.subheader("Entity Type Analysis")

    # For each repository, extract types of entities
    entity_types = {}
    for repo_name, df in data_frames.items():
        # Filter triples where predicate is 'type' or 'rdf:type'
        type_triples = df[df['Predicate'].isin(['type', 'rdf:type'])]
        if type_triples.empty:
            st.write(f"No type information found in repository '{repo_name}'.")
            continue
        types = type_triples['Object'].value_counts()
        entity_types[repo_name] = types
        st.write(f"### Repository '{repo_name}'")
        st.write(f"**Number of entity types:** {len(types)}")
        st.bar_chart(types.head(20))  # Show top 20 types

    # Compare types across repositories
    if entity_types:
        all_types = set.union(*(set(types.index) for types in entity_types.values()))
        type_presence = pd.DataFrame(index=list(all_types))
        for repo_name, types in entity_types.items():
            type_presence[repo_name] = type_presence.index.isin(types.index)

        st.write("### Entity Type Presence Across Repositories")
        st.dataframe(type_presence.fillna(False).astype(bool))

        # Common types
        common_types = set.intersection(*(set(types.index) for types in entity_types.values()))
        st.write(f"**{len(common_types)} entity types** are common across all repositories.")
        if st.checkbox("Show common entity types"):
            st.write(common_types)

        # Unique types
        for repo_name in entity_types:
            other_types = set.union(*(set(entity_types[r].index) for r in entity_types if r != repo_name))
            unique_types = set(entity_types[repo_name].index) - other_types
            st.write(f"**{len(unique_types)} unique entity types** in repository '{repo_name}'.")
            if st.checkbox(f"Show unique entity types in repository '{repo_name}'", key=f"unique_types_{repo_name}"):
                st.write(unique_types)
    else:
        st.write("No type information available for comparison.")


def get_label(uri):
    if '#' in uri:
        return uri.split('#')[-1]
    elif '/' in uri:
        return uri.rstrip('/').split('/')[-1]
    else:
        return uri


if __name__ == "__main__":
    main()
