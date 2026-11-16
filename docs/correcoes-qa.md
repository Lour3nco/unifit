# Correções da rodada de QA (acesso, aulas, treinos e login)

Testes: `backend/tests/test_qa_acesso.py`. Os testes citam o número do bug (B1, B2...).
Para rodar só esta bateria, na pasta `backend`: `python -m pytest tests/test_qa_acesso.py`.

## Regra de acesso (vale para B1–B4 e B9)

Antes, cada tela tinha a sua regra: o check-in na academia pelo app checava plano e atraso, mas reserva de
aula e registro de treino não checavam nada. O bloqueio de "sem plano" existia só no frontend.

Agora existe uma regra única no backend, `exige_acesso` em `backend/app/services/academia.py`:

| Situação do aluno | Check-in na academia (app) | Reservar aula / check-in de aula (app) | Registrar treino (app) | Pela equipe (balcão, reserva para o aluno) |
|---|---|---|---|---|
| Plano valendo, em dia | Libera | Libera | Libera | Libera |
| Plano valendo, mensalidade em atraso | Bloqueia (403) | Bloqueia (403) | **Libera** | Libera com aviso "N mensalidade(s) em atraso" |
| Plano valendo, mensalidade do período **cancelada** (B13) | Bloqueia (403) | Bloqueia (403) | **Libera** | Libera com aviso "reabra a cobrança" |
| Sem plano, plano vencido, trancado ou cancelado | Bloqueia (403) | Bloqueia (403) | Bloqueia (403) | Bloqueia (403) |

"Plano valendo" = matrícula com status `ativa` e hoje dentro de `data_inicio`..`data_fim`.
Mensalidade em atraso = vencida e não paga; a que o aluno já informou ter pago (aguardando a recepção) não conta.

Treino não bloqueia por atraso de propósito: a recepção deixa o inadimplente entrar pelo balcão, então ele
precisa conseguir ver e registrar a ficha. Para mudar, troque `checar_atraso=False` por `True` em
`registrar_meu_treino` (`backend/app/routers/aluno.py`).

---

## B1 — Aluno inadimplente reservava aula
- **Antes:** com mensalidade vencida, o check-in na academia pelo app era recusado, mas a reserva de aula passava (201).
- **Correção:** `reservar` (`backend/app/services/aulas.py`) chama `exige_acesso`. O check-in da aula também,
  então quem reservou em dia e ficou inadimplente antes da aula não consegue confirmar presença.
  Quando a equipe reserva para o aluno, o atraso não bloqueia: a resposta traz `aviso` e a tela mostra um alerta.
- **Testes:** `test_inadimplente_nao_reserva_aula`, `test_quem_ficou_inadimplente_depois_de_reservar_nao_faz_checkin_da_aula`,
  `test_equipe_reserva_para_inadimplente_com_aviso_mas_nao_para_quem_nao_tem_plano`.

## B2 — Aluno sem plano nenhum reservava aula
- **Antes:** bastava ter a ficha de aluno (ex.: cadastrou e não escolheu plano).
- **Correção:** a mesma de B1; sem matrícula ativa, `exige_acesso` devolve 403, inclusive quando é a equipe que reserva.
- **Teste:** `test_aluno_sem_plano_nao_reserva_aula`.

## B3 — Aluno com plano vencido reservava aula
- **Correção:** a mesma de B1 (o período da matrícula precisa incluir hoje).
- **Teste:** `test_aluno_com_plano_vencido_nao_reserva_aula`.

## B4 — Aluno com matrícula trancada reservava aula
- **Correção:** a mesma de B1 (só matrícula com status `ativa` libera).
- **Teste:** `test_aluno_com_matricula_trancada_nao_reserva_aula`.

## B5 — Reserva de aula em data que já passou
- **Antes:** reservar uma aula de semanas atrás era aceito.
- **Correção:** `reservar` recusa data anterior a hoje (400 "Esta aula já aconteceu."), para o aluno e para a equipe.
  No app, a aula passada mostra "Aula encerrada" em vez do botão de reservar.
- **Teste:** `test_nao_reserva_aula_no_passado`.

