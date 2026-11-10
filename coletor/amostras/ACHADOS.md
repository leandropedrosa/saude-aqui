# Fase 0: achados sobre a fonte de dados

Investigação feita em 10/11/2026 com `coletor/investigar.py` (Playwright).
Arquivos de apoio estão nesta pasta: `rede.json`, `escalas_lista.json`, `pagina.png`,
os PDFs e o XLSX de exemplo.

## 1. Como a página carrega os dados (Caso A para a lista, Caso B para o conteúdo)

A página é uma SPA do NúcleoGov. A **lista** das escalas vem de uma API JSON e
o **conteúdo** de cada escala está em um arquivo anexo (PDF ou XLSX) no S3.

| Requisição | Corpo (form-urlencoded) | Retorno |
|---|---|---|
| `POST /api/escalasmedicas` | `acao=listar_unidades` | `[{id, nome}]`, 37 unidades |
| `POST /api` | `multi_request=true&params={"q":{"acao":"escalasmedicas/listarEspecialidades","only_existing":true}}` | `[{id, valor}]`, 14 especialidades |
| `POST /api` | `multi_request=true&params={"q":{"acao":"escalasmedicas/listarCidadao","limit":"0, 200"}}` | `{dados:[...]}`, 65 escalas |

* **Funciona só com `httpx`, sem navegador.** Testado. O Playwright não é necessário em produção.
* ⚠️ O servidor devolve **403** para o user-agent `HeadlessChrome`. Use um
  user-agent de navegador comum.
* Campos de cada escala em `listarCidadao`: `id`, `unidade_id`, `nome` (da unidade),
  `data_inicio`, `data_fim`, `horario_funcionamento` (texto livre, ex.: `24H`,
  `SEGUNDA A SEXTA FEIRA DAS 8H ÀS 17H`), `especialidades` (ids, às vezes `null`),
  `midia` (nome do arquivo), `titulo_midia`, `download_url` (assinada, expira em 40 min).
* ⚠️ O `download_url` assinado **falha (HTTP 400) quando o nome do arquivo tem acento**
  (ex.: `ESCALA MÉDICA.xlsx`). Solução: o bucket é público, então baixe direto de
  `https://nucleogov.s3.us-east-2.amazonaws.com/pf_cidadeocidental/outros/{midia}`.

## 2. O que existe publicado (65 registros)

| Período declarado | Qtde | Arquivo |
|---|---|---|
| 2026-01-01 → 2026-12-31 | 10 | PDF "profissionalEstabelecimento (NN).pdf" (**vigente**) |
| 2025-05 → 2025-11 | 4 | **o mesmo** `ESCALA MÉDICA.xlsx` repetido em 4 unidades |
| 2025-02 → 2025-03 | 7 | PDFs do CNES |
| 2024 (ano todo) | 7 | PDFs do CNES |
| 2023-08-01 | 37 | **um único PDF** repetido para todas as unidades |

**Frequência:** irregular, de 1 a 3 publicações por ano. A última foi em jan/2026,
com validade até dez/2026. Só 10 das 37 unidades têm escala vigente.

## 3. Formato dos arquivos

### 3.1 PDF vigente: "Listagem de Profissionais" do CNES (`atual_*.pdf`)

É uma impressão do CNES/DATASUS e **não é uma escala de plantão**. Não tem datas,
dias da semana nem turnos. O cabeçalho traz o **código CNES** e o nome fantasia da
unidade, o que é ótimo para associar a unidade sem depender do nome. A tabela sai
limpa com `pdfplumber.extract_tables()`:

| Coluna | Uso no Saúde Aqui |
|---|---|
| Nome | sim |
| CNS (Cartão Nacional de Saúde) | 🚫 **descartar na leitura e nunca gravar** (dado pessoal) |
| CBO (código + ocupação, ex.: `225125 - MEDICO CLINICO`) | categoria/especialidade |
| SUS, Vinculação, Tipo, Subtipo | não |
| CHS Outro / Amb. / Hosp. / Total | carga horária **semanal**, não é horário |

