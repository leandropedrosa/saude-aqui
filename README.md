# Saúde Aqui

Site que ajuda moradores de Cidade Ocidental (GO) a encontrar **unidades públicas de saúde**
perto de onde estão (ou no bairro escolhido) e a ver **quais profissionais estão vinculados**
a cada unidade.

Projeto de alunos de graduação da UFG. O código é propositalmente simples e comentado em português.

> ⚠️ Os dados vêm do CNES (Cadastro Nacional de Estabelecimentos de Saúde). Eles mostram quem
> está **vinculado** a cada unidade, e não quem está de plantão hoje. O site sempre orienta a
> confirmar por telefone antes de ir.

## De onde vêm os dados

| Dado | Fonte | Atualização |
|---|---|---|
| Unidades (nome, endereço, bairro, telefone, coordenadas, turno) | API de dados abertos do Ministério da Saúde (`apidadosabertos.saude.gov.br/cnes/estabelecimentos`) | contínua |
| Profissionais × unidade (nome, ocupação CBO, carga horária semanal) | FTP do DATASUS, arquivo mensal `PFGOaamm.dbc` | mensal (~2 meses de atraso) |

Os detalhes da investigação estão em [`coletor/amostras/ACHADOS.md`](coletor/amostras/ACHADOS.md).

**Privacidade:** o coletor descarta CNS (Cartão SUS), CPF e registro em conselho. Guardamos só
nome, ocupação e carga horária.

## Arquivos que os alunos podem editar

* **`db/unidades.csv`**: ajustes manuais por unidade (chave: código CNES). Uma coluna vazia
  significa "usar o valor do CNES".
  * `nome`, `bairro`, `telefone`, `lat`, `lng`: corrigem o que veio do CNES.
  * `horario`: texto livre (ex.: `Seg a sex, 7h às 17h`). Quando preenchido, aparece no
    lugar do turno do CNES.
  * `ativo`: `nao` esconde a unidade do site (ex.: setores administrativos, SAMU).
* **`db/ocupacoes.csv`**: quais ocupações (CBO) aparecem no site. Mude `incluir` para
  `sim`/`nao`; não apague linhas. Depois de editar, rode o coletor com `--forcar`.

## Estrutura

```
saude-aqui/
├── docker-compose.yml          # desenvolvimento local
├── docker-compose.prod.yml     # referência para o Easypanel (etapa 6)
├── .env.example
├── db/          # Postgres: init.sql, unidades.csv, ocupacoes.csv
├── api/         # FastAPI (etapa 3)
├── coletor/     # baixa CNES/DATASUS e importa (etapa 5)
└── web/         # React + Vite + TypeScript + Leaflet/OpenStreetMap (etapa 4)
```

| Serviço | Imagem base | Limite de memória |
|---|---|---|
| db | postgres:16-alpine | 384 MB |
| api | python:3.12-slim + uvicorn (1 worker) | 192 MB |
| coletor | python:3.12-slim + supercronic | 256 MB |
| web | nginx:alpine | 64 MB |

## Rodando localmente

```bash
cp .env.example .env            # ajuste a senha
docker compose up -d db         # sobe o banco (o schema é criado na 1ª vez)
docker compose exec db psql -U saude_aqui -d saude_aqui   # inspecionar
```

Para recriar o banco do zero (apaga os dados): `docker compose down -v`.

*(Seções de API, front-end, coletor e implantação no Easypanel serão adicionadas nas próximas etapas.)*