## B6 — Check-in de aula dias antes da aula
- **Antes:** o aluno reservava a aula da semana seguinte e já marcava presença.
- **Correção:** em `marcar_presenca`:
  - ninguém marca presença em aula futura (400);
  - o aluno só faz check-in no próprio dia da aula (400 nos outros dias);
  - a equipe pode lançar presença de aula que já passou (correção de chamada).
  No app, o botão "Fazer check-in" só aparece no dia da aula.
- **Testes:** `test_checkin_de_aula_so_no_dia_da_aula`, `test_equipe_lanca_presenca_de_aula_passada_mas_nao_de_aula_futura`.

## B7 — Aluno cancelava reserva com presença confirmada (apagava o histórico)
- **Antes:** o cancelamento apagava a reserva mesmo com presença, e também reservas de aulas passadas.
- **Correção:** em `cancelar`, o aluno recebe 409 se a presença já foi confirmada ou se a aula já passou.
  A equipe continua podendo cancelar qualquer reserva, para corrigir lançamentos errados.
  No app, o botão "Cancelar reserva" some nesses casos.
- **Testes:** `test_reserva_com_presenca_nao_e_cancelada_pelo_aluno`, `test_aluno_nao_cancela_reserva_de_aula_que_ja_passou`,
  `test_equipe_ainda_cancela_reserva_com_presenca`.

## B8 — Treino registrado com data no futuro
- **Antes:** era possível registrar uma sessão de treino com data de daqui a um ano, distorcendo os gráficos de evolução.
- **Correção:** validação em `SessaoIn` (`backend/app/schemas.py`): data futura devolve 422. Hoje e dias anteriores continuam aceitos.
- **Testes:** `test_treino_nao_e_registrado_no_futuro`, `test_treino_de_hoje_e_de_dias_anteriores_continua_aceito`.

## B9 — Sem plano, o aluno usava o app pela API
- **Antes:** o bloqueio de "sem plano" estava só no frontend (`App.jsx`); chamando a API direto, o aluno registrava treino,
  reservava aula etc.
- **Correção:** as ações do aluno passaram a checar no backend: reservar aula e check-in de aula (B1) e registrar treino
  (`exige_acesso(..., checar_atraso=False)` em `registrar_meu_treino`). Continuam liberadas, de propósito, as telas de
  que ele precisa para regularizar a situação: resumo, pagamentos, escolher plano, meus dados, ver a ficha e a grade.
- **Testes:** `test_plano_vencido_nao_registra_treino`, `test_aluno_sem_plano_nao_registra_treino`.

## B10 — Tempo de resposta do login revelava quais e-mails existem
- **Antes:** para e-mail inexistente o login respondia sem passar pelo bcrypt, bem mais rápido do que para um e-mail
  cadastrado com senha errada.
- **Correção:** o login sempre compara a senha com um hash; quando o e-mail não existe, usa `HASH_FICTICIO`
  (`backend/app/security.py`). A resposta e o tempo ficam iguais nos dois casos.
- **Teste:** `test_login_com_email_inexistente_tambem_passa_pelo_bcrypt`.

## B11 — Capacidade da aula podia estourar com reservas simultâneas
- **Antes:** o sistema contava as vagas e gravava a reserva em passos separados; duas reservas ao mesmo tempo na
  última vaga podiam passar.
- **Correção:** `reservar` trava a linha da aula (`SELECT ... FOR UPDATE`) até gravar a reserva, então as reservas
  da mesma aula entram uma de cada vez.
- **Teste:** coberto indiretamente por `test_reserva_duplicada_lotada_dia_errado_e_aula_arquivada` (concorrência
  real não é reproduzível de forma confiável num teste).

## B12 — Frequência de aulas errava o dia à noite
- **Antes:** `frequencia_aluno` usava a data em UTC; entre 21h e meia-noite (horário de Brasília) a aula de hoje
  aparecia como "recente" em vez de "próxima".
- **Correção:** usa `hoje()`, no fuso da academia (`FUSO_ACADEMIA`, padrão America/Sao_Paulo).
- **Teste:** sem teste automático (depende do horário em que a suíte roda).

