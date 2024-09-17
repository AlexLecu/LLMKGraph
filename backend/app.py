from flask import Flask, request, jsonify, make_response
from enrich_kg_mistral import return_relations, add_relations_to_kg
from reason import reason_and_update
from search_kg import query_knowledge_graph, delete_relation_kg
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/api/showRelations', methods=['POST'])
def show_relations():
    text = request.data
    relations = return_relations(text)

    response = make_response(jsonify(relations))

    return response

@app.route('/api/addRelations', methods=['POST'])
def add_relations():
    modified_relations = request.get_json()
    add_relations_to_kg(modified_relations)

    response = make_response("{\"status\": \"Successfully completed\"}")

    return response


@app.route('/api/reason', methods=['GET'])
def reason_kg():
    reason_and_update()
    response = make_response("{\"status\": \"Successfully completed\"}")

    return response


@app.route('/api/search', methods=['GET'])
def search():
    query_text = request.args.get('q', '')
    filter_type = request.args.get('type', '')

    data = query_knowledge_graph(query_text, filter_type)
    response = make_response(jsonify(data))

    return response


@app.route('/api/deleteRelation', methods=['POST'])
def delete_relation():
    data = request.json

    subject = data.get('subject')
    predicate = data.get('predicate')
    object_ = data.get('object')

    delete_relation_kg(subject, predicate, object_)

    response = make_response("{\"status\": \"Successfully completed\"}")

    return response


if __name__ == '__main__':
    app.run(debug=True)
