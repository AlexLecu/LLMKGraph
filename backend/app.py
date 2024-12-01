from flask import Flask, request, jsonify, make_response, send_file
from enrich_kg_gpt import return_relations, add_relations_to_kg
from reason import reason_and_update
from search_kg import query_knowledge_graph, delete_relation_kg
from bulk_relations import extract_relations, add_bulk_relations_to_kg
from flask_cors import CORS
import requests
import tempfile
import json

app = Flask(__name__)
CORS(app)


GRAPHDB_REPO_URL = "http://graphdb:7200/rest/repositories"
AVAILABLE_MODELS = ["model_a", "model_b", "model_c"]


@app.route('/api/showRelations', methods=['POST'])
def show_relations():
    text = request.data
    relations = return_relations(text)

    response = make_response(jsonify(relations))

    return response


@app.route('/api/addRelations', methods=['POST'])
def add_relations():
    json_file = request.get_json()
    add_relations_to_kg(json_file["relations"], json_file["repo_id"])

    response = make_response("{\"status\": \"Successfully completed\"}")

    return response


@app.route('/api/reason', methods=['GET'])
def reason_kg():
    repo_id = request.args.get('repo_id', '')

    reason_and_update(repo_id)
    response = make_response("{\"status\": \"Successfully completed\"}")

    return response


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

    repo_id = request.form.get("repo_id")

    delete_relation_kg(subject, predicate, object_, repo_id)

    response = make_response("{\"status\": \"Successfully completed\"}")

    return response


@app.route("/api/available_repositories", methods=["GET"])
def available_repositories():
    try:
        response = requests.get(GRAPHDB_REPO_URL, headers={"Accept": "application/json"})
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
    repo_id = request.form.get("repo_id")

    relations = json.load(file)
    add_bulk_relations_to_kg(relations, repo_id)

    response = make_response("{\"status\": \"Successfully completed\"}")

    return response


if __name__ == '__main__':
    app.run(debug=True)
