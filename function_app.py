import os
import azure.functions as func
import logging
import requests
from pymongo import MongoClient

app = func.FunctionApp()

@app.timer_trigger(schedule="0 0 8 * * *", arg_name="myTimer", run_on_startup=False, use_monitor=False)
def ScraperOportunia(myTimer: func.TimerRequest) -> None:
    logging.info('A iniciar recolha de vagas nacionais no ITJobs...')

    # 1. Puxar as chaves de forma segura do local.settings.json
    LIGACAO = os.environ.get("LIGACAO_COSMOS")
    CHAVE_ITJOBS = os.environ.get("API_KEY_ITJOBS")

    if not LIGACAO or not CHAVE_ITJOBS:
        logging.error("ERRO: Faltam as chaves no local.settings.json!")
        return

    try:
        # 2. Ligar ao teu Cosmos DB
        client = MongoClient(LIGACAO, tlsAllowInvalidCertificates=True)
        db = client["OportuniaDB"]
        colecao = db["Vagas"]
        colecao.delete_many({}) 
        logging.info("Base de dados limpa. A iniciar recolha fresca...")

        total_guardado = 0
        
        # 3. Vamos buscar as primeiras 2 páginas (50 resultados cada = 100 vagas)
        for pagina in range(1, 3):
            # Filtramos por tecnologias base para o vosso curso
            url = f"https://api.itjobs.pt/job/search.json?api_key={CHAVE_ITJOBS}&limit=50&page={pagina}"
            
            # Criar um "disfarce" de navegador normal
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            # Fazer o pedido com o disfarce incluído
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                vagas = response.json().get('results', [])
                
                for item in vagas:
                    # Garantir que não dá erro se a vaga não tiver localização
                    localizacao = "Portugal / Remoto"
                    if 'locations' in item and len(item['locations']) > 0:
                        localizacao = item['locations'][0]['name']

                    vaga = {
                        "id_vaga": str(item['id']),
                        "titulo": item['title'],
                        "empresa": item['company']['name'],
                        "local": localizacao,
                        "fonte": "ITJobs.pt",
                        "data_publicacao": item.get('publishedAt', 'Recente')
                    }
                    
                    # Guarda na base de dados (se a vaga já existir, ele só atualiza e não duplica)
                    colecao.update_one({"id_vaga": vaga["id_vaga"]}, {"$set": vaga}, upsert=True)
                    total_guardado += 1
                
                logging.info(f"Página {pagina} processada com sucesso.")
            else:
                logging.error(f"Erro ao contactar o ITJobs. Código: {response.status_code}")
                break # Para se o site bloquear o acesso

        logging.info(f"RECOLHA CONCLUÍDA! Total de {total_guardado} vagas atualizadas no Cosmos DB.")

    except Exception as e:
        logging.error(f"Ocorreu um erro fatal no Scraper: {e}")