A lista inclui também equipe de limpeza, motoristas, recepção etc. Será preciso filtrar
pelo CBO (médicos `2251xx`/`2252xx`/`2253xx`, enfermeiros `2235xx`, dentistas `2232xx`,
farmacêuticos `2234xx`, nutricionistas `2237xx`, fisioterapeutas `2236xx`...).

### 3.2 XLSX de 2025: a única escala de verdade (`2025_escala_52.xlsx`)

É uma grade semanal do pronto-atendimento do hospital:

```
DIURNO   | SEGUNDA     | TERÇA       | ... | DOMINGO
         | DR ROBERTO  | DR EDNALDO  | ... | DR ALEJANDRO   (3 linhas de médicos)
ESCALA DE INTERNAÇÃO BOX ...
NOTURNO  | ...
```

* Só traz apelidos ("DR JAIRO"), sem especialidade, sem horário e sem data.
  É um padrão semanal que se repete.
* Os nomes vêm com erros de digitação ("EDNALDO"/"EDNARDO", "LETÍCIA"/"LETICIA", "**DR J.MARCELO").
* Foi anexado, por engano, a 4 unidades diferentes (UBSF SQ 19, Jardim ABC, Araguari),
  mas o conteúdo é do hospital.

### 3.3 Legenda de códigos de turno

**Não existe.** Nenhum arquivo usa códigos como M/T/N/PV. O único "turno" encontrado
é `DIURNO`/`NOTURNO` no XLSX de 2025.

## 4. Conclusão: a premissa do projeto precisa de ajuste

A ideia original ("quem está escalado **hoje**, com horário") **não é sustentada pelos
dados publicados hoje**. O que existe de forma confiável é:

1. **Quem atende em cada unidade** (profissional + ocupação), pela listagem do CNES.
2. **Horário de funcionamento da unidade**, pelo campo `horario_funcionamento` da API.
3. Ocasionalmente, uma grade semanal Diurno/Noturno do hospital.

### Opções

* **A (recomendada):** mudar o produto para *"Onde e quem atende perto de mim"*:
  unidades no mapa, horário de funcionamento e profissionais vinculados (médicos,
  enfermeiros, dentistas...). A tabela `turno` vira `vinculo` (profissional ↔ unidade,
  carga horária semanal). O parser suporta também a grade semanal (dia da semana +
  diurno/noturno) para quando a Prefeitura publicar escalas no formato XLSX.
  O aviso "confirme por telefone" fica ainda mais importante.
* **B:** manter o modelo `turno` por data, mas ele ficará quase vazio. Hoje só haveria
  dados do hospital, de 2025 e desatualizados.
* **C (complementar):** fazer um pedido pela LAI (e-SIC) solicitando as escalas mensais
  reais. O portal já tem a seção, mas não está sendo alimentado.

## 5. Outras observações

* **Unidades:** a API dá 37 nomes com `id`. Os nomes têm espaços extras e o travessão
  "–". A normalização (sem acento, caixa baixa, `strip`, travessão → hífen) resolve.
  O PDF traz o CNES, então `unidades.csv` deve ter CNES como chave principal.
* **Layout de referência** (igrejas.adventistas.org, capturas em `docs/referencia/`):
  mapa em tela cheia, painel flutuante à esquerda com cartões (ícone, nome, distância
  em "pílula", etiqueta de tipo), marcadores agrupados (cluster), botão "minha
  localização" no canto inferior direito, barra de busca em formato de pílula no topo.
  No celular, o painel vira uma *bottom sheet* com alça. O mapa usa **OpenFreeMap**
  (tiles vetoriais do OSM, gratuitos e sem chave), e não Google Maps.

---

# Fase 0b: dados abertos do CNES (DATASUS) como fonte principal

