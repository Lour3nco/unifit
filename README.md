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

## Perfis

- **Aluno**: dados, pagamentos, check-in e treinos
- **Recepção**: alunos, matrículas, financeiro e check-in
- **Instrutor**: treinos e análise de postura
- **Administrador**: tudo, mais relatórios e usuários

## Banco

A estrutura está em `backend/banco/schema.sql` e as alterações em `backend/banco/00N_*.sql`.
