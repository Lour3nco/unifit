"""Tela "Alunos" da equipe: busca, cadastro e edição, com a situação de cada aluno."""
import re

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import exige_perfis
from ..reflexao import tabela
from ..schemas import AlunoIn, AlunoNovoIn
from ..services.academia import (EM_ABERTO, JANELA_CHECKIN, criar_matricula, exige_aluno, exige_plano_ativo, hoje,
                                 salvar_aluno, utc)

router = APIRouter(prefix="/alunos", tags=["alunos"])
ver = exige_perfis("administrador", "recepcao", "instrutor")
editar = exige_perfis("administrador", "recepcao")

CAMPOS = ("id", "numero_matricula", "nome", "cpf", "email", "telefone", "data_nascimento", "sexo", "altura_cm", "peso_kg")


def _situacoes(db: Session, ids: list) -> dict:
    """Plano atual, último check-in, mensalidades em atraso e presença agora, por aluno."""
    if not ids:
        return {}
    mat, pag, planos, chk = tabela("matriculas"), tabela("pagamentos"), tabela("planos"), tabela("checkins")
    dia = hoje()
    saida = {i: {"plano": None, "matricula_status": None, "matricula_fim": None, "vigente": False,
                 "ultimo_checkin": None, "atrasados": 0, "na_academia": False} for i in ids}

    ultimas = db.execute(
        select(mat.c.aluno_id, mat.c.status, mat.c.data_fim, planos.c.nome)
        .select_from(mat.join(planos, planos.c.id == mat.c.plano_id))
        .where(mat.c.aluno_id.in_(ids))
        .distinct(mat.c.aluno_id).order_by(mat.c.aluno_id, mat.c.data_inicio.desc(), mat.c.id.desc())
    ).all()
    for aluno_id, st, fim, plano in ultimas:
        saida[aluno_id].update(plano=plano, matricula_status=str(st), matricula_fim=fim,
                               vigente=str(st) == "ativa" and (fim is None or fim >= dia))

    for aluno_id, ultimo in db.execute(select(chk.c.aluno_id, func.max(chk.c.data_hora))
                                       .where(chk.c.aluno_id.in_(ids)).group_by(chk.c.aluno_id)).all():
        saida[aluno_id]["ultimo_checkin"] = utc(ultimo)

    for (aluno_id,) in db.execute(select(chk.c.aluno_id).distinct().where(
            chk.c.aluno_id.in_(ids), chk.c.data_saida.is_(None),
            chk.c.data_hora >= func.now() - JANELA_CHECKIN)).all():
        saida[aluno_id]["na_academia"] = True

    for aluno_id, n in db.execute(
            select(mat.c.aluno_id, func.count()).select_from(pag.join(mat, mat.c.id == pag.c.matricula_id))
            .where(mat.c.aluno_id.in_(ids), pag.c.status.in_(EM_ABERTO), pag.c.data_vencimento < dia)
            .group_by(mat.c.aluno_id)).all():
        saida[aluno_id]["atrasados"] = n
    return saida


def _com_situacao(db: Session, linhas: list) -> list:
    extra = _situacoes(db, [l["id"] for l in linhas])
    return [{**{k: l.get(k) for k in CAMPOS}, "tem_conta": l.get("usuario_id") is not None, **extra[l["id"]]}
            for l in linhas]


@router.get("")
def listar(busca: str = "", db: Session = Depends(get_db), _=Depends(ver)):
    alu = tabela("alunos")
    q = select(alu).order_by(alu.c.nome).limit(200)
    termo = busca.strip()
    if termo:
        conds = [alu.c.nome.ilike(f"%{termo}%"), alu.c.email.ilike(f"%{termo}%")]
        digitos = re.sub(r"\D", "", termo)
        if digitos:
            conds += [alu.c.cpf.like(f"%{digitos}%"), alu.c.numero_matricula.like(f"%{digitos}%")]
        q = q.where(or_(*conds))
    linhas = [dict(l._mapping) for l in db.execute(q).all()]
    return jsonable_encoder(_com_situacao(db, linhas))


@router.post("", status_code=201)
def criar(dados: AlunoNovoIn, db: Session = Depends(get_db), _=Depends(editar)):
    """Novo aluno já matriculado: o número de matrícula é gerado pelo banco."""
    exige_plano_ativo(db, dados.plano_id)  # valida antes de gravar o aluno
    valores = dados.model_dump(exclude={"plano_id", "data_inicio"})
    # aluno e matrícula na mesma transação: se a matrícula falhar, o aluno também não fica gravado
    aluno_id = salvar_aluno(db, {**valores, "nome": dados.nome.strip()}, commit=False)
    criar_matricula(db, aluno_id, dados.plano_id, dados.data_inicio, commit=False)
    db.commit()
    return jsonable_encoder(_com_situacao(db, [exige_aluno(db, aluno_id)])[0])


@router.put("/{aluno_id}")
def alterar(aluno_id: int, dados: AlunoIn, db: Session = Depends(get_db), _=Depends(editar)):
    salvar_aluno(db, {**dados.model_dump(), "nome": dados.nome.strip()}, aluno_id)
    return jsonable_encoder(_com_situacao(db, [exige_aluno(db, aluno_id)])[0])
