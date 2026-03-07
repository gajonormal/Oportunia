// Localização automática baseada no teu novo Resource Group
param location string = resourceGroup().location

// Nomes únicos para evitar conflitos na Azure
var uniqueSuffix = uniqueString(resourceGroup().id)

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

// 2. Web App (Onde o site vai correr)
resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: 'app-oportunia-${uniqueSuffix}'
  location: location
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'DOCKER|mcr.microsoft.com/appsvc/staticsite:latest'
    }
  }
}

// 3. CosmosDB (Base de dados NoSQL - API MongoDB)
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
  }
}

// 4. Storage Account (Para os PDFs e relatórios)
resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: 'stoportunia${uniqueSuffix}'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
}
