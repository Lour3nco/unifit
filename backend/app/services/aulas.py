"""Aulas & Agenda: grade semanal recorrente, reservas, presença (check-in) e performance.
Usado pelas telas da equipe e pela área do aluno."""
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Usuario
from ..reflexao import tabela
from .academia import exige_acesso, hoje, utc


def segunda(d: date) -> date:
    """Segunda-feira da semana que contém a data."""
    return d - timedelta(days=d.weekday())


def _hhmm(t):
    return t.strftime("%H:%M") if t is not None else None


# ---------- definições de aula (CRUD da equipe) ----------

def listar_aulas(db: Session) -> list:
    au, usu = tabela("aulas"), Usuario.__table__
    linhas = db.execute(
        select(au, usu.c.nome.label("instrutor")).select_from(au.outerjoin(usu, usu.c.id == au.c.instrutor_id))
        .order_by(au.c.dia_semana, au.c.hora_inicio)
    ).all()
    return [{"id": l.id, "nome": l.nome, "instrutor_id": l.instrutor_id, "instrutor": l.instrutor,
             "dia_semana": l.dia_semana, "hora_inicio": _hhmm(l.hora_inicio), "hora_fim": _hhmm(l.hora_fim),
             "capacidade": l.capacidade, "ativo": l.ativo} for l in linhas]


