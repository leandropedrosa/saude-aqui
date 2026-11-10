# Imagem do coletor: Python enxuto + supercronic (um "cron" feito para containers,
# que escreve os logs na saída padrão e respeita o fuso horário).
# O contexto do build é a RAIZ do repositório (para copiar db/*.csv).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    TZ=America/Sao_Paulo \
    PASTA_CSV=/app/db \
    PASTA_BRUTOS=/dados/brutos

# supercronic: binário único, verificado pelo SHA-1 publicado no GitHub
ARG SUPERCRONIC_VERSAO=v0.2.33
ARG SUPERCRONIC_SHA1=71b0d58cc53f6bd72cf2f293e09e294b79c666d8
ADD https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSAO}/supercronic-linux-amd64 /usr/local/bin/supercronic
RUN echo "${SUPERCRONIC_SHA1}  /usr/local/bin/supercronic" | sha1sum -c - \
 && chmod +x /usr/local/bin/supercronic

WORKDIR /app
COPY coletor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY coletor/*.py coletor/crontab ./
COPY db/unidades.csv db/ocupacoes.csv ./db/

# Usuário sem privilégios; ele é o dono da pasta dos arquivos baixados
RUN useradd --create-home coletor && mkdir -p /dados/brutos && chown coletor /dados/brutos
USER coletor
VOLUME /dados/brutos

# Padrão: fica rodando e executa o coletor no horário do crontab.
# Execução manual: docker compose run --rm coletor python coletar.py
CMD ["/usr/local/bin/supercronic", "/app/crontab"]
