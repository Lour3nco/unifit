"""Login (RF01), limite de tentativas e cadastro público de aluno."""
from sqlalchemy import func, select

from app.models import Usuario
from app.reflexao import tabela
from conftest import SENHA, gerar_cpf


def _login(cliente, email, senha=SENHA, acesso=None):
    return cliente.post("/auth/login", json={"email": email, "senha": senha, "acesso": acesso})


def test_login_certo_devolve_token_que_abre_a_api(cliente, conta):
    u, _ = conta("administrador")
    r = _login(cliente, u.email.upper())  # e-mail não diferencia maiúsculas
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = cliente.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json() == {"id": u.id, "nome": u.nome, "email": u.email, "perfil": "administrador"}


def test_senha_errada_e_email_inexistente_dao_a_mesma_resposta(cliente, conta):
    u, _ = conta("recepcao")
    errada, inexistente = _login(cliente, u.email, "outra-senha"), _login(cliente, "ninguem@teste.com")
    assert errada.status_code == inexistente.status_code == 401
    assert errada.json() == inexistente.json()  # não revela quais e-mails existem


def test_conta_inativa_nao_entra(cliente, conta):
    u, _ = conta("instrutor", ativo=False)
    assert _login(cliente, u.email).status_code == 403


def test_aba_errada_no_login(cliente, conta):
    aluno, _ = conta("aluno")
    equipe, _ = conta("recepcao")
    assert _login(cliente, aluno.email, acesso="equipe").status_code == 403
    assert _login(cliente, equipe.email, acesso="aluno").status_code == 403
    assert _login(cliente, aluno.email, acesso="aluno").status_code == 200


def test_cinco_erros_bloqueiam_o_email_mesmo_com_a_senha_certa(cliente, conta):
    u, _ = conta("administrador")
    for _ in range(5):
        assert _login(cliente, u.email, "errada").status_code == 401
    r = _login(cliente, u.email)
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_login_certo_zera_as_falhas_do_email(cliente, conta):
    u, _ = conta("administrador")
    for _ in range(4):
        _login(cliente, u.email, "errada")
    assert _login(cliente, u.email).status_code == 200
    for _ in range(4):
        _login(cliente, u.email, "errada")
    assert _login(cliente, u.email).status_code == 200  # contagem recomeçou


def test_token_invalido_e_sem_token(cliente):
    assert cliente.get("/auth/me").status_code == 401
    assert cliente.get("/auth/me", headers={"Authorization": "Bearer lixo"}).status_code == 401


# ---- cadastro público ----

def _cadastro(cliente, plano_id, **extra):
    dados = {"nome": "Ana Souza", "email": "ana@teste.com", "senha": SENHA, "cpf": gerar_cpf(501), "plano_id": plano_id}
    return cliente.post("/auth/cadastro", json={**dados, **extra})


def test_cadastro_cria_conta_ficha_matricula_e_cobranca(cliente, db, plano_id):
    r = _cadastro(cliente, plano_id)
    assert r.status_code == 201, r.text
    assert r.json()["usuario"]["perfil"] == "aluno"
    alu, mat, pag = tabela("alunos"), tabela("matriculas"), tabela("pagamentos")
    aluno = db.execute(select(alu).where(alu.c.email == "ana@teste.com")).first()
    assert aluno.usuario_id == r.json()["usuario"]["id"]
    matricula = db.execute(select(mat).where(mat.c.aluno_id == aluno.id)).one()
    assert str(matricula.status) == "ativa"
    cobranca = db.execute(select(pag).where(pag.c.matricula_id == matricula.id)).one()
    assert str(cobranca.status) == "pendente" and float(cobranca.valor) == 120


def test_cadastro_que_falha_nao_deixa_conta_pela_metade(cliente, db, plano_id):
    assert _cadastro(cliente, plano_id + 999).status_code == 404  # plano inexistente
    assert _cadastro(cliente, plano_id, cpf="11111111111").status_code == 422  # CPF inválido
    assert _cadastro(cliente, plano_id, senha="curta12").status_code == 422  # menos de 8 caracteres
    assert db.scalar(select(func.count()).select_from(Usuario)) == 0
    assert db.scalar(select(func.count()).select_from(tabela("alunos"))) == 0


def test_cadastro_com_email_ou_cpf_repetido(cliente, plano_id):
    assert _cadastro(cliente, plano_id).status_code == 201
    assert _cadastro(cliente, plano_id, cpf=gerar_cpf(502)).status_code == 409  # mesmo e-mail
    assert _cadastro(cliente, plano_id, email="outra@teste.com").status_code == 409  # mesmo CPF