def salvar_aula(db: Session, dados, aula_id=None) -> int:
    au = tabela("aulas")
    if dados.instrutor_id is not None and not db.get(Usuario, dados.instrutor_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instrutor não encontrado.")
    valores = {"nome": dados.nome.strip(), "instrutor_id": dados.instrutor_id, "dia_semana": dados.dia_semana,
               "hora_inicio": dados.hora_inicio, "hora_fim": dados.hora_fim, "capacidade": dados.capacidade}
    if aula_id is None:
        aula_id = db.execute(insert(au).values(**valores, ativo=True).returning(au.c.id)).scalar_one()
    elif db.execute(update(au).where(au.c.id == aula_id).values(**valores)).rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aula não encontrada.")
    db.commit()
    return aula_id


def arquivar_aula(db: Session, aula_id, ativo: bool) -> None:
    au = tabela("aulas")
    if db.execute(update(au).where(au.c.id == aula_id).values(ativo=ativo)).rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aula não encontrada.")
    db.commit()


# ---------- grade da semana ----------

def semana(db: Session, d: date, aluno_id=None) -> dict:
    au, re, usu = tabela("aulas"), tabela("aula_reservas"), Usuario.__table__
    ini = segunda(d)
    fim = ini + timedelta(days=6)
    aulas = db.execute(
        select(au, usu.c.nome.label("instrutor")).select_from(au.outerjoin(usu, usu.c.id == au.c.instrutor_id))
        .where(au.c.ativo.is_(True)).order_by(au.c.hora_inicio)
    ).all()
    # contagem de reservas/presenças por aula na semana
    cont = {r.aula_id: r for r in db.execute(
        select(re.c.aula_id, func.count().label("reservados"),
               func.count().filter(re.c.presente.is_(True)).label("presentes"))
        .where(re.c.data.between(ini, fim)).group_by(re.c.aula_id)).all()}
    # reserva do próprio aluno (quando for aluno)
    minhas = {}
    if aluno_id is not None:
        for r in db.execute(select(re).where(re.c.aluno_id == aluno_id, re.c.data.between(ini, fim))).all():
            minhas[r.aula_id] = r
    itens = []
    for a in aulas:
        data_aula = ini + timedelta(days=a.dia_semana)
        c = cont.get(a.id)
        minha = minhas.get(a.id)
        itens.append({
            "aula_id": a.id, "nome": a.nome, "instrutor": a.instrutor, "capacidade": a.capacidade,
            "dia_semana": a.dia_semana, "data": data_aula.isoformat(),
            "hora_inicio": _hhmm(a.hora_inicio), "hora_fim": _hhmm(a.hora_fim),
            "reservados": c.reservados if c else 0, "presentes": c.presentes if c else 0,
            "lotada": (c.reservados if c else 0) >= a.capacidade,
            "minha_reserva_id": minha.id if minha else None,
            "eu_presente": bool(minha.presente) if minha else False,
        })
    return {"inicio": ini.isoformat(), "fim": fim.isoformat(), "aulas": itens}


# ---------- reservas / presença ----------

def _aula_ativa(db: Session, aula_id, travar: bool = False):
    au = tabela("aulas")
    q = select(au).where(au.c.id == aula_id)
    if travar:  # trava a linha da aula: duas reservas ao mesmo tempo na última vaga não passam juntas
        q = q.with_for_update()
    a = db.execute(q).first()
    if not a or not a.ativo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aula não encontrada.")
    return a


def reservar(db: Session, aula_id, data: date, aluno_id, pelo_app: bool = True) -> dict:
    """pelo_app=True: o próprio aluno (precisa de plano valendo e estar sem atraso). Pela equipe só exige
    o plano; o atraso volta como aviso na resposta."""
    a = _aula_ativa(db, aula_id, travar=True)
    if data < hoje():
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Esta aula já aconteceu.")
    if data.weekday() != a.dia_semana:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A data não corresponde ao dia da semana da aula.")
    try:
        aviso = exige_acesso(db, aluno_id, pelo_app)
    except HTTPException:
        db.rollback()  # solta a trava da aula
        raise
    re = tabela("aula_reservas")
    ocupadas = db.scalar(select(func.count()).select_from(re).where(re.c.aula_id == aula_id, re.c.data == data)) or 0
    if ocupadas >= a.capacidade:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Aula lotada.")
    try:
        rid = db.execute(insert(re).values(aula_id=aula_id, aluno_id=aluno_id, data=data).returning(re.c.id)).scalar_one()
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Você já tem reserva nesta aula.")
    return {"reserva_id": rid, "aviso": aviso}


def _reserva(db: Session, reserva_id, aluno_id=None):
    """A reserva (do aluno, quando aluno_id é dado); 404 se não existir ou for de outro aluno."""
    re = tabela("aula_reservas")
    cond = [re.c.id == reserva_id]
    if aluno_id is not None:
        cond.append(re.c.aluno_id == aluno_id)
    r = db.execute(select(re).where(*cond)).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reserva não encontrada.")
    return r


def cancelar(db: Session, reserva_id, aluno_id=None) -> None:
    """O aluno só cancela reserva futura e sem presença (o histórico fica). A equipe cancela qualquer uma."""
    r = _reserva(db, reserva_id, aluno_id)
    if aluno_id is not None:
        if r.presente:
            raise HTTPException(status.HTTP_409_CONFLICT, "Presença já confirmada: a reserva não pode ser cancelada.")
        if r.data < hoje():
            raise HTTPException(status.HTTP_409_CONFLICT, "Esta aula já aconteceu.")
    re = tabela("aula_reservas")
    db.execute(delete(re).where(re.c.id == r.id))
    db.commit()


def marcar_presenca(db: Session, reserva_id, presente: bool, aluno_id=None) -> None:
    """Presença nunca antes do dia da aula. O aluno (aluno_id) só faz check-in no próprio dia da aula e
    com acesso liberado (plano valendo e sem atraso); a equipe pode lançar presença de aula que já passou."""
    r = _reserva(db, reserva_id, aluno_id)
    if presente:
        if r.data > hoje():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "A aula ainda não aconteceu.")
        if aluno_id is not None:
            if r.data != hoje():
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "O check-in só pode ser feito no dia da aula.")
            exige_acesso(db, aluno_id)
    re = tabela("aula_reservas")
    db.execute(update(re).where(re.c.id == r.id).values(
        presente=presente, presenca_em=datetime.now(timezone.utc) if presente else None))
    db.commit()


