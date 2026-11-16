"""'Esqueci a senha' por e-mail e por SMS: link de uso único, com validade, sem revelar quais contas existem."""
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.reflexao import tabela
from app.services import recuperacao
from app.services.notificacoes import telefone_e164
from conftest import SENHA, aluno_id_de

NOVA = "nova-senha-123"


@pytest.fixture
def enviados(monkeypatch):
    """Captura e-mails e SMS em vez de enviar: lista de (canal, destino, texto)."""
    caixa = []
    monkeypatch.setattr(recuperacao, "enviar_email", lambda para, assunto, texto: caixa.append(("email", para, texto)))
    monkeypatch.setattr(recuperacao, "enviar_sms", lambda tel, texto: caixa.append(("sms", tel, texto)))
    return caixa


def _token(texto: str) -> str:
    return re.search(r"/redefinir-senha\?token=([\w-]+)", texto).group(1)


def _pedir(cliente, **dados):
    return cliente.post("/auth/esqueci-senha", json=dados)


def _redefinir(cliente, token, senha=NOVA):
    return cliente.post("/auth/redefinir-senha", json={"token": token, "senha": senha})


def _login(cliente, email, senha):
    return cliente.post("/auth/login", json={"email": email, "senha": senha}).status_code


def _com_telefone(db, usuario, telefone):
    alu = tabela("alunos")
    db.execute(alu.update().where(alu.c.id == aluno_id_de(db, usuario)).values(telefone=telefone))
    db.commit()


def test_troca_de_senha_por_email(cliente, conta, enviados):
    u, _ = conta("recepcao")
    r = _pedir(cliente, email=u.email.upper())
    assert r.status_code == 200
    assert [(c, d) for c, d, _ in enviados] == [("email", u.email)]
    assert _redefinir(cliente, _token(enviados[0][2])).status_code == 200
    assert _login(cliente, u.email, NOVA) == 200
    assert _login(cliente, u.email, SENHA) == 401  # a senha antiga deixa de valer


def test_troca_de_senha_por_sms_com_telefone_em_outro_formato(cliente, conta, db, enviados):
    u, _ = conta("aluno")
    _com_telefone(db, u, "(11) 98888-7777")
    assert _pedir(cliente, telefone="+55 11 988887777").status_code == 200
    assert len(enviados) == 1 and enviados[0][:2] == ("sms", "(11) 98888-7777")
    assert "vale 30 min" in enviados[0][2]
    assert _redefinir(cliente, _token(enviados[0][2])).status_code == 200
    assert _login(cliente, u.email, NOVA) == 200


def test_conta_inexistente_recebe_a_mesma_resposta_e_nada_e_enviado(cliente, conta, enviados):
    u, _ = conta("recepcao")
    existe, nao_existe = _pedir(cliente, email=u.email), _pedir(cliente, email="ninguem@teste.com")
    assert existe.json() == nao_existe.json() and nao_existe.status_code == 200
    sem_tel = _pedir(cliente, telefone="(11) 90000-0000")
    assert sem_tel.json() == existe.json()
    assert len(enviados) == 1  # só a conta que existe recebeu


def test_conta_inativa_nao_recebe_link(cliente, conta, enviados):
    u, _ = conta("instrutor", ativo=False)  # aguardando aprovação
    assert _pedir(cliente, email=u.email).status_code == 200
    assert enviados == []


def test_link_vale_uma_vez_so(cliente, conta, enviados):
    u, _ = conta("recepcao")
    _pedir(cliente, email=u.email)
    token = _token(enviados[0][2])
    assert _redefinir(cliente, token).status_code == 200
    assert _redefinir(cliente, token, "outra-senha-456").status_code == 400
    assert _login(cliente, u.email, NOVA) == 200


def test_link_expirado_nao_vale(cliente, conta, db, enviados):
    u, _ = conta("recepcao")
    _pedir(cliente, email=u.email)
    tok = tabela("senha_tokens")
    db.execute(tok.update().values(expira_em=datetime.now(timezone.utc) - timedelta(minutes=1)))
    db.commit()
    assert _redefinir(cliente, _token(enviados[0][2])).status_code == 400
    assert _login(cliente, u.email, SENHA) == 200  # a senha não mudou


def test_pedir_outro_link_invalida_o_anterior(cliente, conta, enviados):
    u, _ = conta("recepcao")
    _pedir(cliente, email=u.email)
    _pedir(cliente, email=u.email)
    antigo, novo = _token(enviados[0][2]), _token(enviados[1][2])
    assert _redefinir(cliente, antigo).status_code == 400
    assert _redefinir(cliente, novo).status_code == 200


def test_banco_guarda_so_o_hash_do_token(cliente, conta, db, enviados):
    u, _ = conta("recepcao")
    _pedir(cliente, email=u.email)
    token = _token(enviados[0][2])
    guardado = db.execute(select(tabela("senha_tokens"))).one()
    assert guardado.token_hash != token and token not in guardado.token_hash and guardado.canal == "email"


def test_token_inventado_e_senha_curta_sao_recusados(cliente, conta, enviados):
    u, _ = conta("recepcao")
    _pedir(cliente, email=u.email)
    assert _redefinir(cliente, "x" * 43).status_code == 400
    assert _redefinir(cliente, _token(enviados[0][2]), "curta").status_code == 422


def test_pedido_precisa_de_email_ou_telefone_e_nao_dos_dois(cliente):
    assert _pedir(cliente).status_code == 422
    assert _pedir(cliente, email="a@teste.com", telefone="11988887777").status_code == 422


def test_limite_de_pedidos_para_o_mesmo_destino(cliente, conta, enviados):
    """Contra quem usa a rota para encher a caixa (ou a conta de SMS) de alguém."""
    u, _ = conta("recepcao")
    for _ in range(3):
        assert _pedir(cliente, email=u.email).status_code == 200
    assert _pedir(cliente, email=u.email).status_code == 429
    assert len(enviados) == 3


def test_troca_de_senha_libera_quem_estava_bloqueado_por_errar(cliente, conta, enviados):
    u, _ = conta("recepcao")
    for _ in range(5):
        _login(cliente, u.email, "errada")
    assert _login(cliente, u.email, SENHA) == 429
    _pedir(cliente, email=u.email)
    _redefinir(cliente, _token(enviados[0][2]))
    assert _login(cliente, u.email, NOVA) == 200


@pytest.mark.parametrize("entrada, saida", [
    ("(11) 98888-7777", "+5511988887777"), ("11988887777", "+5511988887777"), ("+55 11 98888-7777", "+5511988887777"),
    ("(11) 3333-4444", "+551133334444"), ("98888-7777", None), ("", None), (None, None),
])
def test_telefone_e164(entrada, saida):
    assert telefone_e164(entrada) == saida
