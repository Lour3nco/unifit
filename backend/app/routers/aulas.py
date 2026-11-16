"""Tela "Aulas & Agenda" da equipe: grade semanal, reservas por aluno, presença e performance."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import exige_perfis
from ..schemas import AtivoIn, AulaIn, PresencaIn, ReservaIn
from ..services import aulas as svc
from ..services.academia import exige_aluno

router = APIRouter(tags=["aulas"])
gestores = exige_perfis("administrador", "recepcao", "instrutor")


# ---- grade e performance (rotas estáticas antes das dinâmicas) ----

@router.get("/aulas/semana")
def grade_semana(data: date | None = None, db: Session = Depends(get_db), _=Depends(gestores)):
    return jsonable_encoder(svc.semana(db, data or date.today()))


@router.get("/aulas/performance")
def ver_performance(db: Session = Depends(get_db), _=Depends(gestores)):
    return jsonable_encoder(svc.performance(db))


# ---- definições de aula ----

@router.get("/aulas")
def listar(db: Session = Depends(get_db), _=Depends(gestores)):
    return jsonable_encoder(svc.listar_aulas(db))


@router.post("/aulas", status_code=status.HTTP_201_CREATED)
def criar(dados: AulaIn, db: Session = Depends(get_db), _=Depends(gestores)):
    svc.salvar_aula(db, dados)
    return jsonable_encoder(svc.listar_aulas(db))


@router.put("/aulas/{aula_id}")
def alterar(aula_id: int, dados: AulaIn, db: Session = Depends(get_db), _=Depends(gestores)):
    svc.salvar_aula(db, dados, aula_id)
    return jsonable_encoder(svc.listar_aulas(db))


@router.patch("/aulas/{aula_id}")
def arquivar(aula_id: int, dados: AtivoIn, db: Session = Depends(get_db), _=Depends(gestores)):
    svc.arquivar_aula(db, aula_id, dados.ativo)
    return jsonable_encoder(svc.listar_aulas(db))


# ---- reservas e presença (equipe reserva/registra por aluno) ----

@router.get("/aulas/{aula_id}/reservas")
def lista_reservas(aula_id: int, data: date, db: Session = Depends(get_db), _=Depends(gestores)):
    return jsonable_encoder(svc.roster(db, aula_id, data))


@router.post("/aulas/{aula_id}/reservas", status_code=status.HTTP_201_CREATED)
def reservar_para_aluno(aula_id: int, dados: ReservaIn, db: Session = Depends(get_db), _=Depends(gestores)):
    if dados.aluno_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Informe o aluno.")
    exige_aluno(db, dados.aluno_id)
    return jsonable_encoder(svc.reservar(db, aula_id, dados.data, dados.aluno_id, pelo_app=False))


@router.delete("/reservas/{reserva_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_reserva(reserva_id: int, db: Session = Depends(get_db), _=Depends(gestores)):
    svc.cancelar(db, reserva_id)


@router.patch("/reservas/{reserva_id}")
def presenca(reserva_id: int, dados: PresencaIn, db: Session = Depends(get_db), _=Depends(gestores)):
    svc.marcar_presenca(db, reserva_id, dados.presente)
    return {"ok": True}
