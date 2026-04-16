from flask import Flask, jsonify, request
from pymongo import MongoClient
import os

app = Flask(__name__)

# Para a Cloud, usamos a variável de ambiente. Para testar no teu PC, coloca a tua string de ligação aqui temporariamente
MONGO_URI = os.environ.get("LIGACAO_COSMOS", "mongodb://cosmos-oportunia-67g5yzourkqaa:H1CxqnwKIj1ow9E3l2Pezdimyz3VY2T2YhXbYrzPLRbPrGVuHszjSaxsf2yzklOWfEP8i7tjPhlqACDbZjmPQg==@cosmos-oportunia-67g5yzourkqaa.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@cosmos-oportunia-67g5yzourkqaa@")
client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
db = client["OportuniaDB"]

@app.route('/api/vagas', methods=['GET'])
def obter_vagas():
    # Vai à coleção Vagas que o Gonçalo configurou e devolve tudo
    vagas = list(db["Vagas"].find({}, {'_id': 0}))
    return jsonify(vagas)

@app.route('/api/perfil', methods=['POST'])
def guardar_perfil():
    # Recebe os dados do Frontend (Bernardo) e guarda na base de dados
    dados_utilizador = request.json
    db["Utilizadores"].insert_one(dados_utilizador)
    return jsonify({"mensagem": "O perfil foi guardado com sucesso!"}), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)