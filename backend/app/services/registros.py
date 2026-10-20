"""Registros de execução de treino (o que o aluno fez e quanto fez) e evolução por exercício.
Usado pela área do aluno (/meu) e pela tela "Treinos" da equipe."""
from fastapi import HTTPException, status
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from ..reflexao import tabela
from .academia import utc


def _treino_do_aluno(db: Session, treino_id, aluno_id=None):
    """Confere que o treino existe (e, quando aluno_id é dado, que é dele). Devolve o aluno_id do treino."""
    tr = tabela("treinos")
    linha = db.execute(select(tr.c.id, tr.c.aluno_id).where(tr.c.id == treino_id)).first()
    if not linha or (aluno_id is not None and linha.aluno_id != aluno_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Treino não encontrado.")
    return linha.aluno_id


def registrar_sessao(db: Session, treino_id, dados, usuario_id, aluno_id=None) -> int:
    aluno_id = _treino_do_aluno(db, treino_id, aluno_id)
    ses, item, ex = tabela("treino_sessoes"), tabela("treino_sessao_itens"), tabela("exercicios")
    pedidos = {i.exercicio_id for i in dados.itens}
    existentes = set(db.scalars(select(ex.c.id).where(ex.c.id.in_(pedidos))).all())
    if pedidos - existentes:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercício não encontrado.")
    valores = {"treino_id": treino_id, "aluno_id": aluno_id, "registrado_por": usuario_id,
               "observacao": (dados.observacao or "").strip() or None}
    if dados.data is not None:
        valores["data_hora"] = dados.data
    sessao_id = db.execute(insert(ses).values(**valores).returning(ses.c.id)).scalar_one()
    db.execute(insert(item), [{"sessao_id": sessao_id, "exercicio_id": i.exercicio_id, "ordem": n,
                               "series": i.series, "repeticoes": i.repeticoes, "carga_kg": i.carga_kg}
                              for n, i in enumerate(dados.itens, start=1)])
    db.commit()
    return sessao_id


def sessoes_do_aluno(db: Session, aluno_id, limit: int = 30) -> list:
    """Histórico recente de sessões executadas, com os itens de cada uma."""
    ses, item, ex, tr = (tabela("treino_sessoes"), tabela("treino_sessao_itens"),
                         tabela("exercicios"), tabela("treinos"))
    sessoes = db.execute(
        select(ses, tr.c.nome.label("treino")).select_from(ses.outerjoin(tr, tr.c.id == ses.c.treino_id))
        .where(ses.c.aluno_id == aluno_id).order_by(ses.c.data_hora.desc()).limit(limit)
    ).all()
    ids = [s.id for s in sessoes]
    itens: dict = {}
    if ids:
        for l in db.execute(select(item, ex.c.nome.label("exercicio"), ex.c.grupo_muscular)
                            .select_from(item.join(ex, ex.c.id == item.c.exercicio_id))
                            .where(item.c.sessao_id.in_(ids)).order_by(item.c.sessao_id, item.c.ordem)).all():
            m = l._mapping
            itens.setdefault(m["sessao_id"], []).append(
                {k: m[k] for k in ("exercicio_id", "exercicio", "grupo_muscular", "series", "repeticoes", "carga_kg")})
    return [{"id": s.id, "treino_id": s.treino_id, "treino": s.treino, "data": utc(s.data_hora),
             "observacao": s.observacao, "itens": itens.get(s.id, [])} for s in sessoes]


def evolucao_do_aluno(db: Session, aluno_id) -> list:
    """Para cada exercício que o aluno já registrou, a série de pontos no tempo (carga e volume)."""
    ses, item, ex = tabela("treino_sessoes"), tabela("treino_sessao_itens"), tabela("exercicios")
    linhas = db.execute(
        select(ses.c.id, ses.c.data_hora, item.c.exercicio_id, ex.c.nome.label("exercicio"), ex.c.grupo_muscular,
               item.c.series, item.c.repeticoes, item.c.carga_kg)
        .select_from(item.join(ses, ses.c.id == item.c.sessao_id).join(ex, ex.c.id == item.c.exercicio_id))
        .where(ses.c.aluno_id == aluno_id).order_by(item.c.exercicio_id, ses.c.data_hora)
    ).all()
    grupos: dict = {}
    for l in linhas:
        g = grupos.setdefault(l.exercicio_id, {"exercicio_id": l.exercicio_id, "exercicio": l.exercicio,
                                               "grupo_muscular": l.grupo_muscular, "pontos": []})
        carga = float(l.carga_kg) if l.carga_kg is not None else None
        volume = (l.series * l.repeticoes * carga) if (carga is not None and l.series and l.repeticoes) else None
        g["pontos"].append({"sessao_id": l.id, "data": utc(l.data_hora), "series": l.series,
                            "repeticoes": l.repeticoes, "carga_kg": carga, "volume": volume})
    return list(grupos.values())


def excluir_sessao(db: Session, sessao_id, aluno_id=None) -> None:
    ses = tabela("treino_sessoes")
    cond = [ses.c.id == sessao_id]
    if aluno_id is not None:  # o aluno só apaga as próprias sessões
        cond.append(ses.c.aluno_id == aluno_id)
    if db.execute(delete(ses).where(*cond)).rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registro não encontrado.")
    db.commit()
