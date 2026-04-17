from flask import Flask, jsonify, request, render_template
from pymongo import MongoClient
import os

app = Flask(__name__)

MONGO_URI = os.environ.get("LIGACAO_COSMOS", "mongodb://cosmos-oportunia-67g5yzourkqaa:H1CxqnwKIj1ow9E3l2Pezdimyz3VY2T2YhXbYrzPLRbPrGVuHszjSaxsf2yzklOWfEP8i7tjPhlqACDbZjmPQg==@cosmos-oportunia-67g5yzourkqaa.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@cosmos-oportunia-67g5yzourkqaa@")
client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
db = client["OportuniaDB"]

# 1. PÁGINA INICIAL (Pública - Landing Page)
@app.route('/')
def index():
    return render_template('index.html')

# 2. PÁGINA DE LOGIN (Pública)
@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/registo')
def registo():
    return render_template('registo.html')

# 3. DASHBOARD / OPORTUNIDADES (Privada - Requer Login)
@app.route('/oportunidades')
def oportunidades():
    # Vai buscar as vagas à BD
    try:
        vagas = list(db["Vagas"].find({}, {'_id': 0}))
    except:
        vagas = []

    return render_template('dashboard.html', vagas=vagas, nome_utilizador="Bernardo")

# 4. PERFIL DO UTILIZADOR (Privada)
@app.route('/perfil')
def perfil():
    return render_template('perfil.html', nome_utilizador="Bernardo")

if __name__ == '__main__':
    # O use_reloader=False evita aquele erro do Windows que tiveste há bocado!
    app.run(host='0.0.0.0', port=8000, debug=True, use_reloader=False)