from flask import Flask, request, jsonify, make_response, send_file
from enrich_kg_gpt import return_relations, add_relations_to_kg
from disambiguation.reason import reason_and_update
from search_kg import query_knowledge_graph, delete_relation_kg, validate_repo_id
from bulk_relations import extract_relations, add_bulk_relations_to_kg
from flask_cors import CORS
import evaluation_stats
import re
import requests
import tempfile
import json
import os

app = Flask(__name__)
# Restrict browser origins in production via CORS_ORIGINS="https://my-frontend.example"
# (comma separated). "*" keeps the permissive development behaviour.
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
CORS(app, origins="*" if _cors_origins == ["*"] else _cors_origins)


GRAPHDB_URL = os.getenv('GRAPHDB_URL', 'http://localhost:7200')
AVAILABLE_MODELS = ["model_a", "model_b", "model_c", "model_d"]

# READ_ONLY=1 turns the API into a browse-only demo: every endpoint that writes
# to the graph or calls a paid LLM answers 403 instead.
READ_ONLY = os.getenv("READ_ONLY", "0") == "1"
WRITE_ENDPOINTS = {"show_relations", "add_relations", "reason_kg", "delete_relation",
                   "upload_abstract", "upload_relations"}

# EMBEDDED_STORE=1 serves the knowledge graph from an in-process rdflib store
# (see embedded_store.py) instead of an external GraphDB.
if os.getenv("EMBEDDED_STORE", "0") == "1":
    import embedded_store
    embedded_store.load_from_env()
    app.register_blueprint(embedded_store.bp)


@app.before_request
def _block_writes_when_read_only():
    if READ_ONLY and request.endpoint in WRITE_ENDPOINTS:
        return jsonify({"error": "This public demo is read-only. Run the project locally to extract, add, delete or reason over relations."}), 403


@app.errorhandler(ValueError)
def handle_value_error(error):
    # Raised by validate_repo_id / validate_local_name on malformed identifiers
    return jsonify({"error": str(error)}), 400


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "read_only": READ_ONLY})


@app.route('/api/showRelations', methods=['POST'])
def show_relations():
    text = request.data
    relations = return_relations(text)

    response = make_response(jsonify(relations))

    return response


@app.route('/api/addRelations', methods=['POST'])
def add_relations():
    json_file = request.get_json()
    add_relations_to_kg(json_file["relations"], validate_repo_id(json_file["repo_id"]))

    response = make_response("{\"status\": \"Successfully completed\"}")

    return response


@app.route('/api/reason', methods=['GET'])
def reason_kg():
    repo_id = validate_repo_id(request.args.get('repo_id', ''))

    reason_and_update(repo_id)
    response = make_response("{\"status\": \"Successfully completed\"}")

    return response


@app.route('/api/sparql', methods=['POST'])
def sparql_proxy():
    """Read-only SPARQL proxy so the browser never talks to GraphDB directly
    (no CORS setup needed, GraphDB can stay private)."""
    body = request.get_json(silent=True) or {}
    repo_id = validate_repo_id(body.get("repo_id", ""))
    query = body.get("query", "")
    if not isinstance(query, str) or not query.strip():
        return jsonify({"error": "query is required"}), 400
    # Prefix declarations may precede the query form; look for the first keyword
    form = re.search(r'\b(SELECT|ASK|CONSTRUCT|DESCRIBE|INSERT|DELETE|LOAD|CLEAR|DROP|CREATE)\b', query, re.I)
    if not form or form.group(1).upper() not in ("SELECT", "ASK", "CONSTRUCT", "DESCRIBE"):
        return jsonify({"error": "Only read-only SPARQL queries are allowed here"}), 400
    try:
        response = requests.post(
            f"{GRAPHDB_URL}/repositories/{repo_id}",
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=60,
        )
    except requests.RequestException as e:
        return jsonify({"error": f"GraphDB not reachable: {e}"}), 502
    if response.status_code != 200:
        return jsonify({"error": f"GraphDB answered {response.status_code}", "detail": response.text[:500]}), 502
    return app.response_class(response.content, status=200, mimetype="application/sparql-results+json")


@app.route('/api/search', methods=['GET'])
def search():
    query_text = request.args.get('q', '')
    filter_type = request.args.get('type', '')
    repo_id = request.args.get('repo_id', '')

    data = query_knowledge_graph(query_text, filter_type, repo_id)
    response = make_response(jsonify(data))

    return response


@app.route('/api/deleteRelation', methods=['POST'])
def delete_relation():
    data = request.json

    subject = data.get('subject')
    predicate = data.get('predicate')
    object_ = data.get('object')

    repo_id = data.get("repo_id")
    relation = data.get("relation")  # REL_... id for reified relations (optional)

    delete_relation_kg(subject, predicate, object_, repo_id, relation=relation)

    response = make_response("{\"status\": \"Successfully completed\"}")

    return response


@app.route("/api/evaluation", methods=["GET"])
def evaluation():
    """Compare the LLM-specific repositories (?repos=a,b,c; default EVAL_REPOS)."""
    repos = [validate_repo_id(r.strip()) for r in request.args.get("repos", "").split(",") if r.strip()]
    try:
        return jsonify(evaluation_stats.compare(repos))
    except requests.RequestException as e:
        return jsonify({"error": f"GraphDB unavailable: {e}"}), 502


@app.route("/api/available_repositories", methods=["GET"])
def available_repositories():
    try:
        response = requests.get(f"{GRAPHDB_URL}/rest/repositories", headers={"Accept": "application/json"}, timeout=15)
        if response.status_code == 200:
            repos = response.json()
            available_repos = [
                {
                    "id": repo["id"],
                }
                for repo in repos
            ]
            return jsonify(available_repos)
        else:
            return jsonify({"error": "Failed to fetch repositories"}), response.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/upload_abstract", methods=["POST"])
def upload_abstract():
    if 'file' not in request.files or 'model' not in request.form:
        return jsonify({"error": "File and model are required"}), 400

    file = request.files['file']
    model = request.form.get("model")

    if model not in AVAILABLE_MODELS:
        return jsonify({"error": "Invalid model selected"}), 400

    try:
        content = json.loads(file.read().decode('utf-8'))
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON file"}), 400
    relations = extract_relations(content, model)

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    with open(temp_file.name, 'w', encoding='utf-8') as f:
        json.dump(relations, f, ensure_ascii=False, indent=2)

    return send_file(temp_file.name, as_attachment=True, download_name="extracted_relations.json",
                     mimetype="application/json")


@app.route("/api/upload_relations", methods=["POST"])
def upload_relations():
    if 'file' not in request.files or 'repo_id' not in request.form:
        return jsonify({"error": "File and repository ID are required"}), 400

    file = request.files['file']
    repo_id = validate_repo_id(request.form.get("repo_id"))

    try:
        relations = json.load(file)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON file"}), 400
    add_bulk_relations_to_kg(relations, repo_id)

    response = make_response("{\"status\": \"Successfully completed\"}")

    return response


if __name__ == '__main__':
    # Debug mode exposes the Werkzeug interactive debugger (remote code execution
    # for anyone who can reach the port). Keep it off unless FLASK_DEBUG=1.
    app.run(host=os.getenv("FLASK_HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", "5555")),
            debug=os.getenv("FLASK_DEBUG", "0") == "1")
