import math

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import limite
from ..database import get_db
from ..deps import usuario_atual
from ..models import Usuario
from ..perfis import normalizar_perfil
from ..schemas import CadastroAlunoIn, CadastroEquipeIn, LoginIn, TokenOut, UsuarioOut
from ..security import criar_token, verificar_senha
from ..services.academia import criar_matricula, exige_plano_ativo, matricula_vigente, planos_ativos
from ..services.alunos import aluno_do_usuario, ficha_para_cadastro
from ..services.usuarios import criar_usuario

router = APIRouter(prefix="/auth", tags=["auth"])


def _out(u: Usuario) -> UsuarioOut:
    return UsuarioOut(id=u.id, nome=u.nome, email=u.email, perfil=normalizar_perfil(u.perfil))


def _token(u: Usuario) -> TokenOut:
    out = _out(u)
    return TokenOut(access_token=criar_token(u.id, out.perfil), usuario=out)


@router.post("/login", response_model=TokenOut)  # RF01
def login(dados: LoginIn, request: Request, db: Session = Depends(get_db)):
    email, ip = dados.email.lower(), request.client.host if request.client else "?"
    espera = limite.segundos_bloqueado(email, ip)
    if espera:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Muitas tentativas de login. Tente de novo em {math.ceil(espera / 60)} minuto(s).",
                            headers={"Retry-After": str(espera)})
    u = db.scalar(select(Usuario).where(func.lower(Usuario.email) == email))
    if not u or not verificar_senha(dados.senha, u.senha_hash):
        limite.registrar_falha(email, ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")
    limite.registrar_sucesso(email)
    if not u.ativo:  # só informa depois da senha certa
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Sua conta está inativa ou aguardando aprovação do administrador.")
    eh_aluno = normalizar_perfil(u.perfil) == "aluno"
    if dados.acesso == "equipe" and eh_aluno:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta conta é de aluno. Use a aba “Aluno” para entrar.")
    if dados.acesso == "aluno" and not eh_aluno:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta conta é da equipe. Use a aba “Equipe” para entrar.")
    return _token(u)


@router.get("/planos")
def planos_publicos(db: Session = Depends(get_db)):
    """Planos à venda, para a tela pública de criar conta."""
    return jsonable_encoder(planos_ativos(db))


@router.post("/cadastro", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def cadastro(dados: CadastroAlunoIn, db: Session = Depends(get_db)):
    """Cadastro público: sempre cria perfil 'aluno', já matriculado no plano escolhido.
    Outros perfis só o administrador cria (/usuarios)."""
    exige_plano_ativo(db, dados.plano_id)  # valida antes de criar a conta
    ficha_id = ficha_para_cadastro(db, dados.email, dados.cpf)  # liga à ficha da recepção só se e-mail E CPF baterem
    # conta, ficha e matrícula na MESMA transação: ou grava tudo, ou nada (sem conta "pela metade")
    try:
        u = criar_usuario(db, dados.nome, dados.email, dados.senha, "aluno", ficha_id=ficha_id, cpf=dados.cpf,
                          commit=False)
        aluno = aluno_do_usuario(db, u)
        if not matricula_vigente(db, aluno["id"]):  # ficha da recepção pode já ter plano ativo
            criar_matricula(db, aluno["id"], dados.plano_id, commit=False)
        db.commit()
    except IntegrityError:  # corrida com outro cadastro do mesmo CPF/e-mail
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um cadastro com este e-mail ou CPF.")
    return _token(u)


@router.post("/cadastro-equipe", status_code=status.HTTP_201_CREATED)
def cadastro_equipe(dados: CadastroEquipeIn, db: Session = Depends(get_db)):
    """Pedido de acesso da equipe (recepção/instrutor). A conta nasce inativa e só entra
    depois que um administrador aprovar em /usuarios."""
    criar_usuario(db, dados.nome, dados.email, dados.senha, dados.perfil, ativo=False)
    return {"mensagem": "Cadastro enviado. Você poderá entrar assim que um administrador aprovar."}


@router.get("/me", response_model=UsuarioOut)
def me(u: Usuario = Depends(usuario_atual)):
    return _out(u)
