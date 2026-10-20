"""Dashboard (RF09): indicadores da academia para a equipe."""
import os
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..ai import churn
from ..database import get_db
from ..deps import exige_perfis
from ..reflexao import tabela
from ..schemas import AlunoRisco, CheckinDia, DashboardOut
from ..services.academia import EM_ABERTO, dia_local, hoje as hoje_local

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
acesso = exige_perfis("administrador", "recepcao", "instrutor")
# demonstração do RF12 (CPU x GPU): roda 100 mil inferências; desligado por padrão em produção
BENCHMARK_ATIVO = os.getenv("BENCHMARK_ATIVO", "false").lower() in ("1", "true", "sim")


@router.get("", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), _=Depends(acesso)):
    hoje = hoje_local()
    alu, mat, pag, chk, prev = (tabela(t) for t in ("alunos", "matriculas", "pagamentos", "checkins",
                                                     "previsoes_evasao"))

    # alunos com plano valendo hoje (matrícula "ativa" já vencida não conta)
    ativos = db.scalar(select(func.count(func.distinct(mat.c.aluno_id))).where(
        mat.c.status == "ativa", or_(mat.c.data_fim.is_(None), mat.c.data_fim >= hoje))) or 0

    receita_mes = float(db.scalar(select(func.coalesce(func.sum(pag.c.valor), 0)).where(
        pag.c.status == "pago", pag.c.data_pagamento >= hoje.replace(day=1))) or 0)

    # inadimplência: % dos alunos com matrícula ativa que têm mensalidade vencida e não paga (calculado na hora)
    vencida = pag.c.status.in_(EM_ABERTO) & (pag.c.data_vencimento < hoje)
    com_matricula = db.scalar(select(func.count(func.distinct(mat.c.aluno_id))).where(mat.c.status == "ativa")) or 0
    devendo = db.scalar(select(func.count(func.distinct(mat.c.aluno_id)))
                        .select_from(pag.join(mat, mat.c.id == pag.c.matricula_id))
                        .where(vencida, mat.c.status == "ativa")) or 0
    atrasados = db.scalar(select(func.count()).select_from(pag).where(vencida)) or 0

    dia = dia_local(chk.c.data_hora)
    por_dia = dict(db.execute(select(dia, func.count()).where(dia >= hoje - timedelta(days=6)).group_by(dia)).all())
    checkins_por_dia = [CheckinDia(dia=DIAS[d.weekday()], total=por_dia.get(d, 0))
                        for d in (hoje - timedelta(days=i) for i in range(6, -1, -1))]

    # 5 maiores riscos do último cálculo de evasão (Relatórios > Calcular agora)
    ultima = select(func.max(prev.c.data_previsao)).scalar_subquery()
    risco = [AlunoRisco(id=a, nome=n, probabilidade=round(float(p) * 100), motivo="")
             for a, n, p in db.execute(
                 select(prev.c.aluno_id, alu.c.nome, prev.c.probabilidade)
                 .select_from(prev.join(alu, alu.c.id == prev.c.aluno_id))
                 .where(prev.c.data_previsao == ultima).order_by(prev.c.probabilidade.desc()).limit(5)).all()]

    return DashboardOut(
        alunos_ativos=ativos, receita_mes=receita_mes,
        inadimplencia_pct=round(devendo / com_matricula * 100, 1) if com_matricula else 0.0,
        pagamentos_atrasados=atrasados, checkins_hoje=por_dia.get(hoje, 0), checkins_por_dia=checkins_por_dia,
        alunos_em_risco=risco, dispositivo_ia=str(churn.dispositivo()), benchmark_ativo=BENCHMARK_ATIVO,
    )


@router.get("/benchmark")  # RF12 (versão inicial)
def benchmark(_=Depends(exige_perfis("administrador", "instrutor"))):
    if not BENCHMARK_ATIVO:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Benchmark desativado (BENCHMARK_ATIVO=false).")
    return churn.benchmark()
