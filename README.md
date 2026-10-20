# UniFit

Sistema de gestão de academia com previsão de evasão e análise de postura por vídeo.

React + Vite · FastAPI · PostgreSQL (Supabase) · PyTorch

## Como rodar

Copie `.env.example` para `.env` e preencha a senha do banco e o `JWT_SECRET`.

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python criar_admin.py
python -m uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Acesse http://localhost:5173. A documentação da API fica em http://localhost:8000/docs.

## Produção (Docker)

```bash
docker compose up --build
```

Site e API em http://localhost:8080 (a API em `/api`, servida pelo nginx junto com o frontend já compilado).

## Testes

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest
```

Os testes rodam num schema temporário (`unifit_teste_xxxx`) no Postgres do `.env`, criado a partir de
`banco/schema.sql` e apagado no final; o schema `unifit` não é tocado. Para usar outro servidor, defina
`TEST_DB_HOST`, `TEST_DB_PORT`, `TEST_DB_NAME`, `TEST_DB_USER` e `TEST_DB_PASSWORD`.

## Perfis

- **Aluno**: dados, pagamentos, check-in e treinos
- **Recepção**: alunos, matrículas, financeiro e check-in
- **Instrutor**: treinos e análise de postura
- **Administrador**: tudo, mais relatórios e usuários

## Banco

A estrutura está em `backend/banco/schema.sql` e as alterações em `backend/banco/00N_*.sql`.
Rode cada migração nova no SQL Editor do Supabase, em ordem, e depois regenere o `schema.sql`
com `python exportar_schema.py` (os testes montam o banco a partir dele).
