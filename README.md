
# 🚀 Notification Service

<p align="center">
  <b>Plataforma Centralizada de Comunicação Corporativa</b>
</p>

<p align="center">
Serviço responsável pelo gerenciamento e envio de notificações através de múltiplos canais de comunicação.
</p>

---

# 📌 Sobre o Projeto

O **Notification Service** é uma plataforma desenvolvida para centralizar o envio de notificações utilizadas por sistemas corporativos.

A solução funciona como uma camada intermediária entre aplicações internas e provedores externos de comunicação, permitindo que diferentes sistemas enviem mensagens sem precisar implementar integrações individuais.

O primeiro módulo utiliza a **Microsoft Graph API** para envio de emails corporativos, porém a arquitetura foi preparada para suportar novos canais:

- 📧 Email
- 💬 Microsoft Teams
- 📱 WhatsApp Business
- 📲 SMS
- 🔔 Push Notifications

---

# 🎯 Objetivos

## Problema

Em ambientes corporativos é comum encontrar diversos sistemas realizando envio de mensagens individualmente.

Exemplo:

```

Sistema A
└── SMTP próprio

Sistema B
└── Outlook próprio

Sistema C
└── Outra integração

```

Isso gera:

- Credenciais espalhadas.
- Código duplicado.
- Dificuldade de manutenção.
- Falta de rastreabilidade.
- Integrações inconsistentes.

---

## Solução

Criar um serviço único responsável por:

- Gerenciar autenticação.
- Processar mensagens.
- Enviar notificações.
- Registrar histórico.
- Controlar falhas.
- Permitir expansão futura.

---

# 🏗️ Arquitetura

```

```
             SISTEMAS CORPORATIVOS

    ERP        CRM        Aplicações Internas
     |          |                 |
     |          |                 |
     +----------+-----------------+

                REST API

                   |
                   v

        +----------------------+
        | Notification Service |
        +----------------------+

                   |
      +------------+-------------+
      |            |             |

    Email       Teams       WhatsApp

      |
      |
```

Provedores Externos

```
      |
      |
Cliente Final
```

```

---

# ⚙️ Tecnologias

## Backend

- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy
- AsyncIO

## Infraestrutura

- Docker
- Docker Compose
- Redis
- PostgreSQL / MongoDB

## Integrações

- Microsoft Graph API
- OAuth 2.0
- REST API

---

# 📂 Estrutura do Projeto

```

notification-service

src/

├── api/
│   └── routes/
│       ├── notification.py
│       ├── email.py
│       └── health.py
│
├── core/
│   ├── config.py
│   ├── security.py
│   └── exceptions.py
│
├── domain/
│   ├── entities/
│   └── enums/
│
├── services/
│   ├── notification_service.py
│   ├── email_service.py
│   └── template_service.py
│
├── providers/
│   ├── microsoft_graph.py
│   ├── smtp_provider.py
│   └── whatsapp_provider.py
│
├── repositories/
│   ├── notification_repository.py
│   └── template_repository.py
│
├── workers/
│   └── email_worker.py
│
└── main.py

```

---

# 🔄 Fluxo de Funcionamento

```

Sistema Corporativo

```
    |
    |
    v
```

Notification Service

```
    |
    |
```

Validação dos dados

```
    |
    |
```

Processamento do template

```
    |
    |
```

Escolha do provedor

```
    |
    |
```

Envio da mensagem

```
    |
    |
```

Registro do histórico

```
    |
    |
```

Retorno do status

```

---

# 📡 API

## Criar Notificação

```

POST /api/v1/notifications

````

Exemplo:

```json
{
  "channel": "email",
  "recipient": "cliente@email.com",
  "template": "resultado_disponivel",
  "data": {
    "cliente": "João",
    "numero": "12345"
  }
}
````

Resposta:

```json
{
  "notification_id": "987654",
  "status": "PROCESSING"
}
```

---

# 📧 Microsoft Graph Provider

Responsável pela integração com Microsoft Graph API.

Responsabilidades:

* Autenticação OAuth 2.0.
* Gerenciamento de tokens.
* Comunicação com Microsoft Graph.
* Envio de emails.

Fluxo:

```
Application

      |

OAuth Token

      |

Microsoft Graph API

      |

Exchange

      |

Cliente
```

---

# 🧩 Principais Componentes

## NotificationController

