# Notification Service

Serviço centralizado de notificações corporativas (FastAPI). Os sistemas internos chamam uma única API REST; o serviço valida, renderiza o template, envia pelo canal escolhido, registra histórico e auditoria e expõe um painel administrativo.

| Canal | Provedor | `recipient` |
|---|---|---|
| `email` | Microsoft Graph (padrão), SMTP, console (dev) | endereço de email |
| `teams` | Webhook de Workflows (Adaptive Card) | alias cadastrado em `TEAMS_WEBHOOKS` |
| `whatsapp` | WhatsApp Business Cloud API (Meta) | telefone E.164 (`+5511999999999`) |
| `sms` | Twilio | telefone E.164 |

**Recursos:** templates por canal (Jinja2 em sandbox) · fila Redis com prioridades (`high`/`normal`/`low`) e retry com backoff · idempotência (`Idempotency-Key`) · rate limit por sistema · API Keys por sistema com permissão por canal, revogação e rotação · auditoria completa · painel web · alerta automático de falhas · IA opcional · retenção/anonimização de dados · migrações Alembic.

## Subir localmente (sem Docker)

```bash
pip install -r requirements.txt
export ADMIN_API_KEY=minha-chave-admin EMAIL_PROVIDER=console
uvicorn app.main:app --reload
```
- Docs da API: http://localhost:8000/docs · Painel: http://localhost:8000/admin/dashboard (entre com a admin key).
- Sem `REDIS_URL`, o envio roda em background no próprio processo. Com `EMAIL_PROVIDER=console` os emails só aparecem no log.

## Subir com Docker (API + worker + Redis + Postgres)

```bash
cp .env.example .env   # preencha ADMIN_API_KEY e as credenciais dos canais que for usar
docker compose up --build
```
A API aplica `alembic upgrade head` ao iniciar; `AUTO_CREATE_TABLES=false` no compose.

## Primeiros passos

```bash
# 1) Template (admin). Em email o conteúdo é HTML; nos demais canais, texto puro.
curl -X POST localhost:8000/api/v1/admin/templates -H "X-Admin-Key: $ADMIN" -H "Content-Type: application/json" -d '{
  "name":"resultado_disponivel","channel":"email",
  "subject":"Resultado {{ numero }} disponível",
  "html_content":"<p>Olá, {{ cliente }}! O resultado {{ numero }} está disponível.</p>",
  "variables":["cliente","numero"]}'

# 2) Sistema cliente (a api_key aparece só nesta resposta)
curl -X POST localhost:8000/api/v1/admin/clients -H "X-Admin-Key: $ADMIN" -H "Content-Type: application/json" \
  -d '{"name":"sistema_laudos","allowed_channels":["email","sms"],"rate_limit_per_minute":60}'

# 3) Enviar
curl -X POST localhost:8000/api/v1/notifications -H "X-API-Key: ns_..." -H "Content-Type: application/json" \
  -H "X-On-Behalf-Of: maria.silva" -H "Idempotency-Key: laudo-12345-aviso" -d '{
  "channel":"email","recipient":"cliente@email.com","template":"resultado_disponivel",
  "priority":"normal","data":{"cliente":"João","numero":"12345"}}'
# -> 202 {"id":"...","status":"PROCESSING"}

# 4) Status
curl localhost:8000/api/v1/notifications/<id> -H "X-API-Key: ns_..."
```

`priority`: `low`, `normal`, `high` ou `auto` (classificada pela IA; sem IA, por palavras-chave).
Todas as variáveis listadas em `variables` do template são obrigatórias em `data` (422 se faltarem).

## Configuração dos canais

**Microsoft Graph (email)** — Registre um app no Entra ID, crie um client secret e conceda a permissão de **aplicativo** `Mail.Send` com consentimento do administrador. Preencha `GRAPH_*`. Restrinja o app às caixas de envio com uma *Application Access Policy* do Exchange Online; sem isso ele poderia enviar como qualquer usuário do tenant.

