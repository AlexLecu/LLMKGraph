from flask import Flask, request, jsonify
from enrich_kg import return_relations, add_relations_to_kg
from reason import reason_and_update


app = Flask(__name__)

@app.route('/api/showRelations', methods=['POST'])
def show_relations():
    global relations
    text = request.data
    relations = return_relations(text)

    return jsonify(relations)


@app.route('/api/addRelations', methods=['POST'])
def add_relations():
    add_relations_to_kg(relations)

    return "{\"status\": \"Successfully completed\"}"


@app.route('/api/reason', methods=['GET'])
def reason_kg():
    reason_and_update()

    return "{\"status\": \"Successfully completed\"}"


if __name__ == '__main__':
    app.run(debug=True)
