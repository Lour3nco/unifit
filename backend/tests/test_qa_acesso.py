"""QA: login, e o que o aluno consegue fazer sem pagar (aulas, treinos, check-in).
Cada correção está descrita em docs/correcoes-qa.md (os testes citam o número do bug: B1, B2...)."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from app.config import JWT_SECRET
from app.reflexao import tabela
from app.services.academia import criar_matricula, hoje
from conftest import SENHA, aluno_id_de, gerar_cpf, mudar_vencimento

def _login(cliente, email, senha=SENHA, acesso=None):
    return cliente.post("/auth/login", json={"email": email, "senha": senha, "acesso": acesso})


@pytest.fixture
def recepcao(conta):
    return conta("recepcao")[1]


@pytest.fixture
def instrutor(conta):
    return conta("instrutor")[1]


@pytest.fixture
def aluno(conta, db, plano_id):
    """Aluno com plano ativo e a 1ª mensalidade pendente vencendo hoje (ainda em dia)."""
    u, auth = conta("aluno")
    aid = aluno_id_de(db, u)
    criar_matricula(db, aid, plano_id)
    return {"id": aid, "auth": auth, "usuario": u}


@pytest.fixture
def inadimplente(aluno, db):
    """Plano ainda vigente, mas a 1ª mensalidade venceu há 5 dias e não foi paga."""
    mudar_vencimento(db, aluno["id"], 5)
    return aluno


@pytest.fixture
def sem_plano(conta, db):
    """Conta de aluno com ficha e sem nenhuma matrícula (ex.: cadastrou e não escolheu plano)."""
    u, auth = conta("aluno")
    return {"id": aluno_id_de(db, u), "auth": auth}


@pytest.fixture
def plano_vencido(aluno, db):
    """Plano venceu há 10 dias (fora da janela de renovação) e a mensalidade não foi paga."""
    mudar_vencimento(db, aluno["id"], 40)
    return aluno


def _criar_aula(cliente, auth, dia=None, capacidade=10):
    dia = hoje().weekday() if dia is None else dia
    r = cliente.post("/aulas", json={"nome": "Spinning", "dia_semana": dia, "hora_inicio": "07:00",
                                     "hora_fim": "08:00", "capacidade": capacidade}, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()[-1]["id"]


@pytest.fixture
def aula(cliente, recepcao):
    """Aula ativa no dia da semana de hoje."""
    return _criar_aula(cliente, recepcao)


def _reservar(cliente, auth, aula_id, data=None):
    return cliente.post(f"/meu/aulas/{aula_id}/reservar", json={"data": str(data or hoje())}, headers=auth)


@pytest.fixture
def treino_id(cliente, db, aluno, instrutor):
    """Ficha de treino do aluno, montada pelo instrutor."""
    ex = cliente.post("/exercicios", json={"nome": "Supino reto"}, headers=instrutor)
    assert ex.status_code == 201, ex.text
    ex_id = db.scalar(select(tabela("exercicios").c.id))
    r = cliente.post("/treinos", json={"aluno_id": aluno["id"], "nome": "Treino A",
                                       "itens": [{"exercicio_id": ex_id, "series": 3, "repeticoes": 10}]},
                     headers=instrutor)
    assert r.status_code == 201, r.text
    return db.scalar(select(tabela("treinos").c.id))


def _sessao(cliente, auth, treino_id, ex_id=None, **extra):
    return cliente.post(f"/meu/treinos/{treino_id}/sessoes",
                        json={"treino_id": treino_id, "itens": [{"exercicio_id": ex_id or 1, "series": 3,
                                                                 "repeticoes": 10, "carga_kg": 40}], **extra},
                        headers=auth)


# =====================================================================================================
# Login e sessão
# =====================================================================================================

def test_token_expirado_nao_abre_a_api(cliente, conta):
    u, _ = conta("administrador")
    vencido = jwt.encode({"sub": str(u.id), "perfil": "administrador",
                          "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}, JWT_SECRET, algorithm="HS256")
    assert cliente.get("/auth/me", headers={"Authorization": f"Bearer {vencido}"}).status_code == 401


def test_token_assinado_com_outra_chave_nao_abre_a_api(cliente, conta):
    u, _ = conta("administrador")
    falso = jwt.encode({"sub": str(u.id), "perfil": "administrador",
                        "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "chave-do-atacante", algorithm="HS256")
    assert cliente.get("/usuarios", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_token_sem_assinatura_alg_none_nao_abre_a_api(cliente, conta):
    u, _ = conta("administrador")
    sem_assinatura = jwt.encode({"sub": str(u.id), "perfil": "administrador"}, key=None, algorithm="none")
    assert cliente.get("/usuarios", headers={"Authorization": f"Bearer {sem_assinatura}"}).status_code == 401


def test_aluno_nao_vira_admin_trocando_o_perfil_no_token(cliente, conta):
    """O perfil vale o do banco: um token de aluno com perfil 'administrador' continua sendo aluno."""
    u, _ = conta("aluno")
    forjado = jwt.encode({"sub": str(u.id), "perfil": "administrador",
                          "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, JWT_SECRET, algorithm="HS256")
    assert cliente.get("/usuarios", headers={"Authorization": f"Bearer {forjado}"}).status_code == 403


def test_usuario_apagado_perde_o_acesso(cliente, conta, db):
    u, auth = conta("recepcao")
    db.delete(u)
    db.commit()
    assert cliente.get("/auth/me", headers=auth).status_code == 401


def test_cadastro_publico_nao_cria_administrador(cliente):
    r = cliente.post("/auth/cadastro-equipe", json={"nome": "Hacker", "email": "h@teste.com", "senha": SENHA,
                                                    "perfil": "administrador"})
    assert r.status_code == 422


def test_cadastro_de_equipe_so_entra_depois_de_aprovado(cliente):
    r = cliente.post("/auth/cadastro-equipe", json={"nome": "Nova Recepção", "email": "nova@teste.com",
                                                    "senha": SENHA, "perfil": "recepcao"})
    assert r.status_code == 201
    assert _login(cliente, "nova@teste.com").status_code == 403


def test_login_com_email_invalido_ou_campos_faltando(cliente):
    assert cliente.post("/auth/login", json={"email": "' or 1=1 --", "senha": "x"}).status_code == 422
    assert cliente.post("/auth/login", json={"email": "a@teste.com"}).status_code == 422
    assert cliente.post("/auth/login", json={"email": "a@teste.com", "senha": "x", "acesso": "admin"}).status_code == 422


def test_muitos_erros_do_mesmo_ip_bloqueiam_ate_conta_certa(cliente, conta):
    """Contra quem testa uma senha em várias contas: 20 falhas do mesmo IP bloqueiam o IP."""
    u, _ = conta("administrador")
    for n in range(20):
        assert _login(cliente, f"alvo{n}@teste.com", "errada").status_code == 401
    assert _login(cliente, u.email).status_code == 429


def test_cadastro_sem_plano_entra_sem_matricula(cliente):
    """Sem plano no cadastro, o resumo volta sem matrícula: o frontend manda para "Escolher plano"."""
    r = cliente.post("/auth/cadastro", json={"nome": "Caio Reis", "email": "caio@teste.com", "senha": SENHA,
                                             "cpf": gerar_cpf(777)})
    assert r.status_code == 201, r.text
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    resumo = cliente.get("/meu/resumo", headers=auth).json()
    assert resumo["vinculado"] is True and resumo["matricula"] is None


# =====================================================================================================
# Aulas: quem consegue reservar e fazer check-in
# =====================================================================================================

def test_aluno_em_dia_reserva_faz_checkin_e_cancela(cliente, aluno, aula):
    r = _reservar(cliente, aluno["auth"], aula)
    assert r.status_code == 201, r.text
    rid = r.json()["reserva_id"]
    assert cliente.post(f"/meu/reservas/{rid}/checkin", headers=aluno["auth"]).status_code == 200
    semana = cliente.get("/meu/aulas/semana", headers=aluno["auth"]).json()
    assert semana["aulas"][0]["minha_reserva_id"] == rid and semana["aulas"][0]["eu_presente"] is True


def test_reserva_duplicada_lotada_dia_errado_e_aula_arquivada(cliente, conta, db, aluno, recepcao, plano_id):
    aula_id = _criar_aula(cliente, recepcao, capacidade=1)
    assert _reservar(cliente, aluno["auth"], aula_id).status_code == 201
    assert _reservar(cliente, aluno["auth"], aula_id).status_code == 409  # já reservou

    outro, auth_outro = conta("aluno")
    criar_matricula(db, aluno_id_de(db, outro), plano_id)
    assert _reservar(cliente, auth_outro, aula_id).status_code == 409  # lotada

    assert _reservar(cliente, auth_outro, aula_id, hoje() + timedelta(days=1)).status_code == 400  # dia errado

    cliente.patch(f"/aulas/{aula_id}", json={"ativo": False}, headers=recepcao)
    assert _reservar(cliente, auth_outro, aula_id, hoje() + timedelta(days=7)).status_code == 404  # arquivada


def test_aluno_nao_mexe_na_reserva_de_outro(cliente, conta, db, aluno, aula, plano_id):
    rid = _reservar(cliente, aluno["auth"], aula).json()["reserva_id"]
    outro, auth_outro = conta("aluno")
    criar_matricula(db, aluno_id_de(db, outro), plano_id)
    assert cliente.post(f"/meu/reservas/{rid}/checkin", headers=auth_outro).status_code == 404
    assert cliente.delete(f"/meu/reservas/{rid}", headers=auth_outro).status_code == 404


def test_aluno_nao_acessa_as_rotas_de_aulas_da_equipe(cliente, aluno, aula):
    assert cliente.get("/aulas", headers=aluno["auth"]).status_code == 403
    assert cliente.get("/aulas/performance", headers=aluno["auth"]).status_code == 403
    assert cliente.post("/aulas", json={"nome": "X", "dia_semana": 0, "hora_inicio": "07:00", "hora_fim": "08:00",
                                        "capacidade": 5}, headers=aluno["auth"]).status_code == 403
    assert cliente.get(f"/aulas/{aula}/reservas", params={"data": str(hoje())}, headers=aluno["auth"]).status_code == 403


def test_inadimplente_nao_reserva_aula(cliente, inadimplente, aula):
    assert _reservar(cliente, inadimplente["auth"], aula).status_code == 403


def test_aluno_sem_plano_nao_reserva_aula(cliente, sem_plano, aula):
    assert _reservar(cliente, sem_plano["auth"], aula).status_code == 403


def test_aluno_com_plano_vencido_nao_reserva_aula(cliente, plano_vencido, aula):
    assert _reservar(cliente, plano_vencido["auth"], aula).status_code == 403


def test_aluno_com_matricula_trancada_nao_reserva_aula(cliente, db, aluno, recepcao, aula):
    mid = db.scalar(select(tabela("matriculas").c.id).where(tabela("matriculas").c.aluno_id == aluno["id"]))
    assert cliente.patch(f"/matriculas/{mid}", json={"status": "trancada"}, headers=recepcao).status_code == 200
    assert _reservar(cliente, aluno["auth"], aula).status_code == 403


def test_nao_reserva_aula_no_passado(cliente, aluno, aula):
    assert _reservar(cliente, aluno["auth"], aula, hoje() - timedelta(days=7)).status_code == 400


def test_checkin_de_aula_so_no_dia_da_aula(cliente, aluno, aula):
    rid = _reservar(cliente, aluno["auth"], aula, hoje() + timedelta(days=7)).json()["reserva_id"]
    assert cliente.post(f"/meu/reservas/{rid}/checkin", headers=aluno["auth"]).status_code == 400


def test_reserva_com_presenca_nao_e_cancelada_pelo_aluno(cliente, aluno, aula):
    rid = _reservar(cliente, aluno["auth"], aula).json()["reserva_id"]
    cliente.post(f"/meu/reservas/{rid}/checkin", headers=aluno["auth"])
    assert cliente.delete(f"/meu/reservas/{rid}", headers=aluno["auth"]).status_code == 409


# =====================================================================================================
# Treinos e acesso geral de quem não pagou
# =====================================================================================================

def test_inadimplente_ve_e_registra_treino(cliente, db, inadimplente, treino_id):
    """Regra: treino exige plano valendo, mas não bloqueia por atraso (a recepção deixa o inadimplente
    entrar pelo balcão). Ver docs/correcoes-qa.md, B9."""
    ex_id = db.scalar(select(tabela("exercicios").c.id))
    assert cliente.get("/meu/treinos", headers=inadimplente["auth"]).json()["treinos"]
    assert _sessao(cliente, inadimplente["auth"], treino_id, ex_id).status_code == 201


def test_inadimplente_nao_faz_checkin_pelo_app_mas_ve_as_cobrancas(cliente, inadimplente):
    assert cliente.post("/meu/checkin", headers=inadimplente["auth"]).status_code == 403
    pagamentos = cliente.get("/meu/resumo", headers=inadimplente["auth"]).json()["pagamentos"]
    assert [p["status"] for p in pagamentos] == ["pendente"]  # vira "atrasado" só quando a rotina rodar


def test_aluno_nao_registra_treino_na_ficha_de_outro(cliente, conta, db, treino_id, plano_id):
    outro, auth_outro = conta("aluno")
    criar_matricula(db, aluno_id_de(db, outro), plano_id)  # com plano: o que barra é a ficha não ser dele
    ex_id = db.scalar(select(tabela("exercicios").c.id))
    assert _sessao(cliente, auth_outro, treino_id, ex_id).status_code == 404


def test_treino_nao_e_registrado_no_futuro(cliente, db, aluno, treino_id):
    ex_id = db.scalar(select(tabela("exercicios").c.id))
    r = _sessao(cliente, aluno["auth"], treino_id, ex_id, data=str(hoje() + timedelta(days=365)))
    assert r.status_code == 422


def test_plano_vencido_nao_registra_treino(cliente, db, plano_vencido, treino_id):
    ex_id = db.scalar(select(tabela("exercicios").c.id))
    assert _sessao(cliente, plano_vencido["auth"], treino_id, ex_id).status_code == 403


def test_contratar_plano_novo_nao_apaga_a_divida_antiga(cliente, db, plano_vencido, plano_id):
    """Plano venceu sem pagar; o aluno contrata outro: a mensalidade antiga continua bloqueando o check-in."""
    assert cliente.post("/meu/matricula", json={"plano_id": plano_id}, headers=plano_vencido["auth"]).status_code == 201
    assert cliente.post("/meu/checkin", headers=plano_vencido["auth"]).status_code == 403


# =====================================================================================================
# Casos extras das correções (equipe, presença, login)
# =====================================================================================================

def _reserva_no_passado(db, aula_id, aluno_id, presente=False):
    """Reserva de 7 dias atrás, gravada direto no banco (a API não aceita mais reservar no passado)."""
    re = tabela("aula_reservas")
    rid = db.execute(re.insert().values(aula_id=aula_id, aluno_id=aluno_id, data=hoje() - timedelta(days=7),
                                        presente=presente).returning(re.c.id)).scalar_one()
    db.commit()
    return rid


def test_equipe_reserva_para_inadimplente_com_aviso_mas_nao_para_quem_nao_tem_plano(
        cliente, inadimplente, sem_plano, aula, recepcao):
    """B1/B2: pela equipe o atraso não bloqueia (como no check-in do balcão), mas volta um aviso; sem plano, não."""
    r = cliente.post(f"/aulas/{aula}/reservas", json={"data": str(hoje()), "aluno_id": inadimplente["id"]},
                     headers=recepcao)
    assert r.status_code == 201 and "atraso" in r.json()["aviso"]
    r = cliente.post(f"/aulas/{aula}/reservas", json={"data": str(hoje()), "aluno_id": sem_plano["id"]},
                     headers=recepcao)
    assert r.status_code == 403


def test_reserva_de_aluno_em_dia_nao_tem_aviso(cliente, aluno, aula):
    assert _reservar(cliente, aluno["auth"], aula).json()["aviso"] is None


def test_quem_ficou_inadimplente_depois_de_reservar_nao_faz_checkin_da_aula(cliente, db, aluno, aula):
    """B1: reservou em dia, a mensalidade venceu; no dia da aula o check-in pelo app é recusado."""
    rid = _reservar(cliente, aluno["auth"], aula).json()["reserva_id"]
    pag, mat = tabela("pagamentos"), tabela("matriculas")
    mid = db.scalar(select(mat.c.id).where(mat.c.aluno_id == aluno["id"]))
    db.execute(pag.update().where(pag.c.matricula_id == mid).values(data_vencimento=hoje() - timedelta(days=3)))
    db.commit()
    assert cliente.post(f"/meu/reservas/{rid}/checkin", headers=aluno["auth"]).status_code == 403


def test_equipe_lanca_presenca_de_aula_passada_mas_nao_de_aula_futura(cliente, aluno, aula, recepcao, db):
    """B6: a equipe pode corrigir a chamada de uma aula que já passou, nunca adiantar a de uma futura."""
    passada = _reserva_no_passado(db, aula, aluno["id"])
    assert cliente.patch(f"/reservas/{passada}", json={"presente": True}, headers=recepcao).status_code == 200
    futura = _reservar(cliente, aluno["auth"], aula, hoje() + timedelta(days=7)).json()["reserva_id"]
    assert cliente.patch(f"/reservas/{futura}", json={"presente": True}, headers=recepcao).status_code == 400
    assert cliente.patch(f"/reservas/{futura}", json={"presente": False}, headers=recepcao).status_code == 200


def test_aluno_nao_cancela_reserva_de_aula_que_ja_passou(cliente, db, aluno, aula):
    """B7: a reserva passada (com ou sem presença) fica no histórico."""
    rid = _reserva_no_passado(db, aula, aluno["id"])
    assert cliente.delete(f"/meu/reservas/{rid}", headers=aluno["auth"]).status_code == 409


def test_equipe_ainda_cancela_reserva_com_presenca(cliente, aluno, aula, recepcao):
    """B7: a trava vale só para o aluno; a equipe pode corrigir um lançamento errado."""
    rid = _reservar(cliente, aluno["auth"], aula).json()["reserva_id"]
    cliente.post(f"/meu/reservas/{rid}/checkin", headers=aluno["auth"])
    assert cliente.delete(f"/reservas/{rid}", headers=recepcao).status_code == 204


def test_treino_de_hoje_e_de_dias_anteriores_continua_aceito(cliente, db, aluno, treino_id):
    """B8: só data futura é recusada."""
    ex_id = db.scalar(select(tabela("exercicios").c.id))
    assert _sessao(cliente, aluno["auth"], treino_id, ex_id, data=str(hoje())).status_code == 201
    assert _sessao(cliente, aluno["auth"], treino_id, ex_id, data=str(hoje() - timedelta(days=2))).status_code == 201


def test_aluno_sem_plano_nao_registra_treino(cliente, conta, db, treino_id, aluno, recepcao):
    """B9: matrícula cancelada também bloqueia o registro de treino."""
    mid = db.scalar(select(tabela("matriculas").c.id).where(tabela("matriculas").c.aluno_id == aluno["id"]))
    assert cliente.patch(f"/matriculas/{mid}", json={"status": "cancelada"}, headers=recepcao).status_code == 200
    ex_id = db.scalar(select(tabela("exercicios").c.id))
    assert _sessao(cliente, aluno["auth"], treino_id, ex_id).status_code == 403


def test_login_com_email_inexistente_tambem_passa_pelo_bcrypt(cliente, conta, monkeypatch):
    """B10: o tempo de resposta não pode revelar se o e-mail existe."""
    from app.routers import auth as rota_auth
    chamadas = []
    original = rota_auth.verificar_senha
    monkeypatch.setattr(rota_auth, "verificar_senha", lambda s, h: chamadas.append(h) or original(s, h))
    u, _ = conta("recepcao")
    assert _login(cliente, "ninguem@teste.com").status_code == 401
    assert _login(cliente, u.email, "errada").status_code == 401
    assert len(chamadas) == 2  # uma verificação de senha em cada caso


# ---- B13: mensalidade do período cancelada liberava o plano de graça ----

def _cancelar_mensalidade(cliente, db, aluno_id, recepcao):
    pag, mat = tabela("pagamentos"), tabela("matriculas")
    pid = db.scalar(select(pag.c.id).select_from(pag.join(mat, mat.c.id == pag.c.matricula_id))
                    .where(mat.c.aluno_id == aluno_id))
    assert cliente.post(f"/pagamentos/{pid}/cancelar", headers=recepcao).status_code == 200
    return pid


def test_mensalidade_cancelada_bloqueia_checkin_e_aulas_pelo_app(cliente, db, aluno, aula, recepcao):
    rid = _reservar(cliente, aluno["auth"], aula).json()["reserva_id"]  # reservou antes do cancelamento
    _cancelar_mensalidade(cliente, db, aluno["id"], recepcao)
    r = cliente.post("/meu/checkin", headers=aluno["auth"])
    assert r.status_code == 403 and "cancelada" in r.json()["detail"]
    assert cliente.post(f"/meu/reservas/{rid}/checkin", headers=aluno["auth"]).status_code == 403
    assert _reservar(cliente, aluno["auth"], aula, hoje() + timedelta(days=7)).status_code == 403


def test_mensalidade_cancelada_no_balcao_entra_com_aviso_e_reabrir_libera_o_app(cliente, db, aluno, recepcao):
    pid = _cancelar_mensalidade(cliente, db, aluno["id"], recepcao)
    r = cliente.post("/checkins", json={"aluno_id": aluno["id"]}, headers=recepcao)
    assert r.status_code == 201 and "cancelada" in r.json()["aviso"]
    cliente.post("/checkins/saida", json={"aluno_id": aluno["id"]}, headers=recepcao)
    assert cliente.post(f"/pagamentos/{pid}/reabrir", headers=recepcao).status_code == 200
    assert cliente.post("/meu/checkin", headers=aluno["auth"]).status_code == 201  # volta a pendente, vence hoje


def test_mensalidade_antiga_cancelada_nao_bloqueia_se_a_atual_esta_paga(cliente, db, aluno, recepcao):
    """Só a cobrança do período atual conta: cancelar uma antiga (ex.: lançada por engano) não bloqueia."""
    _cancelar_mensalidade(cliente, db, aluno["id"], recepcao)
    pag, mat = tabela("pagamentos"), tabela("matriculas")
    mid = db.scalar(select(mat.c.id).where(mat.c.aluno_id == aluno["id"]))
    db.execute(pag.insert().values(matricula_id=mid, valor=120, data_vencimento=hoje() + timedelta(days=1),
                                   status="pago", data_pagamento=hoje()))
    db.commit()
    assert cliente.post("/meu/checkin", headers=aluno["auth"]).status_code == 201
