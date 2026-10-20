"""Área do aluno. RN04: o aluno só enxerga os próprios dados (tudo parte do usuário logado)."""
# pyright: reportMissingImports=false
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import exige_perfis
from ..models import Usuario
from ..reflexao import tabela
from ..schemas import AssinarPlanoIn, DadosAlunoIn, PagarIn, SessaoIn
from ..services.academia import (FORMAS, checkin_aberto, criar_matricula, informar_pagamento, planos_ativos,
                                 registrar_entrada, registrar_saida, salvar_aluno, utc)
from ..services.alunos import aluno_do_usuario
from ..services.registros import evolucao_do_aluno, excluir_sessao, registrar_sessao, sessoes_do_aluno

router = APIRouter(prefix="/meu", tags=["area do aluno"])
so_aluno = exige_perfis("aluno")

CAMPOS_ALUNO = ("cpf", "data_nascimento", "sexo", "telefone", "altura_cm", "peso_kg")


def _perfil(aluno: dict | None) -> dict:
    """Dados que o aluno pode editar, como estão no banco."""
    return {k: (aluno or {}).get(k) for k in CAMPOS_ALUNO}


def _matricula(db: Session, aluno_id):
    """Matrícula mais recente, com o plano."""
    mat, planos = tabela("matriculas"), tabela("planos")
    linha = db.execute(
        select(planos.c.nome.label("plano"), planos.c.valor, mat.c.data_inicio.label("inicio"),
               mat.c.data_fim.label("fim"), mat.c.status)
        .select_from(mat.join(planos, planos.c.id == mat.c.plano_id))
        .where(mat.c.aluno_id == aluno_id).order_by(mat.c.data_inicio.desc(), mat.c.id.desc()).limit(1)).first()
    return {**dict(linha._mapping), "status": str(linha.status)} if linha else None


def _pagamentos(db: Session, aluno_id):
    pag, mat = tabela("pagamentos"), tabela("matriculas")
    linhas = db.execute(
        select(pag).select_from(pag.join(mat, mat.c.id == pag.c.matricula_id))
        .where(mat.c.aluno_id == aluno_id).order_by(pag.c.data_vencimento.desc(), pag.c.id.desc()).limit(12)).all()
    return [{"id": l.id, "valor": l.valor, "forma": l.forma_pagamento, "vencimento": l.data_vencimento,
             "pago_em": l.data_pagamento, "informado_em": utc(l.informado_em), "informado_forma": l.informado_forma,
             "status": str(l.status)} for l in linhas]


def _checkins(db: Session, aluno_id):
    chk = tabela("checkins")
    total = db.scalar(select(func.count()).select_from(chk).where(
        chk.c.aluno_id == aluno_id, chk.c.data_hora >= func.now() - timedelta(days=30))) or 0
    recentes = db.scalars(select(chk.c.data_hora).where(chk.c.aluno_id == aluno_id)
                          .order_by(chk.c.data_hora.desc()).limit(10)).all()
    return {"ultimos_30_dias": total, "recentes": [utc(r) for r in recentes]}


@router.get("/resumo")
def resumo(db: Session = Depends(get_db), usuario: Usuario = Depends(so_aluno)):
    base = {"usuario": {"nome": usuario.nome, "email": usuario.email}, "vinculado": False,
            "numero_matricula": None, "perfil": _perfil(None), "matricula": None, "pagamentos": [],
            "checkins": {"ultimos_30_dias": 0, "recentes": []}}
    aluno = aluno_do_usuario(db, usuario)
    if aluno is None:  # conta ainda sem ficha: o aluno cria em "Meus dados"
        return jsonable_encoder(base)
    return jsonable_encoder({**base, "vinculado": True, "perfil": _perfil(aluno),
                             "numero_matricula": aluno["numero_matricula"],
                             "matricula": _matricula(db, aluno["id"]), "pagamentos": _pagamentos(db, aluno["id"]),
                             "checkins": _checkins(db, aluno["id"])})


def _treinos(db: Session, aluno_id):
    """Fichas ativas (as arquivadas pelo instrutor não aparecem), com os exercícios em ordem."""
    tr, it, ex = tabela("treinos"), tabela("treino_itens"), tabela("exercicios")
    treinos = db.execute(select(tr.c.id, tr.c.nome, tr.c.objetivo).where(tr.c.aluno_id == aluno_id, tr.c.ativo.is_(True))
                         .order_by(tr.c.id.desc()).limit(10)).all()
    itens: dict = {}
    if treinos:
        for l in db.execute(select(it, ex.c.nome.label("exercicio"))
                            .select_from(it.join(ex, ex.c.id == it.c.exercicio_id))
                            .where(it.c.treino_id.in_([t.id for t in treinos])).order_by(it.c.treino_id, it.c.ordem)).all():
            itens.setdefault(l.treino_id, []).append(
                {"exercicio_id": l.exercicio_id, "exercicio": l.exercicio, "series": l.series,
                 "repeticoes": l.repeticoes, "carga": l.carga_kg, "descanso": l.descanso_seg})
    return [{"id": t.id, "nome": t.nome, "objetivo": t.objetivo, "itens": itens.get(t.id, [])} for t in treinos]


