"""Tela "Treinos" da equipe: catálogo de exercícios e fichas de treino por aluno (administrador e instrutor)."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import exige_perfis
from ..models import Usuario
from ..reflexao import tabela
from ..schemas import AtivoIn, ExercicioIn, SessaoIn, TreinoIn
from ..services.academia import exige_aluno, utc
from ..services.registros import evolucao_do_aluno, excluir_sessao, registrar_sessao, sessoes_do_aluno

router = APIRouter(tags=["treinos"])
instrutores = exige_perfis("administrador", "instrutor")


# ---- exercícios ----

@router.get("/exercicios")
def listar_exercicios(db: Session = Depends(get_db), _=Depends(instrutores)):
    ex = tabela("exercicios")
    return jsonable_encoder([dict(l._mapping) for l in db.execute(select(ex).order_by(ex.c.grupo_muscular, ex.c.nome)).all()])


def _salvar_exercicio(db: Session, dados: ExercicioIn, exercicio_id=None):
    ex = tabela("exercicios")
    valores = {"nome": dados.nome.strip(), "grupo_muscular": (dados.grupo_muscular or "").strip() or None,
               "descricao": (dados.descricao or "").strip() or None}
    try:
        if exercicio_id is None:
            exercicio_id = db.execute(insert(ex).values(**valores).returning(ex.c.id)).scalar_one()
        elif db.execute(update(ex).where(ex.c.id == exercicio_id).values(**valores)).rowcount == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercício não encontrado.")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um exercício com este nome.")
    return jsonable_encoder(dict(db.execute(select(ex).where(ex.c.id == exercicio_id)).first()._mapping))


@router.post("/exercicios", status_code=status.HTTP_201_CREATED)
def criar_exercicio(dados: ExercicioIn, db: Session = Depends(get_db), _=Depends(instrutores)):
    return _salvar_exercicio(db, dados)


@router.put("/exercicios/{exercicio_id}")
def alterar_exercicio(exercicio_id: int, dados: ExercicioIn, db: Session = Depends(get_db), _=Depends(instrutores)):
    return _salvar_exercicio(db, dados, exercicio_id)


# ---- fichas de treino ----

def _fichas(db: Session, aluno_id) -> list:
    tr, it, ex = tabela("treinos"), tabela("treino_itens"), tabela("exercicios")
    usu = Usuario.__table__
    treinos = db.execute(
        select(tr, usu.c.nome.label("instrutor")).select_from(tr.outerjoin(usu, usu.c.id == tr.c.instrutor_id))
        .where(tr.c.aluno_id == aluno_id).order_by(tr.c.ativo.desc(), tr.c.criado_em.desc())
    ).all()
    ids = [t.id for t in treinos]
    itens: dict = {}
    if ids:
        for l in db.execute(select(it, ex.c.nome.label("exercicio"), ex.c.grupo_muscular)
                            .select_from(it.join(ex, ex.c.id == it.c.exercicio_id))
                            .where(it.c.treino_id.in_(ids)).order_by(it.c.treino_id, it.c.ordem)).all():
            m = l._mapping
            itens.setdefault(m["treino_id"], []).append(
                {k: m[k] for k in ("exercicio_id", "exercicio", "grupo_muscular", "ordem", "series", "repeticoes",
                                   "carga_kg", "descanso_seg")})
    return [{"id": t.id, "nome": t.nome, "objetivo": t.objetivo, "ativo": t.ativo, "instrutor": t.instrutor,
             "criado_em": utc(t.criado_em), "itens": itens.get(t.id, [])} for t in treinos]


@router.get("/treinos")
def listar_treinos(aluno_id: int, db: Session = Depends(get_db), _=Depends(instrutores)):
    exige_aluno(db, aluno_id)
    return jsonable_encoder(_fichas(db, aluno_id))


def _gravar_itens(db: Session, treino_id, dados: TreinoIn):
    ex, it = tabela("exercicios"), tabela("treino_itens")
    pedidos = {i.exercicio_id for i in dados.itens}
    existentes = set(db.scalars(select(ex.c.id).where(ex.c.id.in_(pedidos))).all())
    if pedidos - existentes:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercício não encontrado.")
    db.execute(delete(it).where(it.c.treino_id == treino_id))
    db.execute(insert(it), [{**i.model_dump(), "treino_id": treino_id, "ordem": n}
                            for n, i in enumerate(dados.itens, start=1)])


@router.post("/treinos", status_code=status.HTTP_201_CREATED)
def criar_treino(dados: TreinoIn, db: Session = Depends(get_db), usuario: Usuario = Depends(instrutores)):
    exige_aluno(db, dados.aluno_id)
    tr = tabela("treinos")
    treino_id = db.execute(insert(tr).values(
        aluno_id=dados.aluno_id, instrutor_id=usuario.id, nome=dados.nome.strip(),
        objetivo=(dados.objetivo or "").strip() or None, ativo=True,
    ).returning(tr.c.id)).scalar_one()
    _gravar_itens(db, treino_id, dados)
    db.commit()
    return jsonable_encoder(_fichas(db, dados.aluno_id))


@router.put("/treinos/{treino_id}")
def alterar_treino(treino_id: int, dados: TreinoIn, db: Session = Depends(get_db), _=Depends(instrutores)):
    tr = tabela("treinos")
    atual = db.execute(select(tr.c.aluno_id).where(tr.c.id == treino_id)).first()
    if not atual or atual.aluno_id != dados.aluno_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Treino não encontrado.")
    db.execute(update(tr).where(tr.c.id == treino_id).values(
        nome=dados.nome.strip(), objetivo=(dados.objetivo or "").strip() or None))
    _gravar_itens(db, treino_id, dados)
    db.commit()
    return jsonable_encoder(_fichas(db, dados.aluno_id))


@router.patch("/treinos/{treino_id}")
def arquivar_treino(treino_id: int, dados: AtivoIn, db: Session = Depends(get_db), _=Depends(instrutores)):
    """ativo=false arquiva (o aluno deixa de ver); true reativa."""
    tr = tabela("treinos")
    linha = db.execute(update(tr).where(tr.c.id == treino_id).values(ativo=dados.ativo).returning(tr.c.aluno_id)).first()
    if not linha:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Treino não encontrado.")
    db.commit()
    return jsonable_encoder(_fichas(db, linha.aluno_id))


# ---- evolução: registros de execução (o que o aluno fez e quanto fez) ----

@router.get("/sessoes")
def listar_sessoes(aluno_id: int, db: Session = Depends(get_db), _=Depends(instrutores)):
    exige_aluno(db, aluno_id)
    return jsonable_encoder(sessoes_do_aluno(db, aluno_id))


@router.get("/evolucao")
def ver_evolucao(aluno_id: int, db: Session = Depends(get_db), _=Depends(instrutores)):
    exige_aluno(db, aluno_id)
    return jsonable_encoder(evolucao_do_aluno(db, aluno_id))


@router.post("/treinos/{treino_id}/sessoes", status_code=status.HTTP_201_CREATED)
def registrar_execucao(treino_id: int, dados: SessaoIn, db: Session = Depends(get_db),
                       usuario: Usuario = Depends(instrutores)):
    registrar_sessao(db, treino_id, dados, usuario.id)
    tr = tabela("treinos")
    aluno_id = db.execute(select(tr.c.aluno_id).where(tr.c.id == treino_id)).scalar_one()
    return jsonable_encoder(sessoes_do_aluno(db, aluno_id))


@router.delete("/sessoes/{sessao_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_sessao(sessao_id: int, db: Session = Depends(get_db), _=Depends(instrutores)):
    excluir_sessao(db, sessao_id)
