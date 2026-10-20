"""Regras de matrícula, pagamento, check-in e renovação automática."""
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.reflexao import tabela
from app.services.academia import criar_matricula, hoje, renovar_matriculas
from conftest import aluno_id_de, mudar_vencimento


@pytest.fixture
def aluno(conta, db, plano_id):
    """Aluno com conta, ficha e matrícula ativa (1ª mensalidade pendente, vencendo hoje)."""
    u, auth = conta("aluno")
    aid = aluno_id_de(db, u)
    criar_matricula(db, aid, plano_id)
    return {"id": aid, "auth": auth}


@pytest.fixture
def recepcao(conta):
    return conta("recepcao")[1]


def _pagamentos(db, aluno_id):
    pag, mat = tabela("pagamentos"), tabela("matriculas")
    return db.execute(select(pag).select_from(pag.join(mat, mat.c.id == pag.c.matricula_id))
                      .where(mat.c.aluno_id == aluno_id).order_by(pag.c.data_vencimento)).all()


# ---- matrícula ----

def test_segunda_matricula_ativa_e_recusada(cliente, aluno, recepcao, plano_id):
    r = cliente.post("/matriculas", json={"aluno_id": aluno["id"], "plano_id": plano_id}, headers=recepcao)
    assert r.status_code == 409


def test_banco_garante_uma_matricula_ativa_por_aluno(db, aluno, plano_id):
    """Mesmo passando por fora da regra do código (dois cliques ao mesmo tempo), o índice único barra."""
    mat = tabela("matriculas")
    with pytest.raises(IntegrityError):
        db.execute(mat.insert().values(aluno_id=aluno["id"], plano_id=plano_id, data_inicio=hoje(), status="ativa"))
    db.rollback()


def test_nova_matricula_depois_de_vencer_encerra_a_antiga(cliente, db, aluno, recepcao, plano_id):
    mudar_vencimento(db, aluno["id"], 40)  # venceu há 10 dias
    r = cliente.post("/matriculas", json={"aluno_id": aluno["id"], "plano_id": plano_id}, headers=recepcao)
    assert r.status_code == 201, r.text
    mat = tabela("matriculas")
    status = sorted(str(m.status) for m in db.execute(select(mat).where(mat.c.aluno_id == aluno["id"])).all())
    assert status == ["ativa", "encerrada"]


def test_aluno_novo_pela_recepcao_sai_matriculado(cliente, db, recepcao, plano_id):
    r = cliente.post("/alunos", json={"nome": "Bruno Lima", "plano_id": plano_id}, headers=recepcao)
    assert r.status_code == 201, r.text
    assert r.json()["vigente"] is True
    assert len(_pagamentos(db, r.json()["id"])) == 1


def test_aluno_novo_com_plano_invalido_nao_e_gravado(cliente, db, recepcao, plano_id):
    r = cliente.post("/alunos", json={"nome": "Bruno Lima", "plano_id": plano_id + 999}, headers=recepcao)
    assert r.status_code == 404
    assert db.scalar(select(func.count()).select_from(tabela("alunos"))) == 0


# ---- pagamento ----

def test_aluno_informa_e_recepcao_confirma(cliente, db, aluno, recepcao):
    pid = _pagamentos(db, aluno["id"])[0].id
    r = cliente.post(f"/meu/pagamentos/{pid}/informar", json={"forma": "pix"}, headers=aluno["auth"])
    assert r.status_code == 200, r.text
    p = _pagamentos(db, aluno["id"])[0]
    assert str(p.status) == "pendente" and p.informado_forma == "Pix"  # informar NÃO quita
    assert cliente.post(f"/meu/pagamentos/{pid}/informar", json={"forma": "pix"},
                        headers=aluno["auth"]).status_code == 409  # não informa duas vezes

    lista = cliente.get("/pagamentos", params={"situacao": "informado"}, headers=recepcao).json()
    assert [x["id"] for x in lista["pagamentos"]] == [pid] and lista["resumo"]["qtd_informados"] == 1

    assert cliente.post(f"/pagamentos/{pid}/baixa", json={"forma": "pix"}, headers=recepcao).status_code == 200
    db.expire_all()
    assert str(_pagamentos(db, aluno["id"])[0].status) == "pago"


def test_baixa_nao_acontece_duas_vezes(cliente, db, aluno, recepcao):
    pid = _pagamentos(db, aluno["id"])[0].id
    assert cliente.post(f"/pagamentos/{pid}/baixa", json={"forma": "dinheiro"}, headers=recepcao).status_code == 200
    assert cliente.post(f"/pagamentos/{pid}/baixa", json={"forma": "dinheiro"}, headers=recepcao).status_code == 409
    assert cliente.post(f"/pagamentos/{pid + 999}/baixa", json={"forma": "pix"}, headers=recepcao).status_code == 404


