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

Antes de existir coleta real, dá para carregar **dados fictícios** (para desenvolver o front-end):

```bash
docker compose exec -T db psql -U saude_aqui -d saude_aqui < db/dados_ficticios.sql
```

## API

```bash
docker compose up -d --build api
# Documentação interativa: http://localhost:8000/api/docs
# (se a porta 8000 estiver ocupada, defina API_PORTA=8001 no .env)
```

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/health` | Verificação de saúde |
| GET | `/api/status` | Última atualização, última verificação e competência (mês) do CNES |
| GET | `/api/bairros` | Bairros que têm unidades |
| GET | `/api/especialidades` | Ocupações presentes (CBO, nome, categoria, total) |
| GET | `/api/unidades?bairro=` | Unidades com coordenadas (para o mapa) |
| GET | `/api/unidades/proximas?lat=&lng=&raio_km=&bairro=&categoria=&cbo=` | Unidades com os **profissionais vinculados**; com lat/lng, ordena por distância e retorna `distancia_km` |

### Testes da API

Os testes usam um banco separado (`saude_aqui_teste`), recriado a cada execução com
`db/init.sql` + `db/dados_ficticios.sql`. É preciso ter o banco no ar.

```bash
docker compose up -d db
cd api
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## Front-end

React + Vite + TypeScript, com mapa **Leaflet + OpenStreetMap** (gratuito, sem chave de API).

```bash
docker compose up -d --build web    # http://localhost:8080 (o nginx repassa /api para a API)
```

* **Layout:** mapa em tela cheia com um painel lateral no desktop. No celular, o mapa fica
  em cima e a lista aparece numa gaveta inferior, que pode ser expandida pela alça.
* **Lista e mapa sincronizados:** clicar num cartão centraliza o marcador; clicar num
  marcador abre e mostra o cartão.
* **Filtros:** busca por nome/bairro (feita no próprio navegador), especialidade, bairro e
  "Usar minha localização" (reordena por distância). Se a permissão for negada, o site
  sugere escolher o bairro.
* **"Como chegar"** é um link gratuito do Google Maps (`google.com/maps/dir/?api=1&destination=LAT,LNG`).
* **Aviso fixo:** os dados mostram profissionais *vinculados* (CNES), e não plantões. Sempre
  peça para confirmar por telefone.
* **Acessibilidade:** fonte de 16 px, contraste AA, foco visível, Tab/Enter e setas ↑/↓ na lista.

**Regras do OpenStreetMap:** a atribuição fica visível no canto do mapa, e o servidor de tiles
`tile.openstreetmap.org` aceita só uso leve. Se o tráfego crescer, troque `VITE_TILES_URL`
(e `VITE_TILES_ATRIBUICAO`) por um provedor com plano gratuito, sem mudar o código.

### Desenvolvimento e testes do front-end

Não é preciso ter Node instalado: dá para usar o Node pelo Docker.

```bash
cd web
docker run --rm -it -v "$PWD":/app -w /app -u "$(id -u):$(id -g)" node:22-alpine npm install
docker run --rm -it -v "$PWD":/app -w /app -u "$(id -u):$(id -g)" node:22-alpine npm test
```

Com Node 22 instalado: `npm install`, `npm test` e `API_URL=http://localhost:8000 npm run dev`
(abre em http://localhost:5173).

*(Seções do coletor e da implantação no Easypanel serão adicionadas nas próximas etapas.)*
