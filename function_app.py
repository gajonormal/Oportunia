import os
import azure.functions as func
import logging
import requests
import re
from pymongo import MongoClient

app = func.FunctionApp()

# ==========================================
# TRABALHADORES (Funções de Extração)
# ==========================================

# --- TRABALHADOR 1: ITJobs ---
def extrair_itjobs(chave):
    vagas_formatadas = []
    if not chave:
        logging.warning("Aviso: Chave ITJobs em falta. A saltar esta fonte...")
        return vagas_formatadas
        
    for pagina in range(1, 3):  # Vai buscar as primeiras 2 páginas (100 vagas máx)
        url = f"https://api.itjobs.pt/job/search.json?api_key={chave}&limit=50&page={pagina}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                vagas = response.json().get('results', [])
                for item in vagas:
                    localizacao = "Portugal / Remoto"
                    if 'locations' in item and len(item['locations']) > 0:
                        localizacao = item['locations'][0]['name']

                    descricao_raw = item.get('body', '')
                    descricao_limpa = re.sub(r'<[^>]+>', '', descricao_raw).strip()
                    
                    tipo_vaga = "Emprego"
                    if 'types' in item and len(item['types']) > 0:
                        tipo_vaga = item['types'][0].get('name', 'Emprego')

                    vaga = {
                        "id_vaga": f"itjobs_{item['id']}",
                        "titulo": item['title'],
                        "empresa": item['company']['name'],
                        "local": localizacao,
                        "fonte": "ITJobs.pt",
                        "data_publicacao": item.get('publishedAt', 'Recente'),
                        "descricao": descricao_limpa,
                        "salario": item.get('wage', ''),
                        "tipo": tipo_vaga,
                        "url": f"https://www.itjobs.pt/oferta/{item['id']}"
                    }
                    vagas_formatadas.append(vaga)
        except Exception as e:
            logging.error(f"Erro ao extrair do ITJobs: {e}")
            
    return vagas_formatadas


# --- TRABALHADOR 2: Jooble ---
def extrair_jooble(chave):
    vagas_formatadas = []
    if not chave:
        logging.warning("Aviso: Chave do Jooble em falta. A saltar esta fonte...")
        return vagas_formatadas
        
    url = f"https://pt.jooble.org/api/{chave}"
    headers = {"Content-type": "application/json"}
    body = {
        "keywords": "IT",
        "location": "Portugal",
        "resultonpage": 50
    }
    
    try:
        response = requests.post(url, headers=headers, json=body, timeout=15)
        if response.status_code == 200:
            vagas = response.json().get('jobs', [])
            for item in vagas:
                descricao_raw = item.get('snippet', '')
                descricao_limpa = re.sub(r'<[^>]+>', '', descricao_raw).strip()
                
                vaga = {
                    "id_vaga": f"jooble_{item.get('id', '')}",
                    "titulo": item.get('title', 'Sem título'),
                    "empresa": item.get('company', 'Confidencial'),
                    "local": item.get('location', 'Portugal'),
                    "fonte": "Jooble",
                    "data_publicacao": item.get('updated', 'Recente'),
                    "descricao": descricao_limpa,
                    "salario": item.get('salary', ''),
                    "tipo": item.get('type', 'Emprego'),
                    "url": item.get('link', '#')
                }
                vagas_formatadas.append(vaga)
    except Exception as e:
        logging.error(f"Erro ao extrair do Jooble: {e}")
        
    return vagas_formatadas


# --- TRABALHADOR 3: Remotive (Não precisa de chave) ---
def extrair_remotive():
    vagas_formatadas = []
    url = "https://remotive.com/api/remote-jobs?category=software-dev&limit=50"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            vagas = response.json().get('jobs', [])
            for item in vagas:
                descricao_raw = item.get('description', '')
                descricao_limpa = re.sub(r'<[^>]+>', '', descricao_raw).strip()
                
                vaga = {
                    "id_vaga": f"remotive_{item.get('id', '')}",
                    "titulo": item.get('title', 'Sem título'),
                    "empresa": item.get('company_name', 'Confidencial'),
                    "local": item.get('candidate_required_location', 'Remoto Global'),
                    "fonte": "Remotive",
                    "data_publicacao": item.get('publication_date', 'Recente'),
                    "descricao": descricao_limpa,
                    "salario": item.get('salary', ''),
                    "tipo": item.get('job_type', 'Emprego'),
                    "url": item.get('url', '#')
                }
                vagas_formatadas.append(vaga)
    except Exception as e:
        logging.error(f"Erro ao extrair do Remotive: {e}")
        
    return vagas_formatadas


# ==========================================
# ORQUESTRADOR (A Função Principal)
# ==========================================

@app.timer_trigger(schedule="0 0 8 * * *", arg_name="myTimer", run_on_startup=False, use_monitor=False)
def ScraperOportunia(myTimer: func.TimerRequest) -> None:
    logging.info('A iniciar recolha de vagas (Multi-fontes)...')

    # 1. Puxar as chaves do ambiente
    LIGACAO = os.environ.get("LIGACAO_COSMOS")
    CHAVE_ITJOBS = os.environ.get("API_KEY_ITJOBS")
    CHAVE_JOOBLE = os.environ.get("API_KEY_JOOBLE")

    if not LIGACAO:
        logging.error("ERRO FATAL: Falta a ligação ao Cosmos DB no local.settings.json ou Azure!")
        return

    # 2. Executar os trabalhadores e receber as listas
    logging.info("A recolher do ITJobs...")
    lista_itjobs = extrair_itjobs(CHAVE_ITJOBS)
    
    logging.info("A recolher do Jooble...")
    lista_jooble = extrair_jooble(CHAVE_JOOBLE)
    
    logging.info("A recolher do Remotive (Remote IT)...")
    lista_remotive = extrair_remotive()
    
    # 3. Juntar tudo numa lista final
    todas_as_vagas = lista_itjobs + lista_jooble + lista_remotive
    
    if len(todas_as_vagas) == 0:
        logging.warning("Nenhuma vaga encontrada nas APIs. A abortar gravação.")
        return

    # 4. Guardar na Base de Dados Cosmos DB
    try:
        client = MongoClient(LIGACAO, tlsAllowInvalidCertificates=True)
        db = client["OportuniaDB"]
        colecao = db["Vagas"]
        
        colecao.delete_many({}) 
        logging.info(f"Base de dados limpa. A guardar {len(todas_as_vagas)} vagas no Cosmos DB...")

        total_guardado = 0
        for vaga in todas_as_vagas:
            # O upsert atualiza a vaga se o id já existir, ou cria uma nova se não existir
            colecao.update_one({"id_vaga": vaga["id_vaga"]}, {"$set": vaga}, upsert=True)
            total_guardado += 1

        logging.info(f"RECOLHA CONCLUÍDA! Total de {total_guardado} vagas guardadas.")

    except Exception as e:
        logging.error(f"Ocorreu um erro ao guardar na Base de Dados: {e}")