def roster(db: Session, aula_id, data: date) -> list:
    """Lista de alunos reservados numa ocorrência (equipe/instrutor)."""
    re, al = tabela("aula_reservas"), tabela("alunos")
    linhas = db.execute(
        select(re.c.id, re.c.presente, al.c.nome, al.c.numero_matricula)
        .select_from(re.join(al, al.c.id == re.c.aluno_id))
        .where(re.c.aula_id == aula_id, re.c.data == data).order_by(al.c.nome)
    ).all()
    return [{"reserva_id": l.id, "aluno": l.nome, "matricula": l.numero_matricula, "presente": bool(l.presente)}
            for l in linhas]


# ---------- performance ----------

def performance(db: Session) -> dict:
    au, re, usu = tabela("aulas"), tabela("aula_reservas"), Usuario.__table__
    aulas_ativas = db.scalar(select(func.count()).select_from(au).where(au.c.ativo.is_(True))) or 0
    reservas_total = db.scalar(select(func.count()).select_from(re)) or 0
    presencas_total = db.scalar(select(func.count()).select_from(re).where(re.c.presente.is_(True))) or 0
    por_aula = [{"nome": l.nome, "capacidade": l.capacidade, "reservas": l.reservas, "presencas": l.presencas}
                for l in db.execute(
        select(au.c.nome, au.c.capacidade, func.count(re.c.id).label("reservas"),
               func.count(re.c.id).filter(re.c.presente.is_(True)).label("presencas"))
        .select_from(au.outerjoin(re, re.c.aula_id == au.c.id))
        .group_by(au.c.id, au.c.nome, au.c.capacidade).order_by(func.count(re.c.id).desc()).limit(10)).all()]
    por_instrutor = [{"instrutor": l.instrutor or "—", "aulas": l.aulas, "reservas": l.reservas, "presencas": l.presencas}
                     for l in db.execute(
        select(usu.c.nome.label("instrutor"), func.count(func.distinct(au.c.id)).label("aulas"),
               func.count(re.c.id).label("reservas"), func.count(re.c.id).filter(re.c.presente.is_(True)).label("presencas"))
        .select_from(au.outerjoin(usu, usu.c.id == au.c.instrutor_id).outerjoin(re, re.c.aula_id == au.c.id))
        .group_by(usu.c.nome).order_by(func.count(re.c.id).desc())).all()]
    pct = round(presencas_total / reservas_total * 100) if reservas_total else 0
    return {"aulas_ativas": aulas_ativas, "reservas_total": reservas_total, "presencas_total": presencas_total,
            "presenca_pct": pct, "por_aula": por_aula, "por_instrutor": por_instrutor}


def frequencia_aluno(db: Session, aluno_id) -> dict:
    """Frequência do aluno em aulas + próximas reservas (para o painel de performance)."""
    re, au = tabela("aula_reservas"), tabela("aulas")
    reservas = db.scalar(select(func.count()).select_from(re).where(re.c.aluno_id == aluno_id)) or 0
    presencas = db.scalar(select(func.count()).select_from(re).where(re.c.aluno_id == aluno_id, re.c.presente.is_(True))) or 0
    dia = hoje()  # fuso da academia (em UTC, à noite a aula de hoje já contava como passada)
    linhas = db.execute(
        select(re.c.id, re.c.data, re.c.presente, au.c.nome, au.c.hora_inicio, au.c.hora_fim)
        .select_from(re.join(au, au.c.id == re.c.aula_id))
        .where(re.c.aluno_id == aluno_id).order_by(re.c.data.desc()).limit(20)
    ).all()
    def item(l):
        return {"reserva_id": l.id, "data": l.data.isoformat(), "aula": l.nome,
                "hora_inicio": _hhmm(l.hora_inicio), "hora_fim": _hhmm(l.hora_fim), "presente": bool(l.presente)}
    proximas = [item(l) for l in sorted([x for x in linhas if x.data >= dia], key=lambda x: x.data)]
    recentes = [item(l) for l in linhas if l.data < dia]
    pct = round(presencas / reservas * 100) if reservas else 0
    return {"reservas": reservas, "presencas": presencas, "presenca_pct": pct,
            "proximas": proximas, "recentes": recentes}
