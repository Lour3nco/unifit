"""Tela "Planos e matrículas": cadastro de planos (administrador) e matrículas (administrador e recepção)."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import exige_perfis
from ..reflexao import tabela
from ..schemas import MatriculaIn, MatriculaStatusIn, PlanoIn
from ..services.academia import (EM_ABERTO, criar_matricula, erro_vigente, exige_aluno, hoje,
                                 matricula_vigente)

router = APIRouter(tags=["planos e matrículas"])
equipe = exige_perfis("administrador", "recepcao")
so_admin = exige_perfis("administrador")
SituacaoMatricula = Literal["", "ativa", "vencida", "trancada", "cancelada", "encerrada"]


@router.get("/planos")
def listar_planos(db: Session = Depends(get_db), _=Depends(equipe)):
    p = tabela("planos")
    return jsonable_encoder([dict(l._mapping) for l in db.execute(select(p).order_by(p.c.ativo.desc(), p.c.valor)).all()])


def _salvar_plano(db: Session, dados: PlanoIn, plano_id=None):
    p = tabela("planos")
    valores = {**dados.model_dump(), "nome": dados.nome.strip()}
    try:
        if plano_id is None:
            plano_id = db.execute(insert(p).values(**valores).returning(p.c.id)).scalar_one()
        elif db.execute(update(p).where(p.c.id == plano_id).values(**valores)).rowcount == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Plano não encontrado.")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um plano com este nome.")
    return jsonable_encoder(dict(db.execute(select(p).where(p.c.id == plano_id)).first()._mapping))


@router.post("/planos", status_code=status.HTTP_201_CREATED)
def criar_plano(dados: PlanoIn, db: Session = Depends(get_db), _=Depends(so_admin)):
    return _salvar_plano(db, dados)


@router.put("/planos/{plano_id}")
def alterar_plano(plano_id: int, dados: PlanoIn, db: Session = Depends(get_db), _=Depends(so_admin)):
    """Mudar o valor não altera cobranças já geradas, só as próximas matrículas."""
    return _salvar_plano(db, dados, plano_id)


@router.get("/matriculas")
def listar_matriculas(situacao: SituacaoMatricula = "", busca: str = "", db: Session = Depends(get_db), _=Depends(equipe)):
    mat, alu, planos = tabela("matriculas"), tabela("alunos"), tabela("planos")
    q = (select(mat.c.id, mat.c.aluno_id, alu.c.nome.label("aluno"), planos.c.nome.label("plano"), planos.c.valor,
                mat.c.data_inicio, mat.c.data_fim, mat.c.status)
         .select_from(mat.join(alu, alu.c.id == mat.c.aluno_id).join(planos, planos.c.id == mat.c.plano_id))
         .order_by(mat.c.data_inicio.desc(), mat.c.id.desc()).limit(300))
    dia = hoje()
    if situacao == "vencida":  # ativa no banco, mas com a data de fim já passada
        q = q.where(mat.c.status == "ativa", mat.c.data_fim < dia)
    elif situacao == "ativa":
        q = q.where(mat.c.status == "ativa", or_(mat.c.data_fim.is_(None), mat.c.data_fim >= dia))
    elif situacao:
        q = q.where(mat.c.status == situacao)
    if busca.strip():
        q = q.where(alu.c.nome.ilike(f"%{busca.strip()}%"))
    saida = []
    for l in db.execute(q).all():
        m = dict(l._mapping)
        m["status"] = str(m["status"])
        m["vigente"] = m["status"] == "ativa" and (m["data_fim"] is None or m["data_fim"] >= dia)
        saida.append(m)
    return jsonable_encoder(saida)


@router.post("/matriculas", status_code=status.HTTP_201_CREATED)
def nova_matricula(dados: MatriculaIn, db: Session = Depends(get_db), _=Depends(equipe)):
    aluno = exige_aluno(db, dados.aluno_id)
    nome = criar_matricula(db, aluno["id"], dados.plano_id, dados.data_inicio)
    return {"mensagem": f"{aluno['nome']} matriculado(a) no plano {nome}. A primeira mensalidade está no Financeiro."}


@router.patch("/matriculas/{matricula_id}")
def mudar_status(matricula_id: int, dados: MatriculaStatusIn, db: Session = Depends(get_db), _=Depends(equipe)):
    """Trancar, cancelar, encerrar ou reativar. Cancelar/encerrar cancela as mensalidades em aberto."""
    mat, pag = tabela("matriculas"), tabela("pagamentos")
    linha = db.execute(select(mat.c.aluno_id).where(mat.c.id == matricula_id)).first()
    if not linha:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Matrícula não encontrada.")
    if dados.status == "ativa":
        vigente = matricula_vigente(db, linha.aluno_id, ignorar_id=matricula_id)
        if vigente:
            raise erro_vigente(vigente)
        # outra "ativa" já vencida do mesmo aluno é encerrada (o banco só aceita uma ativa por aluno)
        db.execute(update(mat).where(mat.c.aluno_id == linha.aluno_id, mat.c.id != matricula_id,
                                     mat.c.status == "ativa", mat.c.data_fim < hoje()).values(status="encerrada"))
    try:
        db.execute(update(mat).where(mat.c.id == matricula_id).values(status=dados.status))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um plano ativo para este aluno.")
    canceladas = 0
    if dados.status in ("cancelada", "encerrada"):
        canceladas = db.execute(update(pag).where(pag.c.matricula_id == matricula_id, pag.c.status.in_(EM_ABERTO))
                                .values(status="cancelado")).rowcount
    db.commit()
    extra = f" {canceladas} mensalidade(s) em aberto cancelada(s)." if canceladas else ""
    return {"mensagem": f"Matrícula {dados.status}.{extra}"}
