from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
from datetime import datetime
from functools import wraps
from openai import AzureOpenAI  
from dotenv import load_dotenv  #Carregar biblioteca para ler o ficheiro .env
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
import smtplib
from email.message import EmailMessage

# Carrega as variáveis de ambiente a partir do ficheiro .env local
load_dotenv()

app = Flask(__name__)

# Configurações dinâmicas lidas de forma segura a partir do ambiente local (.env)
app.secret_key = os.environ.get("SECRET_KEY", "chave-secreta-de-desenvolvimento")
serializer = URLSafeTimedSerializer(app.secret_key)

MONGO_URI = os.environ.get("LIGACAO_COSMOS", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
db = client["OportuniaDB"]

# Inicialização segura do cliente Azure OpenAI sem expor dados no código fonte
AI_CLIENT = AzureOpenAI(
    api_key=os.environ.get("AZURE_OPENAI_KEY"),
    api_version="2024-12-01-preview",
    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT")
)

# ─────────────────────────────────────────────
# Decorator: protege rotas que requerem login
# ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "utilizador_email" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# PÁGINAS PÚBLICAS
# ─────────────────────────────────────────────

@app.route("/")
def index():
    logado = "utilizador_email" in session
    nome = session.get("utilizador_nome", "") if logado else ""
    return render_template("index.html", logado=logado, nome_utilizador=nome)


@app.route("/login", methods=["GET"])
def login():
    if "utilizador_email" in session:
        return redirect(url_for("oportunidades"))
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login_post():
    try:
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("login.html", erro="Preenche todos os campos.")

        utilizador = db["Utilizadores"].find_one({"email": email})

        if not utilizador or not check_password_hash(utilizador["password_hash"], password):
            return render_template("login.html", erro="Email ou password incorretos.")

        session["utilizador_email"] = email
        session["utilizador_nome"] = utilizador.get("nome", "Utilizador")

        return redirect(url_for("oportunidades"))
    except Exception as e:
        import traceback
        erro_detalhado = traceback.format_exc()
        return f"<pre>Erro 500 Detalhado no Login:\n{erro_detalhado}</pre>", 500


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/registo", methods=["GET"])
def registo():
    if "utilizador_email" in session:
        return redirect(url_for("oportunidades"))
    return render_template("registo.html")


@app.route("/registo", methods=["POST"])
def registo_post():
    nome = request.form.get("nome", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not nome or not email or not password:
        return render_template("registo.html", erro="Preenche todos os campos.")

    if len(password) < 8:
        return render_template("registo.html", erro="A password deve ter pelo menos 8 caracteres.")

    if db["Utilizadores"].find_one({"email": email}):
        return render_template("registo.html", erro="Este email já está registado.")

    novo_utilizador = {
        "email": email,
        "password_hash": generate_password_hash(password),
        "nome": nome,
        "headline": "Estudante de Engenharia Informática",
        "instituicao": "Instituto Politécnico de Castelo Branco",
        "curso": "Licenciatura em Engenharia Informática",
        "links": {
            "github": "",
            "linkedin": "",
            "website": ""
        },
        "competencias_tecnicas": [],
        "cadeiras_favoritas": [],
        "localizacoes_preferidas": [],
        "tipos_oportunidade": [],
        "disponibilidade": "",
        "notificacoes": {
            "email_alertas": True,
            "relatorio_semanal": False
        },
        "data_registo": datetime.utcnow().isoformat(),
        "data_atualizacao": datetime.utcnow().isoformat()
    }

    db["Utilizadores"].insert_one(novo_utilizador)

    session["utilizador_email"] = email
    session["utilizador_nome"] = nome

    return redirect(url_for("perfil"))


# ─────────────────────────────────────────────
# PÁGINAS PRIVADAS
# ─────────────────────────────────────────────

@app.route("/oportunidades")
@login_required
def oportunidades():
    try:
        vagas = list(db["Vagas"].find({}, {"_id": 0}))
    except Exception as e:
        print(f"Erro ao obter vagas: {e}")
        vagas = []

    nome = session.get("utilizador_nome", "Utilizador")
    return render_template("dashboard.html", vagas=vagas, nome_utilizador=nome)


@app.route("/perfil", methods=["GET"])
@login_required
def perfil():
    email = session["utilizador_email"]
    utilizador = db["Utilizadores"].find_one({"email": email}, {"_id": 0, "password_hash": 0})

    if not utilizador:
        return redirect(url_for("logout"))

    return render_template("perfil.html", utilizador=utilizador)


# ─────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────

@app.route("/api/vagas", methods=["GET"])
def get_vagas_api():
    try:
        vagas = list(db["Vagas"].find({}, {"_id": 0}))
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    return jsonify(vagas)


@app.route("/api/perfil", methods=["GET"])
@login_required
def get_perfil():
    email = session["utilizador_email"]
    utilizador = db["Utilizadores"].find_one({"email": email}, {"_id": 0, "password_hash": 0})
    if not utilizador:
        return jsonify({"erro": "Utilizador não encontrado"}), 404
    return jsonify(utilizador)


@app.route("/api/recomendacoes", methods=["GET"])
@login_required
def get_recomendacoes():
    """
    Endpoint assíncrono chamado pela dashboard.
    Pede ao GPT-4o que analise o perfil do utilizador e devolva
    as vagas ordenadas por relevância com uma justificação personalizada
    para cada uma, em JSON estruturado.
    """
    email = session["utilizador_email"]

    # 1. Carregar perfil completo do utilizador
    utilizador = db["Utilizadores"].find_one({"email": email}, {"_id": 0, "password_hash": 0})
    if not utilizador:
        return jsonify({"erro": "Utilizador não encontrado"}), 404

    # 2. Buscar todas as vagas disponíveis
    try:
        vagas = list(db["Vagas"].find({}, {"_id": 0}))
    except Exception as e:
        return jsonify({"erro": f"Erro ao carregar vagas: {str(e)}"}), 500

    if not vagas:
        return jsonify({"vagas": [], "perfil_completo": False, "mensagem": "Sem vagas disponíveis."})

    # 3. Verificar se o perfil tem dados suficientes para personalizar
    competencias = utilizador.get("competencias_tecnicas", [])
    cadeiras = utilizador.get("cadeiras_favoritas", [])
    tipos = utilizador.get("tipos_oportunidade", [])
    localizacoes = utilizador.get("localizacoes_preferidas", [])
    perfil_completo = bool(competencias or cadeiras or tipos)

    # 4. Limitar a 20 vagas enviadas à IA (evitar exceder limites de tokens)
    #    Priorizar vagas cujos tipos coincidem com as preferências do utilizador
    vagas_para_ia = vagas[:20]  # por defeito: as 20 primeiras

    if tipos:
        tipos_lower = [t.lower() for t in tipos]
        vagas_match = [v for v in vagas if str(v.get("tipo", "")).lower() in tipos_lower]
        vagas_resto = [v for v in vagas if str(v.get("tipo", "")).lower() not in tipos_lower]
        vagas_para_ia = (vagas_match + vagas_resto)[:20]

    vagas_restantes = [v for v in vagas if v not in vagas_para_ia]

    # 5. Construir resumo compacto das vagas para o prompt
    vagas_resumo = []
    for v in vagas_para_ia:
        vagas_resumo.append({
            "id_vaga": v.get("id_vaga"),
            "titulo": v.get("titulo", ""),
            "empresa": v.get("empresa", ""),
            "tipo": v.get("tipo", ""),
            "local": v.get("local") or v.get("localizacao", ""),
            "tags": v.get("tags", []),
            "descricao": (v.get("descricao", "") or "")[:1000]
        })

    prompt_sistema = (
        "És um assistente de carreira integrado no portal Oportunia. "
        "Analisa o perfil de um estudante e classifica oportunidades por relevância. "
        'Responde SEMPRE com um objeto JSON com a chave "recomendacoes" contendo um array de objetos.'
    )

    prompt_utilizador = f"""Perfil do Estudante:
- Nome: {utilizador.get('nome', 'Estudante')}
- Curso: {utilizador.get('curso', 'Não especificado')} em {utilizador.get('instituicao', 'Não especificada')}
- Competências Técnicas: {', '.join(competencias) if competencias else 'Não especificadas'}
- Cadeiras Favoritas: {', '.join(cadeiras) if cadeiras else 'Não especificadas'}
- Localizações Preferidas: {', '.join(localizacoes) if localizacoes else 'Qualquer'}
- Tipos de Oportunidade: {', '.join(tipos) if tipos else 'Qualquer'}
- Disponibilidade: {utilizador.get('disponibilidade', 'Não especificada')}

Oportunidades a analisar ({len(vagas_resumo)}):
{json.dumps(vagas_resumo, ensure_ascii=False)}

Devolve um objeto JSON com a seguinte estrutura exata:
{{
  "recomendacoes": [
    {{
      "titulo": "título exato da oportunidade (copia exatamente)",
      "score": <inteiro de 1 a 10>,
      "justificacao_ai": "<2 frases em português explicando a adequação>",
      "tags_extraidas": ["React", "TypeScript", "Python"],
      "requisitos_resumo": ["3 anos de experiência", "Inglês B2"]
    }}
  ]
}}
Ordena do score mais alto para o mais baixo. Inclui todas as {len(vagas_resumo)} oportunidades. "tags_extraidas" devem ser no máximo 5 tecnologias essenciais da vaga. "requisitos_resumo" devem ser no máximo 4 pontos com as principais exigências listadas na descrição da vaga.
"""

    # 6. Chamar GPT-4o (ou usar cache se existir)
    recomendacoes_ia = utilizador.get("cache_recomendacoes_ia", [])
    erro_ia = None

    if not recomendacoes_ia and perfil_completo:
        try:
            resposta = AI_CLIENT.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": prompt_utilizador}
                ],
                max_tokens=4000,
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            conteudo = resposta.choices[0].message.content
            parsed = json.loads(conteudo)
            # Extrair a lista de recomendações do objeto devolvido
            if isinstance(parsed, list):
                recomendacoes_ia = parsed
            elif isinstance(parsed, dict):
                for v in parsed.values():
                    if isinstance(v, list):
                        recomendacoes_ia = v
                        break
            
            # Guardar em cache para a próxima vez
            if recomendacoes_ia:
                db["Utilizadores"].update_one(
                    {"email": email}, 
                    {"$set": {"cache_recomendacoes_ia": recomendacoes_ia}}
                )
                
        except Exception as ex:
            erro_ia = str(ex)
            recomendacoes_ia = []
            print(f"[ERRO IA] {erro_ia}")

    # 7. Fazer merge: justificações IA com dados completos das vagas
    vagas_por_titulo = {v.get("titulo", ""): v for v in vagas}
    vagas_finais = []
    titulos_processados = set()

    for rec in recomendacoes_ia:
        if not isinstance(rec, dict):
            continue
        titulo_rec = rec.get("titulo", "")
        if titulo_rec in vagas_por_titulo:
            vaga_completa = dict(vagas_por_titulo[titulo_rec])
            vaga_completa["justificacao_ai"] = rec.get("justificacao_ai", "")
            vaga_completa["score_ia"] = rec.get("score", 0)
            vaga_completa["tags"] = rec.get("tags_extraidas", [])
            vaga_completa["requisitos"] = rec.get("requisitos_resumo", [])
            vagas_finais.append(vaga_completa)
            titulos_processados.add(titulo_rec)

    # Vagas analisadas pela IA mas não devolvidas (falha de match) + restantes
    for vaga in vagas:
        if vaga.get("titulo", "") not in titulos_processados:
            vaga_copia = dict(vaga)
            vaga_copia["justificacao_ai"] = ""
            vaga_copia["score_ia"] = 0
            vagas_finais.append(vaga_copia)

    return jsonify({
        "vagas": vagas_finais,
        "perfil_completo": perfil_completo,
        "erro_ia": erro_ia,
        "nome_utilizador": utilizador.get("nome", "Utilizador")
    })


@app.route("/api/perfil", methods=["POST"])
@login_required
def save_perfil():
    email = session["utilizador_email"]
    dados = request.get_json()

    campos_permitidos = [
        "nome", "headline", "instituicao", "curso",
        "links", "competencias_tecnicas", "cadeiras_favoritas",
        "localizacoes_preferidas", "tipos_oportunidade",
        "disponibilidade", "notificacoes"
    ]

    atualizacao = {k: dados[k] for k in campos_permitidos if k in dados}
    atualizacao["data_atualizacao"] = datetime.utcnow().isoformat()

    if not atualizacao:
        return jsonify({"erro": "Nenhum campo válido para atualizar"}), 400

    # 1. Atualizar os dados do perfil no MongoDB Cosmos DB
    # Limpar a cache da IA porque o perfil mudou
    db["Utilizadores"].update_one(
        {"email": email}, 
        {
            "$set": atualizacao,
            "$unset": {"cache_recomendacoes_ia": ""}
        }
    )

    if "nome" in atualizacao:
        session["utilizador_nome"] = atualizacao["nome"]

    # 2. 🤖 INTEGRAÇÃO AZURE OPENAI: Gerar recomendações baseadas no perfil armazenado
    recomendacoes_ia = ""
    try:
        vagas_disponiveis = list(db["Vagas"].find({}, {"_id": 0}))
        
        prompt_sistema = "És um sistema de IA integrado no portal Oportunia. O teu objetivo é analisar o perfil do estudante e sugerir quais as melhores vagas/oportunidades com base nas suas competências e cadeiras favoritas."
        
        prompt_utilizador = f"""
        Perfil do Estudante:
        - Nome: {atualizacao.get('nome', 'Estudante')}
        - Curso: {atualizacao.get('curso', '')} em {atualizacao.get('instituicao', '')}
        - Competências Técnicas: {', '.join(atualizacao.get('competencias_tecnicas', []))}
        - Cadeiras Favoritas: {', '.join(atualizacao.get('cadeiras_favoritas', []))}
        - Preferência de Localização: {', '.join(atualizacao.get('localizacoes_preferidas', []))}
        - Tipo de Oportunidade pretendida: {', '.join(atualizacao.get('tipos_oportunidade', []))}
        
        Lista de Vagas Disponíveis no Sistema:
        {vagas_disponiveis}
        
        Com base nestes dados, gera uma resposta curta, direta e motivadora em formato de texto para o utilizador. 
        Diz quais as vagas que melhor combinam com ele e porquê. Se não houver nenhuma vaga ideal, dá conselhos de que competências ele deve desenvolver.
        """

        resposta = AI_CLIENT.chat.completions.create(
            model="gpt-4o",  
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_utilizador}
            ],
            max_tokens=800,
            temperature=0.7
        )
        recomendacoes_ia = resposta.choices[0].message.content

    except Exception as ex:
        recomendacoes_ia = f"Não foi possível obter recomendações automáticas neste momento. (Erro: {str(ex)})"

    return jsonify({
        "sucesso": True, 
        "mensagem": "Perfil atualizado com sucesso",
        "recomendacoes": recomendacoes_ia
    })


