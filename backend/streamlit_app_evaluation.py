import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
from SPARQLWrapper import SPARQLWrapper, JSON


def main():
    st.title("GraphDB Ontotext Graph Comparison App")
    st.write("Compare the same graph across multiple GraphDB Ontotext repositories.")

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
        "Diameter",
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
        st.header(f"Comparing Graph '{graph_uri}' across Repositories")
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
                    elif metric == "Diameter":
                        compare_diameter(graphs_data)
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
        ax.hist(
            degrees,
            bins=range(min(degrees), max(degrees)+2),
            alpha=0.5,
            label=repo_name
        )
    ax.set_xlabel('Degree')
    ax.set_ylabel('Frequency')
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


def compare_diameter(graphs_data):
    st.subheader("Diameter Comparison")
    diameters = {}
    for repo_name, G in graphs_data.items():
        # Compute diameter of the largest connected component
        try:
            components = nx.connected_components(G.to_undirected())
            largest_component = max(components, key=len)
            subgraph = G.subgraph(largest_component)
            diameter = nx.diameter(subgraph)
            diameters[repo_name] = diameter
            st.write(f"**{diameter} diameter** in repository '{repo_name}'")
        except Exception as e:
            diameter = float('inf')
            diameters[repo_name] = diameter
            st.warning(f"Could not compute diameter for repository '{repo_name}': {e}")
    # Bar chart comparison
    df = pd.DataFrame.from_dict(diameters, orient='index', columns=['Diameter'])
    st.bar_chart(df)


def compare_triples(data_frames):
    st.subheader("Triple Analysis (Subject-Predicate-Object)")

    # Gather triples from each repository
    triples = {}
    for repo_name, df in data_frames.items():
        triples[repo_name] = set(zip(df['Subject'], df['Predicate'], df['Object']))

    all_repos = set(triples.keys())

    # Common triples
    common_triples = set.intersection(*triples.values())
    st.write(f"**{len(common_triples)} triples** are common across all repositories.")

    # Unique triples
    for repo_name in all_repos:
        unique_triples = triples[repo_name] - set.union(*(triples[r] for r in all_repos - {repo_name}))
        st.write(f"**{len(unique_triples)} unique triples** in repository '{repo_name}'.")
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


def analyze_entity_types(data_frames):
    st.subheader("Entity Type Analysis")

    # For each repository, extract types of entities
    entity_types = {}
    for repo_name, df in data_frames.items():
        # Filter triples where predicate is rdf:type
        type_triples = df[df['Predicate'].isin([
            'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
            'rdf:type'
        ])]
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


if __name__ == "__main__":
    main()
