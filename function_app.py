import azure.functions as func
import logging
import requests
from pymongo import MongoClient

app = func.FunctionApp()

LIGACAO = "mongodb://cosmos-oportunia-67g5yzourkqaa:H1CxqnwKIj1ow9E3l2Pezdimyz3VY2T2YhXbYrzPLRbPrGVuHszjSaxsf2yzklOWfEP8i7tjPhlqACDbZjmPQg==@cosmos-oportunia-67g5yzourkqaa.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@cosmos-oportunia-67g5yzourkqaa@"

@app.timer_trigger(schedule="0 0 8 * * *", arg_name="myTimer", run_on_startup=False, use_monitor=False)
def ScraperOportunia(myTimer: func.TimerRequest) -> None:
    logging.info('O motor Oportunia iniciou a recolha MASSIVA de informática...')

    # Ligação ao Cosmos DB
    client = MongoClient(LIGACAO, tlsAllowInvalidCertificates=True)
    db = client["OportuniaDB"]
    colecao = db["Vagas"]

    total_guardado = 0
    # Vamos percorrer as páginas 1 a 5 (Total de 100 vagas potenciais)
    for pagina in range(1, 6):
        url = f"https://www.themuse.com/api/public/jobs?category=Software%20Engineering&category=Computer%20Science&page={pagina}"
        
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                vagas = response.json().get('results', [])
                
                for item in vagas:
                    vaga = {
                        "id_vaga": str(item['id']),
                        "titulo": item['name'],
                        "empresa": item['company']['name'],
                        "local": item['locations'][0]['name'] if item['locations'] else "Remoto",
                        "fonte": "The Muse API",
                        "pagina_origem": pagina
                    }
                    # Upsert garante que se a vaga já existir, não cria duplicados
                    colecao.update_one({"id_vaga": vaga["id_vaga"]}, {"$set": vaga}, upsert=True)
                    total_guardado += 1
                
                logging.info(f"Página {pagina} processada com sucesso.")
            else:
                break # Pára se houver erro no site

        except Exception as e:
            logging.error(f"Erro na página {pagina}: {e}")
            break

    logging.info(f"RECOLHA CONCLUÍDA! Total de {total_guardado} vagas no Cosmos DB.")