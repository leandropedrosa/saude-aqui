# Imagem da API: Python enxuto + uvicorn com 1 worker (cabe em 192 MB).
FROM python:3.12-slim

# Logs aparecem na hora e não criamos arquivos .pyc
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Usuário sem privilégios de administrador
RUN useradd --create-home api
USER api

EXPOSE 8000
# --proxy-headers: respeita o IP/protocolo repassados pelo nginx/Easypanel
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
