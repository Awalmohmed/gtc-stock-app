FROM python:3.9

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV FLASK_APP run.py

WORKDIR /app

# unixODBC : requis à l'exécution par pyodbc (voir apps/sage_connector.py,
# rapprochement Sage 100). Le driver Sage/SQL Server/Pervasive lui-même
# reste à installer séparément selon l'édition Sage 100 utilisée par
# l'entreprise (non couvert ici, spécifique à chaque environnement).
RUN apt-get update \
    && apt-get install -y --no-install-recommends unixodbc unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# install python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker-entrypoint.sh

# Applique les migrations puis démarre gunicorn (voir docker-entrypoint.sh)
ENTRYPOINT ["./docker-entrypoint.sh"]