def test_recusar_informe_volta_a_ser_cobranca_normal(cliente, db, aluno, recepcao):
    pid = _pagamentos(db, aluno["id"])[0].id
    cliente.post(f"/meu/pagamentos/{pid}/informar", json={"forma": "boleto"}, headers=aluno["auth"])
    assert cliente.post(f"/pagamentos/{pid}/recusar-informe", headers=recepcao).status_code == 200
    db.expire_all()
    assert _pagamentos(db, aluno["id"])[0].informado_em is None
    assert cliente.post(f"/pagamentos/{pid}/recusar-informe", headers=recepcao).status_code == 409


def test_aluno_nao_consegue_mais_dar_baixa_sozinho(cliente, db, aluno):
    pid = _pagamentos(db, aluno["id"])[0].id
    assert cliente.post(f"/meu/pagamentos/{pid}/pagar", json={"forma": "pix"}, headers=aluno["auth"]).status_code == 404


# ---- check-in ----

def test_checkin_pelo_app_com_plano_em_dia(cliente, aluno):
    r = cliente.post("/meu/checkin", headers=aluno["auth"])
    assert r.status_code == 201 and r.json()["aberto"] is not None
    assert cliente.post("/meu/checkin", headers=aluno["auth"]).status_code == 409  # já está dentro
    assert cliente.post("/meu/checkout", headers=aluno["auth"]).json()["aberto"] is None


def test_checkin_sem_plano_ativo_e_recusado(cliente, conta, db, recepcao):
    u, auth = conta("aluno")  # ficha sem matrícula
    assert cliente.post("/meu/checkin", headers=auth).status_code == 403
    assert cliente.post("/checkins", json={"aluno_id": aluno_id_de(db, u)}, headers=recepcao).status_code == 403


def test_checkin_com_mensalidade_atrasada(cliente, db, aluno, recepcao):
    mudar_vencimento(db, aluno["id"], 5)  # 1ª mensalidade venceu há 5 dias; plano ainda vale
    assert cliente.post("/meu/checkin", headers=aluno["auth"]).status_code == 403  # app bloqueia
    r = cliente.post("/checkins", json={"aluno_id": aluno["id"]}, headers=recepcao)
    assert r.status_code == 201 and "atraso" in r.json()["aviso"]  # balcão deixa entrar e avisa


def test_pagamento_informado_libera_o_checkin_pelo_app(cliente, db, aluno):
    mudar_vencimento(db, aluno["id"], 5)
    pid = _pagamentos(db, aluno["id"])[0].id
    cliente.post(f"/meu/pagamentos/{pid}/informar", json={"forma": "pix"}, headers=aluno["auth"])
    assert cliente.post("/meu/checkin", headers=aluno["auth"]).status_code == 201


# ---- renovação automática ----

def _matricula(db, aluno_id):
    mat = tabela("matriculas")
    return db.execute(select(mat).where(mat.c.aluno_id == aluno_id)).one()


def _quitar_tudo(db, aluno_id):
    pag = tabela("pagamentos")
    db.execute(pag.update().where(pag.c.id.in_([p.id for p in _pagamentos(db, aluno_id)])).values(status="pago"))
    db.commit()


def test_matricula_que_termina_hoje_ganha_nova_mensalidade(db, aluno):
    _quitar_tudo(db, aluno["id"])
    mudar_vencimento(db, aluno["id"], 30)  # data_fim = hoje
    assert renovar_matriculas(db) == 1
    assert _matricula(db, aluno["id"]).data_fim == hoje() + timedelta(days=30)
    novas = [p for p in _pagamentos(db, aluno["id"]) if str(p.status) == "pendente"]
    assert len(novas) == 1 and novas[0].data_vencimento == hoje() and float(novas[0].valor) == 120
    assert renovar_matriculas(db) == 0  # rodar de novo não duplica


def test_com_duas_mensalidades_em_atraso_para_de_renovar(db, aluno):
    mudar_vencimento(db, aluno["id"], 30)
    assert renovar_matriculas(db) == 1  # 1 em atraso: ainda renova
    mudar_vencimento(db, aluno["id"], 30)
    assert renovar_matriculas(db) == 0  # agora são 2 em atraso
    assert _matricula(db, aluno["id"]).data_fim == hoje()  # não estendeu: vence amanhã


def test_matricula_vencida_ha_muito_tempo_nao_renova_sozinha(db, aluno):
    _quitar_tudo(db, aluno["id"])
    mudar_vencimento(db, aluno["id"], 45)  # venceu há 15 dias
    assert renovar_matriculas(db) == 0


def test_matricula_trancada_nao_renova(cliente, db, aluno, recepcao):
    _quitar_tudo(db, aluno["id"])
    mudar_vencimento(db, aluno["id"], 30)
    mid = _matricula(db, aluno["id"]).id
    assert cliente.patch(f"/matriculas/{mid}", json={"status": "trancada"}, headers=recepcao).status_code == 200
    assert renovar_matriculas(db) == 0