**Teams** — No canal, crie um fluxo do Power Automate/Workflows "Postar em um canal quando uma solicitação de webhook for recebida". Cadastre a URL em `TEAMS_WEBHOOKS='{"ti-alertas":"https://..."}'` e use `ti-alertas` como `recipient`. A URL é segredo: nunca aparece em logs ou erros.

**WhatsApp** — Configure `WHATSAPP_TOKEN` e `WHATSAPP_PHONE_NUMBER_ID`. A Meta só entrega texto livre dentro da janela de 24h de conversa; para iniciar conversas use um template aprovado: no template do serviço informe `external_template_name` (e `language`); as `variables`, na ordem declarada, viram os parâmetros do corpo.

**SMS** — Configure `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` e `TWILIO_FROM`.

## Painel administrativo (`/admin/dashboard`)

Visão geral (volume, taxa de sucesso, falhas por canal/sistema, principais erros, alerta de falhas), busca de notificações com trilha de auditoria e reenvio manual, gestão de templates, gestão de sistemas (canais permitidos, limite por minuto, revogar/reativar, rotacionar chave) e assistentes de IA.

## Fila, retry e falhas

- Com Redis, o worker (`python -m app.workers.email_worker`) consome as filas em ordem de prioridade. Falhas temporárias (rede, 408/429/5xx) são reenviadas com backoff exponencial até `MAX_ATTEMPTS`, mantendo a prioridade; erros permanentes viram `FAILED`. Rode quantos workers precisar.
- **Alerta de falhas:** quando a taxa de falhas na janela atinge `FAILURE_ALERT_THRESHOLD` (com ao menos `FAILURE_ALERT_MIN_EVENTS` envios finalizados), o painel exibe um alerta (`GET /api/v1/admin/stats`).

## IA (opcional — `ANTHROPIC_API_KEY`)

Tudo é sugestão: nada é salvo ou enviado automaticamente. Revise antes de usar.
- `POST /api/v1/admin/ai/generate-template` — gera um template a partir de uma descrição (as variáveis são extraídas do texto gerado, não confiadas ao modelo).
- `POST /api/v1/admin/ai/classify-priority` e `priority: "auto"` no envio (nunca bloqueia: em falha cai na heurística).
- `POST /api/v1/admin/ai/suggest-reply` — sugere respostas a mensagens de clientes.
- `GET /api/v1/admin/ai/failure-analysis` — alerta por regra + diagnóstico em texto das falhas.

Atenção à privacidade: ao usar IA, o texto dessas chamadas é transmitido à API da Anthropic. Geração de template, sugestão de resposta e análise de falhas são acionadas só pelo admin. Já `priority: "auto"` envia o assunto e o corpo renderizado de cada notificação — não use `auto` se o conteúdo for sensível.

## Segurança e privacidade

- API Keys por sistema, guardadas só como hash SHA-256; cada sistema só consulta as próprias notificações e usa só os canais permitidos. Rotas admin exigem `ADMIN_API_KEY` (desabilitadas se vazia).
- Templates em sandbox Jinja2; no email, autoescape de HTML nas variáveis.
- **Retenção:** com `DATA_RETENTION_DAYS=N`, notificações mais antigas que N dias têm `data` removido e destinatário mascarado (também na auditoria); status, datas e sistema de origem são mantidos. Roda no worker (ou na API, sem Redis); `POST /api/v1/admin/maintenance/purge` executa na hora.
- Segredos vêm de variáveis de ambiente: em produção use um cofre (Azure Key Vault etc.) e sirva a API atrás de HTTPS.
- O rate limit usa Redis quando disponível (compartilhado entre instâncias); sem Redis, é local a cada processo.

## Migrações

```bash
alembic upgrade head                                      # aplicar
alembic revision --autogenerate -m "descrição"            # após alterar modelos
```
Em desenvolvimento, `AUTO_CREATE_TABLES=true` (padrão) cria as tabelas sozinho; em produção use Alembic.

## Testes

```bash
pytest   # 60 testes: API, retry, todos os canais (HTTP simulado), filas, IA, retenção, migrações
```