Decisão do grupo: **opção A + C**. O produto passa a ser "onde e quem atende perto de mim",
com base nos dados oficiais do CNES. Investigação feita em 10/11/2026.

## 6. Fontes encontradas

| Fonte | O que traz | Formato | Atualização |
|---|---|---|---|
| **FTP DATASUS — PF** `ftp://ftp.datasus.gov.br/dissemin/publicos/CNES/200508_/Dados/PF/PFGOaamm.dbc` | um registro por vínculo profissional × estabelecimento: `CNES`, `CODUFMUN`, `CBO`, `NOMEPROF`, `HORAOUTR`/`HORAHOSP`/`HORA_AMB`, `COMPETEN` | DBC (DBF comprimido), 10 MB para GO | **mensal**. Em 10/11/2026 a mais recente era **2026-09** (~2 meses de atraso) |
| **API de dados abertos do Ministério da Saúde** `GET https://apidadosabertos.saude.gov.br/cnes/estabelecimentos?codigo_municipio=520549&limit=20&offset=N` | nome fantasia, endereço, **bairro**, **telefone**, **latitude/longitude**, **turno de atendimento**, CNPJ da mantenedora | JSON paginado (20 por página), sem chave | contínua |
| FTP DATASUS — ST (estabelecimentos) | mesmos códigos do PF, porém **sem nome nem endereço** | DBC | mensal (não é necessário; a API é melhor) |

* Código IBGE de Cidade Ocidental: **520549** (6 dígitos, como o DATASUS usa).
* O DBF descomprimido tem um **cabeçalho fora do padrão**: o campo "tamanho do cabeçalho"
  não bate com o terminador `0x0D`, e a biblioteca `dbfread` falha. Um leitor DBF de
  ~20 linhas, que usa o tamanho do cabeçalho, resolve, lendo registro a registro sem
  carregar 46 MB na memória. Para descomprimir o DBC: pacote `datasus-dbc`.
* FTP: `ftplib`/`urllib` da biblioteca padrão. O `httpx` não faz FTP.

## 7. Cobertura em comparação com o portal municipal

* A API retorna **69 estabelecimentos** no município. O campo `descricao_esfera_administrativa`
  diz "MUNICIPAL" para **todos**, inclusive Drogasil e Sabin, então **não é confiável**.
  O filtro correto é `numero_cnpj_entidade == "36862621000121"` (mantenedora = Município
  de Cidade Ocidental): **47 unidades públicas**, contra 37 nomes e só 10 escalas vigentes no portal.
* **45 das 47** unidades públicas têm latitude/longitude. Sem coordenadas: a "Unidade Móvel
  Terrestre II" (fora do PF, provavelmente desativada) e o "Centro de Saúde Cidade
  Ocidental" (CNPJ privado, 0 profissionais).
* PF 2026-09: **815 vínculos** no município.
* **Conferência com os PDFs do portal (jan/2026 × CNES set/2026):**

| Unidade | PDF | DATASUS | Em ambos | Só no PDF | Só no DATASUS |
|---|---|---|---|---|---|
| Hospital Municipal (CNES 2569728) | 158 | 181 | 133 | 25 | 48 |
| UBS Família Dom Bosco (7713304) | 10 | 8 | 8 | 2 | 0 |

  As diferenças são compatíveis com 8 meses de rotatividade. O DATASUS é a mesma base,
  só que mais recente. **Conclusão: o CNES/DATASUS vira a fonte principal**, e os PDFs do
  portal ficam apenas para conferência manual.

## 8. Horário de funcionamento (item 5)

A API traz `codigo_identificador_turno_atendimento` nas 47 unidades públicas:

| Código | Descrição oficial | Texto curto sugerido |
|---|---|---|
| 02 | Atendimento somente à tarde | Tarde |
| 03 | Atendimentos nos turnos da manhã e à tarde | Manhã e tarde |
| 04 | Atendimento nos turnos da manhã, tarde e noite | Manhã, tarde e noite |
| 06 | Atendimento contínuo de 24 horas/dia (plantão, inclui sábados, domingos e feriados) | 24 horas |

