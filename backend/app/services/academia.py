"""Regras de cadastro, check-in, matrícula e pagamento, usadas pela área do aluno e pelas telas da equipe."""
import logging
import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import Date, cast, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..reflexao import tabela

log = logging.getLogger("unifit")

FUSO = os.getenv("FUSO_ACADEMIA", "America/Sao_Paulo")
FORMAS = {"pix": "Pix", "cartao": "Cartão de crédito", "boleto": "Boleto", "dinheiro": "Dinheiro"}
EM_ABERTO = ("pendente", "atrasado")
JANELA_CHECKIN = timedelta(hours=12)  # check-in sem saída mais velho que isso conta como esquecido
try:
    _TZ = ZoneInfo(FUSO)
except ZoneInfoNotFoundError:  # Windows sem o pacote tzdata: usa o horário de Brasília (UTC-3, sem horário de verão)
    log.warning("fuso %s não encontrado (instale o pacote tzdata); usando UTC-3", FUSO)
    _TZ = timezone(timedelta(hours=-3))


# ---- datas: as colunas de data/hora são timestamptz; "hoje" e "hora" são sempre no fuso da academia ----

def utc(v):
    """Garante fuso no valor enviado ao navegador (um timestamp sem fuso do banco está em UTC)."""
    return v.replace(tzinfo=timezone.utc) if isinstance(v, datetime) and v.tzinfo is None else v


def hoje() -> date:
    return datetime.now(_TZ).date()


def hora_local(coluna):
    """Data e hora no fuso da academia (sem fuso) de uma coluna timestamptz."""
    return func.timezone(FUSO, coluna)


def dia_local(coluna):
    """Data no fuso da academia de uma coluna timestamptz."""
    return cast(hora_local(coluna), Date)


# ---- alunos ----

def salvar_aluno(db: Session, valores: dict, aluno_id=None, commit: bool = True):
    """Insere (aluno_id=None) ou atualiza a linha de "alunos". Devolve o id.
    commit=False: só grava na transação aberta; quem chama faz o commit."""
    alu = tabela("alunos")
    try:
        if aluno_id is None:
            aluno_id = db.execute(insert(alu).values(**valores).returning(alu.c.id)).scalar_one()
        elif db.execute(update(alu).where(alu.c.id == aluno_id).values(**valores)).rowcount == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Aluno não encontrado.")
        if commit:
            db.commit()
        return aluno_id
    except IntegrityError as erro:
        db.rollback()
        if "cpf" in str(erro.orig):
            raise HTTPException(status.HTTP_409_CONFLICT, "Este CPF já está cadastrado para outro aluno.")
        log.warning("salvar_aluno: %s", erro)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Não foi possível salvar. Confira os dados.")


def exige_aluno(db: Session, aluno_id) -> dict:
    alu = tabela("alunos")
    linha = db.execute(select(alu).where(alu.c.id == aluno_id)).first()
    if not linha:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aluno não encontrado.")
    return dict(linha._mapping)


# ---- check-in ----

def checkin_aberto(db: Session, aluno_id):
    chk = tabela("checkins")
    return db.execute(select(chk).where(
        chk.c.aluno_id == aluno_id, chk.c.data_saida.is_(None), chk.c.data_hora >= func.now() - JANELA_CHECKIN,
    ).order_by(chk.c.data_hora.desc()).limit(1)).first()


def mensalidades_em_atraso(db: Session, aluno_id) -> int:
    """Mensalidades vencidas e não pagas. As que o aluno já informou ter pago (aguardando a recepção) não contam."""
    pag, mat = tabela("pagamentos"), tabela("matriculas")
    return db.scalar(select(func.count()).select_from(pag.join(mat, mat.c.id == pag.c.matricula_id)).where(
        mat.c.aluno_id == aluno_id, pag.c.status.in_(EM_ABERTO), pag.c.data_vencimento < hoje(),
        pag.c.informado_em.is_(None))) or 0


