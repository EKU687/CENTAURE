# Image Python légère et officielle
FROM python:3.11-slim

# Éviter l'écriture de fichiers .pyc et forcer l'affichage direct des logs
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Installation des dépendances système nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt-lists/*

# Copie et installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie de l'intégralité du code application
COPY . .

# Exposition du port 8080 (utilisé par Fly.io par défaut)
EXPOSE 8080

# Commande de lancement de CENTAURE
CMD ["python", "main.py"]