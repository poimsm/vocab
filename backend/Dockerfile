FROM python:3.11-slim

WORKDIR /app

# Instalar Java, vim, curl y otras herramientas útiles
RUN apt-get update && apt-get install -y openjdk-21-jre-headless vim curl \
    && rm -rf /var/lib/apt/lists/*

# 1. Copiamos el requirements a /requirements.txt (fuera de /app para evitar que se sobrescriba con el volumen)
COPY requirements.txt /requirements.txt

RUN pip install --no-cache-dir -r /requirements.txt \
    && python -m nltk.downloader punkt wordnet stopwords punkt_tab

# Pre-download LanguageTool to avoid runtime download
RUN python -c "from language_tool_python import LanguageTool; LanguageTool('en-US')"

# 2. Copiamos TODO el contenido de la carpeta local backend/ dentro de /app
COPY ./backend/ .

# 3. Exponemos el puerto
EXPOSE 8000

# 4. 🔥 EL CAMBIO CLAVE: Le decimos a Uvicorn dónde está parado main:app
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]