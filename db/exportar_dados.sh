#!/bin/sh
# Gera db/dados_iniciais.sql a partir do banco de desenvolvimento (docker compose).
#
# Esse arquivo é carregado automaticamente pela imagem do banco na PRIMEIRA
# inicialização (volume vazio). Assim um servidor novo já sobe com os dados,
# sem precisar rodar o coletor. Depois, o coletor mantém tudo atualizado.
#
# Uso (na raiz do projeto, com o banco no ar e já coletado):
#   sh db/exportar_dados.sh
#
# O arquivo não tem dados pessoais: o banco nunca guarda CNS, CPF ou registro em conselho.
set -e
docker compose exec -T db pg_dump -U saude_aqui -d saude_aqui \
  --data-only --no-owner --no-privileges \
  --table=ocupacao --table=unidade --table=coleta --table=vinculo --table=arquivo_portal \
  > db/dados_iniciais.sql
echo "Gerado db/dados_iniciais.sql ($(wc -c < db/dados_iniciais.sql) bytes)"
