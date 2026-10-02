
# 🚀 Notification Service

<p align="center">
  <img src="https://img.shields.io/badge/status-em%20desenvolvimento-blue">
  <img src="https://img.shields.io/badge/python-3.12+-yellow">
  <img src="https://img.shields.io/badge/FastAPI-backend-green">
  <img src="https://img.shields.io/badge/architecture-enterprise-purple">
</p>

<h3 align="center">
Plataforma Centralizada de Comunicação Corporativa
</h3>

<p align="center">
Serviço responsável por gerenciar, processar e distribuir notificações corporativas através de múltiplos canais de comunicação.
</p>


---

# 📌 Visão Geral

O **Notification Service** é uma plataforma de comunicação desenvolvida para centralizar o envio de notificações utilizadas por sistemas corporativos.

A solução atua como uma camada intermediária entre aplicações internas e provedores externos, eliminando a necessidade de cada sistema implementar sua própria integração de comunicação.

Com isso, aplicações corporativas conseguem enviar mensagens através de uma única API padronizada.

Exemplo:

```

ERP
|
CRM
|
Sistema Laboratorial
|
Aplicações Internas

```
      |
      v
```

Notification Service

```
      |
      +----------------+
      |                |
    Email            Teams
    WhatsApp         SMS
    Push
```

```

---

# 🎯 Motivação

## O problema

Em ambientes corporativos é comum cada aplicação possuir sua própria implementação de comunicação.

Exemplo:

```

Sistema A
|
+-- SMTP próprio

Sistema B
|
+-- Integração Outlook

Sistema C
|
+-- API independente

```

Esse modelo gera:

- 🔴 Credenciais distribuídas em vários sistemas.
- 🔴 Código duplicado.
- 🔴 Alto custo de manutenção.
- 🔴 Falta de padronização.
- 🔴 Dificuldade de auditoria.
- 🔴 Baixa escalabilidade.

---

# 💡 A solução

O Notification Service cria uma camada única responsável por:

- Gerenciamento de autenticação.
- Processamento de mensagens.
- Controle de templates.
- Integração com provedores.
- Histórico de notificações.
- Auditoria.
- Controle de falhas.
- Processamento assíncrono.

Resultado:

```

Antes:

Sistema → Email Provider

Depois:

Sistema
|
|
Notification Service
|
|
Provider
|
Cliente

```

---

# 🏗️ Arquitetura

A arquitetura segue princípios de:

- Clean Architecture.
- Provider Pattern.
- Separação de responsabilidades.
- Baixo acoplamento.
- Alta extensibilidade.


```

```
                SISTEMAS CORPORATIVOS

    ERP        CRM        Aplicações Internas

      \          |             /

               REST API

                   |

          +----------------+
          | Notification   |
          |    Service     |
          +----------------+

                   |

    +--------------+--------------+

    |              |              |

  Email          Teams        WhatsApp

    |
```

Provedor Externo

```
    |

  Usuário Final
```

```

---

# ⚙️ Stack Tecnológica


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
- PostgreSQL
- MongoDB


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
│   ├── enums/
│   └── interfaces/
│
├── services/
│   ├── notification_service.py
│   ├── email_service.py
│   ├── template_service.py
│   └── audit_service.py
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
│   └── notification_worker.py
│
└── main.py

```

---

# 🔄 Fluxo de Processamento


```

Sistema Corporativo

```
    |

    v
```

POST /notifications

```
    |

    v
```

Validação da requisição

```
    |

    v
```

Processamento do Template

```
    |

    v
```

Seleção do Provider

```
    |

    v
```

Envio da Mensagem

```
    |

    v
```

Registro de Auditoria

```
    |

    v
```

Retorno do Status

```

---

# 📡 API


## Criar Notificação


```

POST /api/v1/notifications

````


Request:

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

Response:

```json
{
  "notification_id": "987654",
  "status": "PROCESSING"
}
```

---

# 📧 Microsoft Graph Provider

Primeiro provider implementado utilizando Microsoft Graph API.

Responsabilidades:

* Autenticação OAuth 2.0.
* Gerenciamento de tokens.
* Comunicação com Microsoft Graph.
* Envio de emails corporativos.

Fluxo:

```
Application

     |

OAuth 2.0

     |

Microsoft Graph API

     |

Exchange Online

     |

Destinatário
```

---

# 🧩 Componentes Principais

## NotificationController

Responsável pela entrada das requisições.

Responsabilidades:

* Receber chamadas HTTP.
* Validar payload.
* Encaminhar processamento.

---

## NotificationService

Núcleo da aplicação.

Responsabilidades:

* Orquestrar fluxo.
* Definir provider.
* Controlar estados.

---

## Provider Layer

Camada responsável pelas integrações externas.

Exemplo:

```
NotificationService

        |

Provider Interface

        |

+---------------+
|               |
Graph        SMTP
Email        WhatsApp
```

---

# 📨 Sistema de Templates

Permite criação de mensagens reutilizáveis.

Estrutura:

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

# 🗄️ Modelo de Dados

## Notification

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

```
id

name

content

variables

created_at
```

---

# ⚡ Processamento Assíncrono

Para grandes volumes de comunicação será utilizado processamento baseado em filas.

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

* Maior desempenho.
* Retry automático.
* Controle de falhas.
* Escalabilidade horizontal.

---

# 🔐 Segurança

Recursos previstos:

* OAuth 2.0.
* Controle de acesso.
* Gestão segura de credenciais.
* Auditoria.
* Rate Limiting.
* Logs estruturados.

---

# 📊 Observabilidade

Métricas disponíveis:

* Mensagens processadas.
* Taxa de sucesso.
* Taxa de erro.
* Tempo médio de envio.
* Histórico por sistema.

Exemplo:

```
Sistema: ERP

Enviadas:
15400

Falhas:
12

Último envio:
01/10/2026
```

---

# 🛣️ Roadmap

## v1.0

* [x] Arquitetura inicial
* [ ] API REST
* [ ] Microsoft Graph Provider
* [ ] Templates
* [ ] Auditoria

## v2.0

* [ ] Redis Queue
* [ ] Workers
* [ ] Dashboard administrativo
* [ ] Retry automático

## v3.0

* [ ] Microsoft Teams
* [ ] WhatsApp Business
* [ ] SMS
* [ ] IA para geração de mensagens

---

# 🚀 Executando Localmente

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

# 🤝 Integração

Qualquer sistema capaz de consumir HTTP pode utilizar o serviço.

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

HTTP API

        |

Notification Service

        |

Mensagem enviada
```

---

# 🌎 Visão Futura

O Notification Service pode evoluir para uma plataforma completa de comunicação empresarial:

Possibilidades:

* Comunicação multicanal.
* Automação inteligente.
* Analytics.
* IA para geração de conteúdo.
* Fluxos automatizados.
* Gestão centralizada.

---

# 📌 Conclusão

O Notification Service transforma comunicação distribuída em uma infraestrutura centralizada, segura e escalável.

A plataforma reduz complexidade operacional, padroniza integrações e permite que novos sistemas utilizem recursos de comunicação sem depender de implementações individuais.

---

# 👨‍💻 Autor

Projeto de arquitetura e desenvolvimento de software corporativo.

```