Responsável pela entrada das requisições.

Responsabilidades:

* Receber chamadas HTTP.
* Validar payload.
* Iniciar processamento.

---

## NotificationService

Camada principal de negócio.

Responsabilidades:

* Controlar fluxo.
* Escolher provider.
* Gerenciar status.

---

## EmailService

Responsável pelo processamento de emails.

Funções:

* Criar mensagens.
* Aplicar templates.
* Executar envio.

---

## MicrosoftGraphProvider

Responsável pela comunicação com Microsoft Graph.

Funções:

* Autenticação.
* Geração de token.
* Envio de mensagens.

---

## TemplateService

Responsável pela criação dinâmica dos conteúdos.

Funções:

* Carregar templates.
* Substituir variáveis.
* Gerar HTML final.

---

## AuditService

Responsável pelo rastreamento.

Registra:

* Sistema origem.
* Destinatário.
* Data.
* Status.
* Erros.

---

# 📨 Sistema de Templates

O serviço utiliza templates reutilizáveis.

Exemplo:

```
templates/

├── welcome.html
├── password_reset.html
└── report_available.html
```

Modelo:

```html
Olá {{cliente}}

Seu relatório {{numero}} está disponível.
```

Resultado:

```
Olá João

Seu relatório 12345 está disponível.
```

---

# 🗄️ Banco de Dados

## Notification

Campos:

```
id

system_origin

channel

recipient

subject

status

created_at

sent_at

error_message
```

---

## Template

Campos:

```
id

name

content

variables

created_at
```

---

# ⚡ Processamento Assíncrono

Para grandes volumes será utilizado processamento em fila.

Arquitetura:

```
Sistema

 |

API

 |

Queue

 |

Worker

 |

Provider

 |

Cliente
```

Benefícios:

* Escalabilidade.
* Reprocessamento automático.
* Controle de falhas.
* Maior desempenho.

---

# 🔐 Segurança

Implementações:

* OAuth 2.0.
* API Authentication.
* Controle de permissões.
* Criptografia de credenciais.
* Logs de auditoria.
* Rate Limiting.

---

# 📊 Observabilidade

Monitoramento:

* Quantidade de mensagens enviadas.
* Taxa de falhas.
* Tempo de processamento.
* Histórico por sistema.

Exemplo:

```
Sistema: ERP

Mensagens enviadas:
15400

Falhas:
12

Último envio:
01/10/2026
```

---

# 🛣️ Roadmap

## Versão 1.0

* [x] Arquitetura inicial
* [ ] API de notificações
* [ ] Integração Microsoft Graph
* [ ] Templates
* [ ] Logs

## Versão 2.0

* [ ] Redis Queue
* [ ] Dashboard administrativo
* [ ] Retry automático
* [ ] Monitoramento

## Versão 3.0

* [ ] Microsoft Teams
* [ ] WhatsApp Business
* [ ] SMS
* [ ] Inteligência Artificial

---

# 🚀 Execução Local

Instalar dependências:

```bash
pip install -r requirements.txt
```

Executar:

```bash
uvicorn src.main:app --reload
```

Documentação:

```
http://localhost:8000/docs
```

---

# 🐳 Docker

Build:

```bash
docker compose build
```

Executar:

```bash
docker compose up -d
```

---

# 🤝 Integração com Sistemas

Qualquer aplicação pode consumir o serviço através de HTTP.

Compatível com:

* Java
* C#
* Node.js
* Python
* Sistemas legados

Exemplo:

```
Sistema Corporativo

        |

POST /api/v1/notifications

        |

Notification Service

        |

Email enviado
```

---

# 🌎 Visão Futura

O Notification Service pode evoluir para uma plataforma completa de comunicação corporativa.

Possibilidades:

* Comunicação multicanal.
* Inteligência artificial para geração de mensagens.
* Analytics de comunicação.
* Automações.
* Gestão centralizada de notificações.

---

# 📌 Conclusão

O Notification Service cria uma camada única de comunicação para a organização, reduzindo complexidade, aumentando segurança e permitindo que novos sistemas sejam integrados rapidamente.

A solução transforma o envio de mensagens em uma infraestrutura reutilizável, escalável e preparada para futuras tecnologias.

---

# 👨‍💻 Autor

Projeto de arquitetura e desenvolvimento de software corporativo.

```
```