@app.route("/api/credenciais", methods=["POST"])
@login_required
def update_credenciais():
    email = session["utilizador_email"]
    dados = request.get_json()

    atualizacao = {}

    if "novo_email" in dados:
        novo_email = dados["novo_email"].strip().lower()
        if not novo_email:
            return jsonify({"erro": "Email inválido."}), 400
        if db["Utilizadores"].find_one({"email": novo_email}):
            return jsonify({"erro": "Este email já está em uso."}), 400
        atualizacao["email"] = novo_email

    if "nova_password" in dados:
        nova_password = dados["nova_password"]
        if len(nova_password) < 8:
            return jsonify({"erro": "A password deve ter pelo menos 8 caracteres."}), 400
        atualizacao["password_hash"] = generate_password_hash(nova_password)

    if not atualizacao:
        return jsonify({"erro": "Nada para atualizar."}), 400

    atualizacao["data_atualizacao"] = datetime.utcnow().isoformat()
    db["Utilizadores"].update_one({"email": email}, {"$set": atualizacao})

    if "email" in atualizacao:
        session["utilizador_email"] = atualizacao["email"]

    return jsonify({"sucesso": True})


@app.route("/api/recuperar-password", methods=["POST"])
def recuperar_password():
    dados = request.get_json()
    email = dados.get("email", "").strip().lower()
    
    if not email:
        return jsonify({"erro": "Email inválido."}), 400
        
    utilizador = db["Utilizadores"].find_one({"email": email})
    if utilizador:
        # Gera o token seguro
        token = serializer.dumps(email, salt='recuperacao-password')
        link_recuperacao = url_for('reset_password_page', token=token, _external=True)
        
        # Envia o email
        try:
            enviar_email_recuperacao(email, link_recuperacao)
        except Exception as e:
            print(f"Erro ao enviar email de recuperação: {e}")
            return jsonify({"erro": "Ocorreu um erro ao enviar o email de recuperação."}), 500
    
    return jsonify({"sucesso": True, "mensagem": "Se o email existir, enviámos as instruções para recuperares a password."})

