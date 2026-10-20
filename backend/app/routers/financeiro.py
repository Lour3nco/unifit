"""Tela "Financeiro": mensalidades de todos os alunos, baixa de pagamento e cancelamento."""
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import Date, cast, func, select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import exige_perfis
from ..reflexao import tabela
from ..schemas import BaixaIn
from ..services.academia import EM_ABERTO, FORMAS, hoje, quitar, recusar_informe, utc

router = APIRouter(prefix="/pagamentos", tags=["financeiro"],
                   dependencies=[Depends(exige_perfis("administrador", "recepcao"))])
SituacaoPagamento = Literal["", "pendente", "atrasado", "pago", "cancelado", "informado"]


@router.get("")
def listar(situacao: SituacaoPagamento = "", mes: str = "", busca: str = "", db: Session = Depends(get_db)):
    """mes no formato AAAA-MM filtra pelo vencimento. situacao=informado: o aluno disse que pagou e falta confirmar."""
    pag, mat, alu, planos = tabela("pagamentos"), tabela("matriculas"), tabela("alunos"), tabela("planos")
    base = pag.join(mat, mat.c.id == pag.c.matricula_id).join(alu, alu.c.id == mat.c.aluno_id)
    q = (select(pag.c.id, alu.c.id.label("aluno_id"), alu.c.nome.label("aluno"), planos.c.nome.label("plano"),
                pag.c.valor, pag.c.data_vencimento, pag.c.data_pagamento, pag.c.status, pag.c.forma_pagamento,
                pag.c.informado_em, pag.c.informado_forma)
         .select_from(base.join(planos, planos.c.id == mat.c.plano_id))
         .order_by(pag.c.data_vencimento.desc(), pag.c.id.desc()).limit(500))
    if situacao == "informado":
        q = q.where(pag.c.status.in_(EM_ABERTO), pag.c.informado_em.is_not(None))
    elif situacao:
        q = q.where(pag.c.status == situacao)
    if re.fullmatch(r"\d{4}-\d{2}", mes):
        q = q.where(func.to_char(pag.c.data_vencimento, "YYYY-MM") == mes)
    if busca.strip():
        q = q.where(alu.c.nome.ilike(f"%{busca.strip()}%"))
    linhas = [{**dict(l._mapping), "status": str(l.status), "informado_em": utc(l.informado_em)}
              for l in db.execute(q).all()]

    dia = hoje()
    soma = lambda *cond: float(db.scalar(select(func.coalesce(func.sum(pag.c.valor), 0)).where(*cond)) or 0)
    resumo = {
        "recebido_mes": soma(pag.c.status == "pago", cast(pag.c.data_pagamento, Date) >= dia.replace(day=1)),
        "a_receber": soma(pag.c.status == "pendente"),
        "em_atraso": soma(pag.c.status == "atrasado"),
        "qtd_atraso": db.scalar(select(func.count()).select_from(pag).where(pag.c.status == "atrasado")) or 0,
        "qtd_informados": db.scalar(select(func.count()).select_from(pag).where(
            pag.c.status.in_(EM_ABERTO), pag.c.informado_em.is_not(None))) or 0,
    }
    return jsonable_encoder({"resumo": resumo, "pagamentos": linhas})


@router.post("/{pagamento_id}/baixa")
def dar_baixa(pagamento_id: int, dados: BaixaIn, db: Session = Depends(get_db)):
    """Recebimento no balcão (exemplo: não há integração com banco ou maquininha)."""
    quitar(db, pagamento_id, dados.forma)
    return {"mensagem": f"Pagamento recebido via {FORMAS[dados.forma]}."}


@router.post("/{pagamento_id}/recusar-informe")
def recusar(pagamento_id: int, db: Session = Depends(get_db)):
    """O aluno informou o pagamento, mas ele não foi encontrado: a mensalidade volta a ser cobrança normal."""
    recusar_informe(db, pagamento_id)
    return {"mensagem": "Pagamento informado recusado. A mensalidade continua em aberto."}


@router.post("/{pagamento_id}/cancelar")
def cancelar(pagamento_id: int, db: Session = Depends(get_db)):
    pag = tabela("pagamentos")
    n = db.execute(update(pag).where(pag.c.id == pagamento_id, pag.c.status.in_(EM_ABERTO))
                   .values(status="cancelado")).rowcount
    if not n:
        raise HTTPException(status.HTTP_409_CONFLICT, "Só é possível cancelar mensalidades em aberto.")
    db.commit()
    return {"mensagem": "Mensalidade cancelada."}