Não há horário exato (ex.: 8h às 17h). Proposta: usar o turno do CNES por padrão, com uma
coluna opcional `horario` em `unidades.csv` que, quando preenchida, tem prioridade. O
portal municipal tem esse texto para 10 unidades (campo `horario_funcionamento`).

## 9. Ocupações (CBO) mais frequentes nas unidades públicas

`322255` técnico em agente comunitário de saúde (113) · `322205` técnico de enfermagem (74) ·
`225125` médico clínico (61) · `422105` recepcionista (36) · `223505` enfermeiro (33) ·
`322245` técnico de enfermagem da ESF (33) · `225142` médico da ESF (32) ·
`515140` agente de combate às endemias (31) · `223565` enfermeiro da ESF (30) ·
`223293` cirurgião-dentista da ESF (27) · `223605` fisioterapeuta (24) · `251510` psicólogo (19) ·
`223405` farmacêutico (19) · `223208` cirurgião-dentista clínico geral (14) · `223710` nutricionista (11) ·
`251605` assistente social (10) ...

A lista final de CBOs "de atendimento" (item 2) será confirmada na tabela CBO e ficará
configurável. Ponto para o grupo decidir: **agentes comunitários de saúde** (113) atendem
em domicílio, não na unidade. A sugestão é deixá-los de fora por padrão.

## 10. Privacidade

* O PF traz `CNS_PROF` (Cartão SUS), `CPF_PROF` (ofuscado) e `CONSELHO`/`REGISTRO`.
  **O coletor descarta esses campos na leitura.** Guardamos só nome, CBO/ocupação,
  carga horária e competência.
* A fixture `cnes_pf_cidade_ocidental_202609.json` já está sanitizada, sem CNS, CPF ou registro.
* Os PDFs do portal trazem o CNS impresso. Por isso foram colocados no `.gitignore` e
  **não devem ir para o repositório**.

## 11. Memória e custo na VM

PF de GO: 10 MB (DBC) → 46 MB (DBF). A leitura é em fluxo e o filtro por `CODUFMUN`
acontece durante a leitura, então cabe com folga nos 256 MB do coletor. Uma execução
por mês é suficiente: o coletor diário só verifica se apareceu uma competência nova no
FTP e, se não apareceu, encerra.

---

# Decisões tomadas (10/11/2026)

1. **Fonte única: CNES/DATASUS.** O PF mensal fornece os profissionais e a API de dados
   abertos fornece as unidades. O parser de PDF e o de grade semanal foram **descartados**,
   e o portal municipal não é mais usado.
2. **Ocupações:** a lista é configurável em `db/ocupacoes.csv`, gerada a partir da tabela
   CBO oficial do DATASUS (`TAB_CNES.zip` → `CBO.dbf`). Os médicos ficam nas famílias CBO 2002
   2251/2252/2253 (os códigos 2231xx são do CBO 94 e não aparecem no PF). **Agentes
   comunitários de saúde (515105, 322255) e agentes de endemias (515140) ficam fora por padrão.**
   Com esse filtro, 454 dos 815 vínculos de set/2026 aparecem no site.
3. **Horário:** o turno do CNES é o padrão, com a coluna opcional `horario` em `db/unidades.csv`.
4. **Modelo:** a tabela `turno` foi substituída por `vinculo` (profissional, unidade, ocupação,
   carga horária semanal, competência, fonte).
5. **Mapa:** Leaflet + tiles do OpenStreetMap (sem chave do Google). "Como chegar" continua
   como link gratuito do Google Maps.
6. **Interface:** usar "profissionais vinculados a esta unidade", nunca "disponíveis agora",
   e manter o aviso de confirmar por telefone.
7. O pedido pela LAI (item 8) foi adiado.
