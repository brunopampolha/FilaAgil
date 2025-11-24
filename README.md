# Projeto Integrador: Desenvolvimento de Sistemas Orientado a Dispositivos Móveis e Baseados na Web

Integrantes:

Alipio de Oliveira Vieira
Kaique Medeiros de Oliveira
Leonardo Miranda Jaques
Bruno Pampolha
Giovanna Souza Bancala
Jessica Thamires Pereira Da Silva

# FilaÁgil — Prova de Conceito

FilaÁgil oferece senha virtual, previsão de atendimento e painel simples para gestores de unidades públicas.  
Esta etapa do trabalho implementa uma prova de conceito totalmente local com SQLite, backend em Python (Flask) e frontend em HTML/CSS.

## Escopo da Prova de Conceito

| Persona | Fluxo coberto no MVP |
| --- | --- |
| Camila (cidadã ocupada) | Consulta unidades/serviços, gera senha virtual, acompanha posição e previsão de atendimento em tempo real. |
| Seu Joaquim (atendimento prioritário) | Recebe link simplificado, escolhe fila prioritária, gera código numérico e visualiza status. |
| Patrícia (gestora) | Painel web mostra filas em andamento, throughput básico e SLAs previstos. |

### Funcionalidades entregues
1. **Listagem de unidades e serviços** com lotação média e tempo estimado.
2. **Emissão de senha virtual** (prioritária ou padrão) com QR/código numérico para check-in.
3. **Consulta de status do ticket** com posição, previsão e alertas de deslocamento.
4. **Painel do gestor** com visão agregada das filas de cada unidade.
5. **Persistência local** em SQLite, incluindo dados de exemplo para testes.

### Fora de Escopo (futuro)
- Integração com prontuários, autenticação, envio real de notificações.
- Agendamento em slots de horário, analytics avançado e acessibilidade por voz.

## Arquitetura e Tecnologias

```
frontend/ (HTML + CSS)
  index.html         -> fluxo do cidadão
  dashboard.html     -> painel do gestor
backend/
  app.py             -> API Flask
  schema.sql         -> criação do banco SQLite e dados seed
data/
  filaagil.db        -> banco local gerado a partir de schema.sql
```

### Banco de Dados (SQLite)

| Tabela | Descrição |
| --- | --- |
| `units` | Unidades de atendimento com endereço, lotação e georreferência simples. |
| `services` | Serviços ofertados em cada unidade e tempo médio de atendimento. |
| `tickets` | Senhas virtuais emitidas com status, prioridade, previsão e timestamps. |

### API do Backend

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/api/units` | Lista unidades com serviços agregados. |
| `GET` | `/api/services/<unit_id>` | Lista serviços e fila atual por unidade. |
| `GET` | `/api/units/<unit_id>/queue` | Retorna todas as senhas ativas da unidade com posição/prioridade. |
| `POST` | `/api/tickets` | Cria senha virtual (`unit_id`, `service_id`, `customer_name`, `priority_level`). |
| `GET` | `/api/tickets/<ticket_ref>` | Consulta posição e previsão (ID numérico ou código). |
| `POST` | `/api/tickets/<ticket_ref>/checkin` | Confirma presença para liberação do atendimento. |
| `DELETE` | `/api/tickets/<ticket_ref>` | Remove uma senha da fila (status `waiting/called`). |
| `GET` | `/api/dashboard` | Dados resumidos (filas, SLAs, throughput) para o painel do gestor. |

### Frontend

- **Fluxo cidadão (`index.html`)**
  - Seleciona unidade e serviço.
  - Gera senha virtual (prioritária ou comum).
  - Exibe QR/código, posição e contagem regressiva para deslocamento.
- **Painel gestor (`dashboard.html`)**
  - Lista filas ativas com status atual vs SLA configurado.

## Próximos Passos

1. Implementar banco e backend (`backend/app.py`, `backend/schema.sql`).
2. Construir frontend HTML/CSS responsivo.
3. Documentar execução local (criação do DB, execução do servidor e teste do frontend).

## Executando localmente

1. **Instale as dependências**
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Suba a API Flask** (o banco `data/filaagil.db` é criado automaticamente)
   ```bash
   python3 backend/app.py
   ```
3. **Acesse o frontend** em `http://localhost:5000/` (fluxo cidadão) e `http://localhost:5000/dashboard` (painel do gestor).

## Testes rápidos

Use o cliente de testes do Flask para validar as rotas principais:

```bash
python3 - <<'PY'
from backend.app import app
client = app.test_client()
assert client.get('/api/units').status_code == 200
unit_queue = client.get('/api/units/1/queue').get_json()
assert 'queue' in unit_queue
ticket = client.post('/api/tickets', json={
    'unit_id': 1,
    'service_id': 1,
    'customer_name': 'Teste automatizado',
    'priority_level': 0
}).get_json()
assert client.get(f"/api/tickets/{ticket['code']}").status_code == 200
assert client.delete(f"/api/tickets/{ticket['code']}").status_code == 200
assert len(client.get('/api/dashboard').get_json()) >= 1
print('rotas OK')
PY
```