def registrar_entrada(db: Session, aluno_id, pelo_app: bool = False) -> str | None:
    """Só entra quem tem plano valendo hoje. Mensalidade em atraso: pelo app bloqueia; no balcão entra,
    mas devolve um aviso para a recepção decidir/cobrar."""
    if checkin_aberto(db, aluno_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um check-in aberto. Faça o check-out antes.")
    mat, dia = tabela("matriculas"), hoje()
    plano = db.execute(select(mat.c.id).where(
        mat.c.aluno_id == aluno_id, mat.c.status == "ativa", mat.c.data_inicio <= dia,
        or_(mat.c.data_fim.is_(None), mat.c.data_fim >= dia)).limit(1)).first()
    if not plano:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sem plano ativo: renove o plano para fazer check-in."
                            if pelo_app else "Este aluno não tem plano ativo. Faça uma nova matrícula antes do check-in.")
    aviso = None
    atrasos = mensalidades_em_atraso(db, aluno_id)
    if atrasos:
        if pelo_app:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "Você tem mensalidade em atraso. Procure a recepção para liberar o check-in.")
        aviso = f"{atrasos} mensalidade(s) em atraso. Cobre o aluno."
    db.execute(insert(tabela("checkins")).values(aluno_id=aluno_id))  # data_hora = now() no banco
    db.commit()
    return aviso


def registrar_saida(db: Session, aluno_id):
    aberto = checkin_aberto(db, aluno_id)
    if not aberto:
        raise HTTPException(status.HTTP_409_CONFLICT, "Não há check-in aberto.")
    chk = tabela("checkins")
    db.execute(update(chk).where(chk.c.id == aberto._mapping["id"]).values(data_saida=func.now()))
    db.commit()


# ---- matrícula ----

def matricula_vigente(db: Session, aluno_id, ignorar_id=None):
    mat = tabela("matriculas")
    q = select(mat.c.id, mat.c.data_fim).where(
        mat.c.aluno_id == aluno_id, mat.c.status == "ativa", or_(mat.c.data_fim.is_(None), mat.c.data_fim >= hoje()))
    if ignorar_id is not None:
        q = q.where(mat.c.id != ignorar_id)
    return db.execute(q.limit(1)).first()


def erro_vigente(vigente) -> HTTPException:
    ate = f" até {vigente.data_fim:%d/%m/%Y}" if vigente.data_fim else ""
    return HTTPException(status.HTTP_409_CONFLICT, f"Já existe um plano ativo{ate}.")


def planos_ativos(db: Session) -> list:
    p = tabela("planos")
    return [dict(l._mapping) for l in db.execute(select(p.c.id, p.c.nome, p.c.valor, p.c.duracao_dias)
                                                 .where(p.c.ativo.is_(True)).order_by(p.c.valor)).all()]


def exige_plano_ativo(db: Session, plano_id) -> dict:
    planos = tabela("planos")
    plano = db.execute(select(planos).where(planos.c.id == plano_id, planos.c.ativo.is_(True))).first()
    if not plano:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plano não encontrado ou inativo.")
    return dict(plano._mapping)


def criar_matricula(db: Session, aluno_id, plano_id, inicio: date | None = None, commit: bool = True) -> str:
    """Cria a matrícula e a primeira cobrança (pendente, vencendo no início). Devolve o nome do plano.
    commit=False: só grava na transação aberta; quem chama faz o commit."""
    mat, pag = tabela("matriculas"), tabela("pagamentos")
    vigente = matricula_vigente(db, aluno_id)
    if vigente:
        raise erro_vigente(vigente)
    p = exige_plano_ativo(db, plano_id)
    inicio = inicio or hoje()
    # a matrícula "ativa" que já venceu (parou de renovar) é encerrada: o banco só aceita uma ativa por aluno
    db.execute(update(mat).where(mat.c.aluno_id == aluno_id, mat.c.status == "ativa", mat.c.data_fim < hoje())
               .values(status="encerrada"))
    try:
        matricula_id = db.execute(insert(mat).values(
            aluno_id=aluno_id, plano_id=p["id"], data_inicio=inicio,
            data_fim=inicio + timedelta(days=p["duracao_dias"]), status="ativa",
        ).returning(mat.c.id)).scalar_one()
    except IntegrityError:  # outra matrícula ativa criada ao mesmo tempo (índice único do 006)
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um plano ativo para este aluno.")
    db.execute(insert(pag).values(matricula_id=matricula_id, valor=p["valor"], data_vencimento=inicio, status="pendente"))
    if commit:
        db.commit()
    return p["nome"]


MAX_ATRASOS_RENOVACAO = 2  # com tantas mensalidades em atraso, a matrícula para de renovar e vence
JANELA_RENOVACAO = timedelta(days=7)  # matrícula vencida há mais tempo que isso não é renovada sozinha