@router.get("/treinos")
def meus_treinos(db: Session = Depends(get_db), usuario: Usuario = Depends(so_aluno)):
    aluno = aluno_do_usuario(db, usuario)
    if aluno is None:
        return {"vinculado": False, "treinos": []}
    return jsonable_encoder({"vinculado": True, "treinos": _treinos(db, aluno["id"])})


# ---- Evolução: o aluno registra o que fez e acompanha o próprio progresso ----

@router.get("/sessoes")
def minhas_sessoes(db: Session = Depends(get_db), usuario: Usuario = Depends(so_aluno)):
    return jsonable_encoder(sessoes_do_aluno(db, _aluno(db, usuario)["id"]))


@router.get("/evolucao")
def minha_evolucao(db: Session = Depends(get_db), usuario: Usuario = Depends(so_aluno)):
    return jsonable_encoder(evolucao_do_aluno(db, _aluno(db, usuario)["id"]))


@router.post("/treinos/{treino_id}/sessoes", status_code=status.HTTP_201_CREATED)
def registrar_meu_treino(treino_id: int, dados: SessaoIn, db: Session = Depends(get_db),
                         usuario: Usuario = Depends(so_aluno)):
    aluno_id = _aluno(db, usuario)["id"]
    registrar_sessao(db, treino_id, dados, usuario.id, aluno_id=aluno_id)
    return jsonable_encoder(sessoes_do_aluno(db, aluno_id))


@router.delete("/sessoes/{sessao_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_minha_sessao(sessao_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(so_aluno)):
    excluir_sessao(db, sessao_id, aluno_id=_aluno(db, usuario)["id"])

# ---- Ações do aluno: editar dados, check-in/check-out e informar pagamentos ----

def _aluno(db: Session, usuario: Usuario) -> dict:
    aluno = aluno_do_usuario(db, usuario)
    if aluno is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Salve seus dados em “Meus dados” para liberar esta função.")
    return aluno


@router.put("/dados")
def salvar_dados(dados: DadosAlunoIn, db: Session = Depends(get_db), usuario: Usuario = Depends(so_aluno)):
    aluno = aluno_do_usuario(db, usuario)
    if aluno is None:  # conta sem cadastro de aluno: cria agora
        salvar_aluno(db, {"nome": usuario.nome, "email": usuario.email, "usuario_id": usuario.id, **dados.model_dump()})
    else:
        salvar_aluno(db, dados.model_dump(), aluno["id"])
    return jsonable_encoder(_perfil(aluno_do_usuario(db, usuario)))


def _registro(m) -> dict:
    return {"id": m["id"], "entrada": utc(m["data_hora"]), "saida": utc(m["data_saida"])}


@router.get("/checkins")
def meus_checkins(db: Session = Depends(get_db), usuario: Usuario = Depends(so_aluno)):
    aluno = _aluno(db, usuario)
    chk = tabela("checkins")
    aberto = checkin_aberto(db, aluno["id"])
    linhas = db.execute(select(chk).where(chk.c.aluno_id == aluno["id"])
                        .order_by(chk.c.data_hora.desc()).limit(15)).all()
    return jsonable_encoder({"aberto": _registro(aberto._mapping) if aberto else None,
                             "recentes": [_registro(l._mapping) for l in linhas]})


@router.post("/checkin", status_code=status.HTTP_201_CREATED)
def fazer_checkin(db: Session = Depends(get_db), usuario: Usuario = Depends(so_aluno)):
    """Pelo app: precisa ter plano ativo e estar sem mensalidade em atraso."""
    registrar_entrada(db, _aluno(db, usuario)["id"], pelo_app=True)
    return meus_checkins(db, usuario)


@router.post("/checkout")
def fazer_checkout(db: Session = Depends(get_db), usuario: Usuario = Depends(so_aluno)):
    registrar_saida(db, _aluno(db, usuario)["id"])
    return meus_checkins(db, usuario)


@router.get("/planos")
def planos_disponiveis(db: Session = Depends(get_db), _=Depends(so_aluno)):
    return jsonable_encoder(planos_ativos(db))


@router.post("/matricula", status_code=status.HTTP_201_CREATED)
def assinar_plano(dados: AssinarPlanoIn, db: Session = Depends(get_db), usuario: Usuario = Depends(so_aluno)):
    nome = criar_matricula(db, _aluno(db, usuario)["id"], dados.plano_id)
    return {"mensagem": f"Plano {nome} contratado. Pague a primeira mensalidade para concluir."}


@router.post("/pagamentos/{pagamento_id}/informar")
def informar(pagamento_id: int, dados: PagarIn, db: Session = Depends(get_db), usuario: Usuario = Depends(so_aluno)):
    """O aluno avisa que pagou. Só a recepção dá a baixa (não há gateway de pagamento integrado)."""
    informar_pagamento(db, pagamento_id, dados.forma, _aluno(db, usuario)["id"])
    return {"mensagem": f"Pagamento via {FORMAS[dados.forma]} informado. A recepção vai confirmar o recebimento."}
