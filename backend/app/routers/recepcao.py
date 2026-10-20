"""Tela "Check-in" da equipe: registrar entrada e saída de alunos no balcão."""
from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import exige_perfis
from ..reflexao import tabela
from ..schemas import AlunoIdIn
from ..services.academia import (JANELA_CHECKIN, dia_local, exige_aluno, hoje, registrar_entrada,
                                 registrar_saida, utc)

router = APIRouter(prefix="/checkins", tags=["check-in"],
                   dependencies=[Depends(exige_perfis("administrador", "recepcao"))])


@router.get("/hoje")
def de_hoje(db: Session = Depends(get_db)):
    chk, alu = tabela("checkins"), tabela("alunos")
    aberto = chk.c.data_saida.is_(None) & (chk.c.data_hora >= func.now() - JANELA_CHECKIN)
    linhas = db.execute(
        select(chk.c.id, chk.c.aluno_id, alu.c.nome.label("aluno"), chk.c.data_hora, chk.c.data_saida,
               aberto.label("aberto"))
        .select_from(chk.join(alu, alu.c.id == chk.c.aluno_id))
        .where(dia_local(chk.c.data_hora) == hoje())
        .order_by(chk.c.data_hora.desc())
    ).all()
    registros = [{"id": l.id, "aluno_id": l.aluno_id, "aluno": l.aluno, "entrada": utc(l.data_hora),
                  "saida": utc(l.data_saida), "aberto": bool(l.aberto)} for l in linhas]
    return jsonable_encoder({"presentes": sum(r["aberto"] for r in registros), "total": len(registros),
                             "registros": registros})


@router.post("", status_code=status.HTTP_201_CREATED)
def entrada(dados: AlunoIdIn, db: Session = Depends(get_db)):
    """Exige plano ativo. Com mensalidade em atraso entra, mas volta um "aviso" para a recepção."""
    aviso = registrar_entrada(db, exige_aluno(db, dados.aluno_id)["id"])
    return {**de_hoje(db), "aviso": aviso}


@router.post("/saida")
def saida(dados: AlunoIdIn, db: Session = Depends(get_db)):
    registrar_saida(db, exige_aluno(db, dados.aluno_id)["id"])
    return de_hoje(db)