def enviar_email_recuperacao(email_destino, link):
    remetente = os.environ.get("MAIL_USERNAME")
    password = os.environ.get("MAIL_PASSWORD")
    servidor = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    porta = int(os.environ.get("MAIL_PORT", 587))
    
    if not remetente or not password:
        raise Exception("Credenciais de email não configuradas no .env")

    msg = EmailMessage()
    msg['Subject'] = 'Oportunia - Recuperação de Password'
    msg['From'] = remetente
    msg['To'] = email_destino
    msg.set_content(f"""Olá,
    
Recebemos um pedido para redefinir a tua password no Oportunia.
Clica no link abaixo para criar uma nova password (o link expira em 1 hora):

{link}

Se não pediste para redefinir a password, podes ignorar este email.
    
A Equipa Oportunia""")

    with smtplib.SMTP(servidor, porta) as s:
        s.starttls()
        s.login(remetente, password)
        s.send_message(msg)

@app.route("/reset-password/<token>", methods=["GET"])
def reset_password_page(token):
    try:
        serializer.loads(token, salt='recuperacao-password', max_age=3600) # Expira em 1 hora
    except SignatureExpired:
        return render_template("reset_password.html", erro="O link de recuperação expirou. Por favor, pede um novo.")
    except BadTimeSignature:
        return render_template("reset_password.html", erro="Link de recuperação inválido.")
    
    return render_template("reset_password.html", token=token)

@app.route("/reset-password/<token>", methods=["POST"])
def reset_password_post(token):
    try:
        email = serializer.loads(token, salt='recuperacao-password', max_age=3600)
    except SignatureExpired:
        return render_template("reset_password.html", erro="O link de recuperação expirou. Por favor, pede um novo.")
    except BadTimeSignature:
        return render_template("reset_password.html", erro="Link de recuperação inválido.")
        
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    
    if len(password) < 8:
        return render_template("reset_password.html", token=token, erro="A password deve ter pelo menos 8 caracteres.")
        
    if password != confirm_password:
        return render_template("reset_password.html", token=token, erro="As passwords não coincidem.")
        
    # Atualiza a base de dados
    db["Utilizadores"].update_one(
        {"email": email}, 
        {
            "$set": {
                "password_hash": generate_password_hash(password),
                "data_atualizacao": datetime.utcnow().isoformat()
            }
        }
    )
    
    return render_template("reset_password.html", sucesso="Password redefinida com sucesso!")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)