## B13 — Mensalidade cancelada liberava o período de graça
- **Encontrado em:** teste manual. A aluna tinha a única mensalidade **cancelada** e o plano "válido até 01/12";
  ela fazia check-in na academia e nas aulas sem ter pago nada.
- **Causa:** a regra de acesso só olhava mensalidades **em atraso** (pendente/atrasada vencida). Cancelada não é atraso,
  então a matrícula seguia ativa e sem nenhuma pendência.
- **Correção:** em `exige_acesso`, se a cobrança mais recente da matrícula ativa (a do período atual) estiver
  cancelada, conta como pendência, igual ao atraso:
  - pelo app: check-in, reserva e check-in de aula recusados (403 "Sua mensalidade atual foi cancelada...");
  - no balcão / reserva pela equipe: passa, com o aviso "reabra a cobrança no Financeiro";
  - registro de treino continua liberado (mesma decisão do atraso, ver a tabela da regra de acesso).
  Para regularizar: a recepção usa **Reabrir** na mensalidade (ou faz uma nova matrícula). Cancelar uma mensalidade
  antiga, de período que já foi substituído, não bloqueia nada.
- **Telas:** em "Pagamentos" o aluno vê o aviso de que a mensalidade foi cancelada e deve procurar a recepção;
  no Financeiro, a confirmação de "Cancelar" avisa que o aluno perde o acesso pelo app.
- **Testes:** `test_mensalidade_cancelada_bloqueia_checkin_e_aulas_pelo_app`,
  `test_mensalidade_cancelada_no_balcao_entra_com_aviso_e_reabrir_libera_o_app`,
  `test_mensalidade_antiga_cancelada_nao_bloqueia_se_a_atual_esta_paga`.

---

## Não corrigido no código: limite de tentativas de login

O limite (5 erros por e-mail, 20 por IP em 15 minutos, `backend/app/limite.py`) fica **em memória**:
- zera quando o servidor reinicia;
- com vários processos/servidores, cada um conta separado.

Com um único processo do uvicorn (como no `Dockerfile`) ele funciona. Para escalar, a contagem precisa ir para o
Redis ou para o banco.

**Configuração necessária atrás de proxy (Nginx, balanceador, Render etc.):** o `Dockerfile` já usa `--proxy-headers`,
mas o uvicorn só confia no cabeçalho `X-Forwarded-For` vindo de `127.0.0.1`. Se o proxy estiver em outra máquina ou
contêiner, defina a variável de ambiente `FORWARDED_ALLOW_IPS` com o IP do proxy. Sem isso, todos os usuários aparecem
com o IP do proxy e 20 erros de qualquer pessoa bloqueiam o login de todo mundo por 15 minutos.

## Funcionalidade nova: reabrir mensalidade

Recepção e administrador podem desfazer uma baixa ou um cancelamento feito por engano.
- **Tela:** Financeiro → botão "Reabrir" nas mensalidades pagas ou canceladas (pede confirmação).
- **API:** `POST /pagamentos/{id}/reabrir` (`reabrir_pagamento` em `backend/app/services/academia.py`).
- **O que acontece:** a mensalidade volta para `pendente`, ou `atrasado` se o vencimento já passou, e perde a
  data/forma de pagamento e o informe do aluno. Se ficar atrasada, volta a bloquear o check-in e as aulas pelo app.
- **Recusas:** 409 se a mensalidade já está em aberto; 404 se não existe; 403 para instrutor e aluno.
- **Limitação:** não há registro de quem reabriu nem quando (o sistema ainda não tem trilha de auditoria).
- **Testes:** `test_reabrir_pagamento_pago_desfaz_a_baixa`, `test_reabrir_cancelada_vencida_volta_atrasada_e_bloqueia_o_checkin`,
  `test_so_recepcao_e_admin_reabrem_pagamento` (em `backend/tests/test_regras.py`).

## Comportamento mantido de propósito

A renovação automática mantém a matrícula ativa até acumular 2 mensalidades em atraso (cerca de 60 dias num plano
mensal). Com as correções acima, durante esse período o aluno inadimplente fica bloqueado no check-in e nas aulas
pelo app; só o registro de treino continua liberado (ver a tabela da regra de acesso).
