"""Tela "Relatórios" (administrador): receita, matrículas, frequência, inadimplência e risco de evasão."""
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy import Integer, cast, extract, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import exige_perfis
from ..reflexao import tabela
from ..services.academia import EM_ABERTO, dia_local, hoje, hora_local, utc

router = APIRouter(prefix="/relatorios", tags=["relatórios"], dependencies=[Depends(exige_perfis("administrador"))])
DIAS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]  # extract(dow): 0 = domingo
MODELO_VERSAO = "rede-evasao-v2"


def _meses(n: int) -> list:
    """Os últimos n meses como 'AAAA-MM', do mais antigo ao atual."""
    d = hoje().replace(day=1)
    saida = []
    for _ in range(n):
        saida.append(d.strftime("%Y-%m"))
        d = (d - timedelta(days=1)).replace(day=1)
    return saida[::-1]


def _vigente(mat, dia):
    return (mat.c.status == "ativa") & or_(mat.c.data_fim.is_(None), mat.c.data_fim >= dia)


@router.get("")
def relatorio(meses: int = Query(6, ge=1, le=24), db: Session = Depends(get_db)):
    pag, mat, alu, planos, chk, prev = (tabela(t) for t in ("pagamentos", "matriculas", "alunos", "planos",
                                                            "checkins", "previsoes_evasao"))
    dia = hoje()
    lista_meses = _meses(meses)
    desde = f"{lista_meses[0]}-01"

    mes_pag = func.to_char(pag.c.data_pagamento, "YYYY-MM")
    receita = dict(db.execute(select(mes_pag, func.sum(pag.c.valor)).where(
        pag.c.status == "pago", pag.c.data_pagamento >= desde).group_by(mes_pag)).all())
    # nova = primeira matrícula do aluno; retorno = ex-aluno que se matriculou de novo
    # (a renovação automática estende a mesma matrícula, então não entra em nenhuma das duas)
    ordem = func.row_number().over(partition_by=mat.c.aluno_id, order_by=(mat.c.data_inicio, mat.c.id)).label("n")
    todas = select(mat.c.data_inicio, ordem).subquery()
    mes_mat = func.to_char(todas.c.data_inicio, "YYYY-MM")
    novas, retornos = {}, {}
    for m, primeira, n in db.execute(select(mes_mat, todas.c.n == 1, func.count()).where(todas.c.data_inicio >= desde)
                                     .group_by(mes_mat, todas.c.n == 1)).all():
        (novas if primeira else retornos)[m] = n
    mensal = [{"mes": m, "receita": float(receita.get(m, 0)), "novas_matriculas": novas.get(m, 0),
               "retornos": retornos.get(m, 0)} for m in lista_meses]

    situacao: dict = {}  # "ativa" com data de fim passada aparece como "vencida"
    for st, fim, n in db.execute(select(mat.c.status, mat.c.data_fim >= dia, func.count())
                                 .group_by(mat.c.status, mat.c.data_fim >= dia)).all():
        chave = "vencida" if str(st) == "ativa" and fim is False else str(st)
        situacao[chave] = situacao.get(chave, 0) + n

    por_plano = [{"plano": p, "alunos": n, "receita_ciclo": float(v or 0)} for p, n, v in db.execute(
        select(planos.c.nome, func.count(), func.sum(planos.c.valor))
        .select_from(mat.join(planos, planos.c.id == mat.c.plano_id))
        .where(_vigente(mat, dia)).group_by(planos.c.nome).order_by(func.count().desc())).all()]

    local = hora_local(chk.c.data_hora)
    periodo = dia_local(chk.c.data_hora) >= desde
    dow = cast(extract("dow", local), Integer)
    por_dia = dict(db.execute(select(dow, func.count()).where(periodo).group_by(dow)).all())
    hora = cast(extract("hour", local), Integer)
    por_hora = dict(db.execute(select(hora, func.count()).where(periodo).group_by(hora)).all())
    frequencia = {
        "por_dia": [{"dia": DIAS[(i + 1) % 7], "total": por_dia.get((i + 1) % 7, 0)} for i in range(7)],  # Seg..Dom
        "por_hora": [{"hora": f"{h}h", "total": por_hora.get(h, 0)} for h in range(5, 24)],
        "total": sum(por_dia.values()),
    }

    inadimplentes = [{"aluno_id": a, "aluno": n, "numero_matricula": nm, "mensalidades": q, "total": float(t),
                      "desde": d} for a, n, nm, q, t, d in db.execute(
        select(alu.c.id, alu.c.nome, alu.c.numero_matricula, func.count(), func.sum(pag.c.valor),
               func.min(pag.c.data_vencimento))
        .select_from(pag.join(mat, mat.c.id == pag.c.matricula_id).join(alu, alu.c.id == mat.c.aluno_id))
        .where(pag.c.status == "atrasado").group_by(alu.c.id).order_by(func.sum(pag.c.valor).desc()).limit(30)).all()]

    ultimo = select(chk.c.aluno_id, func.max(chk.c.data_hora).label("ultimo")).group_by(chk.c.aluno_id).subquery()
    sumidos = []
    for a, n, nm, ult in db.execute(
            select(alu.c.id, alu.c.nome, alu.c.numero_matricula, ultimo.c.ultimo)
            .select_from(alu.join(mat, mat.c.aluno_id == alu.c.id).outerjoin(ultimo, ultimo.c.aluno_id == alu.c.id))
            .where(_vigente(mat, dia), or_(ultimo.c.ultimo.is_(None), ultimo.c.ultimo < func.now() - timedelta(days=14)))
            .order_by(ultimo.c.ultimo.asc().nulls_first()).limit(30)).all():
        sumidos.append({"aluno_id": a, "aluno": n, "numero_matricula": nm, "ultimo_checkin": utc(ult),
                        "dias": (dia - ult.date()).days if ult else None})

    data_prev = db.scalar(select(func.max(prev.c.data_previsao)))
    evasao = []
    if data_prev:
        evasao = [{"aluno_id": a, "aluno": n, "numero_matricula": nm, "probabilidade": round(float(p) * 100)}
                  for a, n, nm, p in db.execute(
                select(alu.c.id, alu.c.nome, alu.c.numero_matricula, prev.c.probabilidade)
                .select_from(prev.join(alu, alu.c.id == prev.c.aluno_id))
                .where(prev.c.data_previsao == data_prev).order_by(prev.c.probabilidade.desc()).limit(20)).all()]

    return jsonable_encoder({
        "mensal": mensal, "situacao_matriculas": situacao, "por_plano": por_plano, "frequencia": frequencia,
        "inadimplentes": inadimplentes, "sumidos": sumidos,
        "evasao": {"data": data_prev, "alunos": evasao},
    })


