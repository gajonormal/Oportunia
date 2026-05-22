# Imagem base de Python
FROM python:3.10-slim

# Define a pasta de trabalho
WORKDIR /app

# Copia as dependências e instala-as
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do código para dentro do contentor
COPY . .

# Expõe a porta 8000 (padrão do App Service Linux para Python)
EXPOSE 8000

# Comando para iniciar a API no Azure (timeout de 120s para acomodar a IA)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--timeout", "120", "app:app"]