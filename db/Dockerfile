# Imagem do banco: o Postgres oficial + nosso schema.
# Empacotar o init.sql na imagem evita depender de "montar arquivos" no
# Easypanel: a VM só puxa a imagem pronta do GHCR.
FROM postgres:16-alpine

# Scripts em /docker-entrypoint-initdb.d rodam só na primeira inicialização
# (quando o volume de dados está vazio), em ordem alfabética:
#   01: cria as tabelas
#   02: carrega os dados já coletados (gerados por db/exportar_dados.sh), para um
#       servidor novo subir com o site funcionando sem precisar rodar o coletor
COPY init.sql /docker-entrypoint-initdb.d/01-init.sql
COPY dados_iniciais.sql /docker-entrypoint-initdb.d/02-dados_iniciais.sql

# Configuração para pouca memória (VM com 2 GB, limite de 384 MB para o banco)
CMD ["postgres", \
     "-c", "shared_buffers=64MB", \
     "-c", "max_connections=20", \
     "-c", "work_mem=4MB", \
     "-c", "effective_cache_size=192MB", \
     "-c", "maintenance_work_mem=32MB", \
     "-c", "timezone=America/Sao_Paulo", \
     "-c", "log_timezone=America/Sao_Paulo"]
