from flask import Flask, request, jsonify, make_response
from enrich_kg_mistral import return_relations, add_relations_to_kg
from reason import reason_and_update


app = Flask(__name__)

@app.route('/api/showRelations', methods=['POST'])
def show_relations():
    global relations
    text = request.data
    relations = return_relations(text)

    response = make_response(jsonify(relations))
    response.headers["Access-Control-Allow-Origin"] = "*"

    return response

@app.route('/api/addRelations', methods=['POST'])
def add_relations():
    add_relations_to_kg(relations)

    response = make_response("{\"status\": \"Successfully completed\"}")
    response.headers["Access-Control-Allow-Origin"] = "*"

    return response


@app.route('/api/reason', methods=['GET'])
def reason_kg():
    reason_and_update()

    response = make_response("{\"status\": \"Successfully completed\"}")
    response.headers["Access-Control-Allow-Origin"] = "*"

    return response


if __name__ == '__main__':
    app.run(debug=True)
