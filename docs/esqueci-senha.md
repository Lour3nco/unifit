# "Esqueci a senha" (e-mail e SMS)

## Como o usuário usa
1. Na tela de login, clica em **Esqueci a senha**.
2. Escolhe **E-mail** ou **Telefone (SMS)** e informa o dado da conta.
3. Recebe um link `.../redefinir-senha?token=...`, que vale **30 minutos** e **uma única vez**.
4. Abre o link, digita a nova senha duas vezes e entra com ela.

Telefone: só funciona para **alunos** com telefone salvo na ficha ("Meus dados" ou cadastro da recepção).
A equipe (recepção, instrutor, administrador) não tem telefone no cadastro e usa o e-mail.
O número é comparado já normalizado: `(11) 98888-7777`, `11988887777` e `+55 11 98888-7777` são o mesmo.

## Para colocar no ar
1. Rodar `backend/banco/009_recuperacao_senha.sql` no SQL Editor do Supabase e **reiniciar o backend**
   (as tabelas são lidas do banco quando o backend sobe).
2. Preencher no `.env` (modelo em `.env.example`):
   - `FRONTEND_URL`: endereço público do frontend (é a base do link).
   - E-mail: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` (e `SMTP_SSL=true` se o servidor usar a porta 465).
   - SMS: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM` (número comprado no Twilio).
3. Sem SMTP ou Twilio configurado, nada é enviado: a mensagem com o link aparece no log do backend.
   Serve para testar em desenvolvimento.

## Segurança
- **Não revela quais contas existem:** a resposta é sempre a mesma ("Se houver uma conta com esses dados...").
  A busca da conta e o envio rodam depois da resposta, então o tempo de resposta também é igual.
- **Só o hash fica no banco:** a tabela `senha_tokens` guarda o SHA-256 do token. Quem lê o banco não consegue usar os links.
- **Uso único e validade:** o link expira em 30 minutos e é invalidado ao ser usado.
  Pedir um link novo invalida os anteriores, e trocar a senha invalida todos os pendentes.
- **Contas inativas** (equipe aguardando aprovação) não recebem link.
- **Limite de pedidos:** 3 pedidos por e-mail/telefone e 10 por IP a cada 15 minutos (429 acima disso).
  Evita que alguém use a rota para encher a caixa de outra pessoa ou gastar créditos de SMS.
- **Desbloqueio:** trocar a senha zera o bloqueio de login por senhas erradas daquele e-mail.

## Limitações
- Sessões já abertas continuam válidas até o token de login expirar (`JWT_EXPIRE_MINUTES`, padrão 60 min).
  O login é por JWT sem lista de revogação, então trocar a senha não derruba quem já estava logado.
- Se o envio falhar (SMTP fora do ar, saldo do Twilio), o usuário não recebe aviso, porque a resposta já foi dada.
  A falha fica no log do backend.
- Vários alunos com o mesmo telefone (ex.: família) recebem um SMS por conta, cada um com o link da própria conta.
- O limite de pedidos fica em memória, como o do login (ver `correcoes-qa.md`).

## Código
| O quê | Onde |
|---|---|
| Rotas `POST /auth/esqueci-senha` e `POST /auth/redefinir-senha` | `backend/app/routers/auth.py` |
| Gerar e validar o link | `backend/app/services/recuperacao.py` |
| Envio de e-mail (SMTP) e SMS (Twilio) | `backend/app/services/notificacoes.py` |
| Limite de pedidos | `backend/app/limite.py` (`envio_permitido`) |
| Tabela `senha_tokens` | `backend/banco/009_recuperacao_senha.sql` |
| Telas | `frontend/src/pages/EsqueciSenha.jsx` |
| Testes | `backend/tests/test_recuperacao_senha.py` |
