"""Tela "Análise de postura": upload do vídeo, análise com IA no servidor e histórico (administrador e instrutor).

A análise roda numa fila em segundo plano (uma por vez): o upload responde na hora com status "processando"
e a tela consulta GET /postura/{id} até virar "concluida" ou "erro". Assim um vídeo não trava a API."""
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..deps import exige_perfis
from ..reflexao import tabela
from ..services.academia import exige_aluno, utc

log = logging.getLogger("unifit")
router = APIRouter(prefix="/postura", tags=["análise de postura"],
                   dependencies=[Depends(exige_perfis("administrador", "instrutor"))])
EXTENSOES = {".mp4", ".mov", ".avi", ".webm", ".mkv", ".m4v"}
MAX_BYTES = 100 * 1024 * 1024
fila = ThreadPoolExecutor(max_workers=1, thread_name_prefix="postura")  # 1 por vez: a IA usa a CPU/GPU inteira


def _exercicio(db: Session, exercicio_id) -> dict:
    ex = tabela("exercicios")
    linha = db.execute(select(ex).where(ex.c.id == exercicio_id)).first()
    if not linha:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercício não encontrado.")
    return dict(linha._mapping)


def _processar(sessao_id: int, caminho: str, exercicio: str, grupo: str | None) -> None:
    """Executa na fila: roda a IA e grava o resultado (ou o erro) na linha da sessão."""
    sp = tabela("sessoes_postura")
    try:
        from ..ai import postura  # importa o torchvision só quando a fila é usada

        analise = postura.analisar(caminho, exercicio, grupo)
        valores = {"status": "concluida", "erro": None, "fps_original": analise["fps_original"],
                   "fps_processado": analise["fps_processado"], "duracao_seg": analise["duracao_seg"],
                   "resultado": analise["resultado"]}
    except ValueError as erro:  # vídeo ilegível etc.: mensagem pensada para o usuário
        valores = {"status": "erro", "erro": str(erro)}
    except Exception:
        log.exception("postura: falha na análise da sessão %s", sessao_id)
        valores = {"status": "erro", "erro": "Falha inesperada na análise. Tente de novo com outro vídeo."}
    finally:
        os.unlink(caminho)
    with SessionLocal() as db:
        db.execute(update(sp).where(sp.c.id == sessao_id).values(**valores))
        db.commit()


def marcar_interrompidas() -> None:
    """Ao subir a API: análises que estavam na fila quando o servidor parou não vão mais terminar."""
    sp = tabela("sessoes_postura")
    with SessionLocal() as db:
        db.execute(update(sp).where(sp.c.status == "processando").values(
            status="erro", erro="O servidor reiniciou durante a análise. Envie o vídeo de novo."))
        db.commit()


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def analisar(aluno_id: int = Form(...), exercicio_id: int = Form(...), video: UploadFile = File(...),
             db: Session = Depends(get_db)):
    exige_aluno(db, aluno_id)
    ex = _exercicio(db, exercicio_id)
    extensao = os.path.splitext(video.filename or "")[1].lower()
    if extensao not in EXTENSOES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Envie um vídeo MP4, MOV, AVI, WEBM ou MKV.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=extensao) as tmp:
        tamanho = 0
        while bloco := video.file.read(1024 * 1024):  # copia em blocos e para no limite, sem encher o disco
            tamanho += len(bloco)
            if tamanho > MAX_BYTES:
                break
            tmp.write(bloco)
    if tamanho > MAX_BYTES:
        os.unlink(tmp.name)
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Vídeo maior que 100 MB. Envie um trecho menor.")

    sp = tabela("sessoes_postura")
    try:
        sessao_id = db.execute(insert(sp).values(
            aluno_id=aluno_id, exercicio_id=exercicio_id, video_nome=(video.filename or "video")[:255],
            status="processando").returning(sp.c.id)).scalar_one()
        db.commit()
    except Exception:
        os.unlink(tmp.name)
        raise
    fila.submit(_processar, sessao_id, tmp.name, ex["nome"], ex.get("grupo_muscular"))
    return detalhe(sessao_id, db)


@router.get("")
def historico(aluno_id: int, db: Session = Depends(get_db)):
    sp, ex = tabela("sessoes_postura"), tabela("exercicios")
    linhas = db.execute(
        select(sp.c.id, sp.c.criado_em, sp.c.video_nome, sp.c.duracao_seg, sp.c.fps_processado, sp.c.status,
               ex.c.nome.label("exercicio"), sp.c.resultado["repeticoes"].astext.label("repeticoes"),
               sp.c.resultado["alertas"].label("alertas"))
        .select_from(sp.join(ex, ex.c.id == sp.c.exercicio_id))
        .where(sp.c.aluno_id == aluno_id).order_by(sp.c.criado_em.desc()).limit(50)
    ).all()
    return jsonable_encoder([{**dict(l._mapping), "criado_em": utc(l.criado_em),
                              "alertas": len(l.alertas or [])} for l in linhas])


@router.get("/{sessao_id}")
def detalhe(sessao_id: int, db: Session = Depends(get_db)):
    sp, ex, alu = tabela("sessoes_postura"), tabela("exercicios"), tabela("alunos")
    linha = db.execute(
        select(sp, ex.c.nome.label("exercicio"), alu.c.nome.label("aluno"))
        .select_from(sp.join(ex, ex.c.id == sp.c.exercicio_id).join(alu, alu.c.id == sp.c.aluno_id))
        .where(sp.c.id == sessao_id)
    ).first()
    if not linha:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Análise não encontrada.")
    return jsonable_encoder({**dict(linha._mapping), "criado_em": utc(linha.criado_em)})
