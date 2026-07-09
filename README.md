# Oportunia 

<img src="static/logo.png" width="200" alt="Logo Oportunia">

<div align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/Microsoft_Azure-0089D6?style=for-the-badge&logo=microsoft-azure&logoColor=white" alt="Azure">
  <img src="https://img.shields.io/badge/Azure_Cosmos_DB-31A8FF?style=for-the-badge&logo=microsoft-azure&logoColor=white" alt="Azure Cosmos DB">
</div>

**Assistente de Carreira para Estudantes de Informática Portugueses**

Plataforma cloud-native que agrega e personaliza oportunidades profissionais e académicas — estágios, empregos entry-level, bolsas de estudo e eventos tecnológicos — para estudantes de Engenharia Informática em Portugal.

## Sobre o projeto

Mais do que um agregador, o Oportunia funciona como uma camada de curadoria que cruza o percurso académico do estudante com as necessidades reais do mercado. A recolha de dados é automatizada (IEFP, ITJobs.pt, Erasmus+) via Azure Functions, com os resultados persistidos em Azure CosmosDB e servidos através de uma interface web em Azure App Service. A análise semântica de perfis e a geração de recomendações personalizadas são feitas via Azure OpenAI Service.

Projeto desenvolvido no âmbito da unidade curricular de Computação em Nuvem (Licenciatura em Engenharia Informática, ESTCB/IPCB), em equipa.

## Stack técnica

- **Backend:** Flask (Python)
- **Base de dados:** Azure CosmosDB (API MongoDB)
- **Serverless:** Azure Functions (Timer Trigger) — recolha automática de dados
- **Armazenamento:** Azure BLOB Storage — relatórios e ficheiros estáticos
- **Deployment:** Docker + Azure App Service
- **Infraestrutura como código:** Bicep (ARM)
- **CI/CD:** GitHub Actions
- **IA:** Azure OpenAI Service (GPT-4o) — análise semântica de perfis e recomendações personalizadas de compatibilidade

## Funcionalidades

- Registo e autenticação de utilizadores, com recuperação de password
- Dashboard com oportunidades agregadas de múltiplas fontes
- Relatórios semanais de oportunidades
- Perfil de utilizador com competências técnicas, usado para matching semântico via IA
- Recomendações personalizadas e justificadas, geradas pelo Azure OpenAI Service
- API REST própria (`/api/vagas`) que serve os dados persistidos no CosmosDB

## Como correr localmente

1. Clonar o repositório
```bash
   git clone https://github.com/gajonormal/Oportunia.git
   cd Oportunia
```

2. Instalar dependências
```bash
   pip install -r requirements.txt
```

3. Configurar variáveis de ambiente (copiar `.env.example` para `.env` e preencher)

4. Correr a aplicação
```bash
   python app.py
```

## Infraestrutura

Toda a infraestrutura Azure (App Service, CosmosDB, Storage) é provisionada via Bicep (`main.bicep`), garantindo automação e reprodutibilidade.

## Equipa

Bernardo Maia, Leonardo Martins, Gonçalo Nunes — sob orientação do Prof. Osvaldo Santos.
