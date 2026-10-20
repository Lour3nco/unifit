"""RF02: cada perfil só alcança as rotas do seu menu. RN04: o aluno só alcança os próprios dados."""
import pytest

from app.perfis import perfil_para_banco
from app.reflexao import tabela
from app.services.academia import criar_matricula
from conftest import aluno_id_de

PERFIS = ("administrador", "recepcao", "instrutor", "aluno")

# rota -> perfis que podem acessar
ROTAS = {
    "/usuarios": {"administrador"},
    "/relatorios": {"administrador"},
    "/pagamentos": {"administrador", "recepcao"},
    "/matriculas": {"administrador", "recepcao"},
    "/planos": {"administrador", "recepcao"},
    "/checkins/hoje": {"administrador", "recepcao"},
    "/dashboard": {"administrador", "recepcao", "instrutor"},
    "/alunos": {"administrador", "recepcao", "instrutor"},
    "/exercicios": {"administrador", "instrutor"},
    "/meu/resumo": {"aluno"},
    "/meu/treinos": {"aluno"},
}


@pytest.mark.parametrize("rota", ROTAS)
def test_cada_perfil_so_acessa_as_proprias_rotas(cliente, conta, rota):
    for perfil in PERFIS:
        _, auth = conta(perfil)
        r = cliente.get(rota, headers=auth)
        esperado = 200 if perfil in ROTAS[rota] else 403
        assert r.status_code == esperado, f"{perfil} em {rota}: {r.status_code} {r.text}"


@pytest.mark.parametrize("rota", ROTAS)
def test_sem_login_nada_abre(cliente, rota):
    assert cliente.get(rota).status_code == 401


def test_perfil_vale_o_do_banco_e_nao_o_do_token(cliente, conta, db):
    """Rebaixar alguém tem efeito na hora, mesmo com um token emitido antes."""
    u, auth = conta("administrador")
    assert cliente.get("/usuarios", headers=auth).status_code == 200
    u.perfil = perfil_para_banco("recepcao")
    db.commit()
    assert cliente.get("/usuarios", headers=auth).status_code == 403


def test_conta_desativada_perde_o_acesso_na_hora(cliente, conta, db):
    u, auth = conta("recepcao")
    u.ativo = False
    db.commit()
    assert cliente.get("/alunos", headers=auth).status_code == 401


def test_admin_nao_pode_se_rebaixar_nem_se_desativar(cliente, conta):
    u, auth = conta("administrador")
    assert cliente.patch(f"/usuarios/{u.id}", json={"ativo": False}, headers=auth).status_code == 400
    assert cliente.patch(f"/usuarios/{u.id}", json={"perfil": "aluno"}, headers=auth).status_code == 400


def test_aluno_nao_mexe_no_pagamento_de_outro_aluno(cliente, conta, db, plano_id):
    dono, _ = conta("aluno")
    _, auth_intruso = conta("aluno")
    criar_matricula(db, aluno_id_de(db, dono), plano_id)
    pagamento_id = db.execute(tabela("pagamentos").select()).first().id
    r = cliente.post(f"/meu/pagamentos/{pagamento_id}/informar", json={"forma": "pix"}, headers=auth_intruso)
    assert r.status_code == 404  # nem confirma que o pagamento existe
