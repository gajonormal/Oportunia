// Localização automática baseada no teu novo Resource Group
param location string = resourceGroup().location

// Nomes únicos para evitar conflitos na Azure
var uniqueSuffix = uniqueString(resourceGroup().id)

// ==========================================
// PARÂMETROS SEGUROS (Segredos e Chaves)
// ==========================================
@secure()
@description('Chave da API do Azure OpenAI')
param azureOpenAIKey string

@secure()
@description('Endpoint da API do Azure OpenAI')
param azureOpenAIEndpoint string

@secure()
@description('Chave secreta usada pelo Flask para assinar sessões')
param secretKey string

@secure()
@description('Chave da API do ITJobs (Scraper)')
param apiItJobs string

@secure()
@description('Chave da API do Jooble (Scraper)')
param apiJooble string

@secure()
@description('Password do servidor de SMTP (Envio de Emails)')
param mailPassword string

@description('Endereço do servidor SMTP')
param mailServer string

@description('Porta do servidor SMTP')
param mailPort string

@description('Username do servidor SMTP')
param mailUsername string

// ==========================================
// INFRAESTRUTURA DE ALOJAMENTO WEB E DB
// ==========================================

// 1. App Service Plan (O servidor Linux para o Docker)
resource appServicePlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: 'asp-oportunia-${uniqueSuffix}'
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

// 2. Storage Account (Para os PDFs e relatórios)
resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: 'stoportunia${uniqueSuffix}'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
}

// 3. CosmosDB (Base de dados NoSQL - API MongoDB - MODO SERVERLESS)
resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: 'cosmos-oportunia-${uniqueSuffix}'
  location: location
  kind: 'MongoDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless' // Ativa o modo de faturação Serverless
      }
    ]
  }
}

// ==========================================
// MONITORIZAÇÃO (Para os logs da Azure Function)
// ==========================================
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-oportunia-${uniqueSuffix}'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-oportunia-${uniqueSuffix}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ==========================================
// CONNECTION STRINGS E INJEÇÃO DE DEPENDÊNCIAS
// ==========================================

// Obter dinamicamente a Connection String da Storage Account recém-criada
var storageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'

// Obter dinamicamente a Connection String do Cosmos DB recém-criado
var cosmosConnectionString = cosmosDb.listConnectionStrings().connectionStrings[0].connectionString

// 4. Web App (Onde o site principal vai correr via Docker)
resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: 'app-oportunia-67g5yzourkqaa' // Nome fixo exigido pelo deploy.yml
  location: location
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'DOCKER|mcr.microsoft.com/appsvc/staticsite:latest'
      appSettings: [
        { name: 'AZURE_STORAGE_CONNECTION_STRING', value: storageConnectionString }
        { name: 'LIGACAO_COSMOS', value: cosmosConnectionString }
        { name: 'AZURE_OPENAI_KEY', value: azureOpenAIKey }
        { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAIEndpoint }
        { name: 'SECRET_KEY', value: secretKey }
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsights.properties.InstrumentationKey }
      ]
    }
  }
}

// ==========================================
// AZURE FUNCTION (O Scraper Automático)
// ==========================================

// 5. Plano de Consumo para a Function (Pagas ao milissegundo de uso)
resource functionAppPlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: 'asp-func-oportunia-${uniqueSuffix}'
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

// 6. A Azure Function App
resource functionApp 'Microsoft.Web/sites@2022-09-01' = {
  name: 'oportunia-scraper' // Nome fixo exigido pelo deploy.yml
  location: location
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: functionAppPlan.id
    siteConfig: {
      linuxFxVersion: 'python|3.11'
      appSettings: [
        { name: 'AzureWebJobsStorage', value: storageConnectionString }
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsights.properties.InstrumentationKey }
        { name: 'LIGACAO_COSMOS', value: cosmosConnectionString }
        { name: 'API_KEY_ITJOBS', value: apiItJobs }
        { name: 'API_KEY_JOOBLE', value: apiJooble }
        { name: 'MAIL_SERVER', value: mailServer }
        { name: 'MAIL_PORT', value: mailPort }
        { name: 'MAIL_USERNAME', value: mailUsername }
        { name: 'MAIL_PASSWORD', value: mailPassword }
      ]
    }
  }
}