@router.post("/evasao")
def calcular_evasao(db: Session = Depends(get_db)):
    """Roda a rede de evasão (ai/churn.py) para cada aluno com plano vigente e grava em previsoes_evasao."""
    from ..ai import churn

    pag, mat, planos, chk, prev = (tabela(t) for t in ("pagamentos", "matriculas", "planos", "checkins",
                                                       "previsoes_evasao"))
    dia = hoje()
    vigentes = db.execute(
        select(mat.c.aluno_id, planos.c.valor, planos.c.duracao_dias).select_from(mat.join(planos, planos.c.id == mat.c.plano_id))
        .where(_vigente(mat, dia))).all()
    if not vigentes:
        return {"mensagem": "Nenhum aluno com plano vigente para analisar.", "alunos": 0}
    ids = [v.aluno_id for v in vigentes]
    agora = func.now()
    c30 = dict(db.execute(select(chk.c.aluno_id, func.count()).where(
        chk.c.aluno_id.in_(ids), chk.c.data_hora >= agora - timedelta(days=30)).group_by(chk.c.aluno_id)).all())
    cprev = dict(db.execute(select(chk.c.aluno_id, func.count()).where(
        chk.c.aluno_id.in_(ids), chk.c.data_hora < agora - timedelta(days=30),
        chk.c.data_hora >= agora - timedelta(days=60)).group_by(chk.c.aluno_id)).all())
    ultimo = dict(db.execute(select(chk.c.aluno_id, func.max(dia_local(chk.c.data_hora)))
                             .where(chk.c.aluno_id.in_(ids)).group_by(chk.c.aluno_id)).all())
    atrasos = dict(db.execute(select(mat.c.aluno_id, func.count())
                              .select_from(pag.join(mat, mat.c.id == pag.c.matricula_id))
                              .where(mat.c.aluno_id.in_(ids), pag.c.status.in_(EM_ABERTO), pag.c.data_vencimento < dia)
                              .group_by(mat.c.aluno_id)).all())
    inicio = dict(db.execute(select(mat.c.aluno_id, func.min(mat.c.data_inicio))
                             .where(mat.c.aluno_id.in_(ids)).group_by(mat.c.aluno_id)).all())

    # mesmas entradas do treino: [frequência 30d, frequência 30-60d, dias sem treinar, atrasos, meses de casa,
    # valor mensal]. As frequências são check-ins "por 30 dias" proporcionais ao tempo de casa, para quem
    # entrou há poucos dias não ser comparado com um mês inteiro.
    linhas = []
    for a, valor, duracao in vigentes:
        casa = max((dia - inicio[a]).days, 0)
        janela = min(max(casa, 7), 30)  # mínimo de 7 dias: evita extrapolar 1 treino em 1 dia para 30/mês
        freq = min(c30.get(a, 0) * 30 / janela, 30)
        janela_ant = min(max(casa - 30, 0), 30)
        # sem pelo menos uma semana de período anterior, repete a frequência atual (tendência neutra)
        freq_ant = min(cprev.get(a, 0) * 30 / janela_ant, 30) if janela_ant >= 7 else freq
        sem_treinar = min((dia - ultimo[a]).days if a in ultimo else casa, 30)
        mensal = float(valor) * 30 / (duracao or 30)  # trimestral/anual convertidos para valor por mês
        linhas.append([freq, freq_ant, sem_treinar, min(atrasos.get(a, 0), 4), max(1, min(casa // 30 + 1, 24)),
                       mensal])
    probs = churn.prever(linhas)

    stmt = pg_insert(prev).values([{"aluno_id": a, "data_previsao": dia, "probabilidade": round(p, 4),
                                    "modelo_versao": MODELO_VERSAO} for (a, _, _), p in zip(vigentes, probs)])
    db.execute(stmt.on_conflict_do_update(
        index_elements=[prev.c.aluno_id, prev.c.data_previsao],
        set_={"probabilidade": stmt.excluded.probabilidade, "modelo_versao": stmt.excluded.modelo_versao}))
    db.commit()
    risco = sum(p >= 0.55 for p in probs)
    return {"mensagem": f"Risco calculado para {len(probs)} aluno(s) em {churn.dispositivo()}; {risco} com risco alto.",
            "alunos": len(probs)}