def renovar_matriculas(db: Session) -> int:
    """Renovação automática: matrícula ativa cujo período termina hoje (ou terminou há poucos dias) ganha
    a próxima mensalidade, vencendo hoje, e um novo período a partir de hoje, pelo valor atual do plano.
    Trancar, cancelar ou encerrar para a renovação. Devolve quantas foram renovadas."""
    mat, pag, planos = tabela("matriculas"), tabela("pagamentos"), tabela("planos")
    dia = hoje()
    vencendo = db.execute(
        select(mat.c.id, planos.c.valor, planos.c.duracao_dias)
        .select_from(mat.join(planos, planos.c.id == mat.c.plano_id))
        .where(mat.c.status == "ativa", mat.c.data_fim <= dia, mat.c.data_fim >= dia - JANELA_RENOVACAO)
        .with_for_update(of=mat, skip_locked=True)  # dois processos rodando juntos não renovam a mesma
    ).all()
    renovadas = 0
    for m in vencendo:
        atrasos = db.scalar(select(func.count()).select_from(pag).where(
            pag.c.matricula_id == m.id, pag.c.status.in_(EM_ABERTO), pag.c.data_vencimento < dia)) or 0
        if atrasos >= MAX_ATRASOS_RENOVACAO:
            continue
        db.execute(update(mat).where(mat.c.id == m.id).values(data_fim=dia + timedelta(days=m.duracao_dias)))
        db.execute(insert(pag).values(matricula_id=m.id, valor=m.valor, data_vencimento=dia, status="pendente"))
        renovadas += 1
    db.commit()
    return renovadas


# ---- pagamento ----

def atualizar_atrasados(db: Session):
    """Pendentes com vencimento passado viram "atrasado". Roda na rotina de fundo (services/rotinas.py),
    não nas telas: abrir o financeiro ou o dashboard não escreve no banco."""
    pag = tabela("pagamentos")
    db.execute(update(pag).where(pag.c.status == "pendente", pag.c.data_vencimento < hoje()).values(status="atrasado"))
    db.commit()


def quitar(db: Session, pagamento_id, forma: str):
    """Baixa feita pela equipe (recepção/administrador). O aluno só informa o pagamento (informar_pagamento)."""
    pag = tabela("pagamentos")
    # o WHERE no status evita baixa dupla com dois cliques ao mesmo tempo
    n = db.execute(update(pag).where(pag.c.id == pagamento_id, pag.c.status.in_(EM_ABERTO)).values(
        status="pago", data_pagamento=hoje(), forma_pagamento=FORMAS[forma])).rowcount
    if not n:
        existe = db.scalar(select(pag.c.id).where(pag.c.id == pagamento_id))
        raise (HTTPException(status.HTTP_409_CONFLICT, "Este pagamento já foi quitado ou cancelado.") if existe
               else HTTPException(status.HTTP_404_NOT_FOUND, "Pagamento não encontrado."))
    db.commit()


def informar_pagamento(db: Session, pagamento_id, forma: str, aluno_id):
    """O aluno avisa que pagou; a mensalidade continua em aberto até a recepção confirmar (RN04: só as dele)."""
    pag, mat = tabela("pagamentos"), tabela("matriculas")
    linha = db.execute(select(pag.c.status, pag.c.informado_em)
                       .select_from(pag.join(mat, mat.c.id == pag.c.matricula_id))
                       .where(pag.c.id == pagamento_id, mat.c.aluno_id == aluno_id)).first()
    if not linha:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pagamento não encontrado.")
    if str(linha.status) not in EM_ABERTO:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este pagamento já foi quitado ou cancelado.")
    if linha.informado_em is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Você já informou este pagamento. Aguarde a confirmação da recepção.")
    db.execute(update(pag).where(pag.c.id == pagamento_id).values(informado_em=func.now(), informado_forma=FORMAS[forma]))
    db.commit()


def recusar_informe(db: Session, pagamento_id):
    """A recepção não encontrou o pagamento informado: volta a ser cobrança normal."""
    pag = tabela("pagamentos")
    n = db.execute(update(pag).where(pag.c.id == pagamento_id, pag.c.status.in_(EM_ABERTO),
                                     pag.c.informado_em.is_not(None))
                   .values(informado_em=None, informado_forma=None)).rowcount
    if not n:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta mensalidade não tem pagamento informado em aberto.")
    db.commit()
