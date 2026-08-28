FROM python:3.11-slim

WORKDIR /app

# Instalar Java (versión 21 disponible en Debian estable)
RUN apt-get update && apt-get install -y openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# 1. Copiamos el requirements que está en la raíz del contexto (.)
COPY requirements.txt ..

RUN pip install --no-cache-dir -r requirements.txt \
    && python -m nltk.downloader punkt wordnet stopwords punkt_tab

# 2. Copiamos TODO el contenido de la carpeta local backend/ dentro de /app
COPY ./backend/ .

# 3. Exponemos el puerto
EXPOSE 8000

# 4. 🔥 EL CAMBIO CLAVE: Le decimos a Uvicorn dónde está parado main:app
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]