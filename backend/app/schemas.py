import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

PerfilNome = Literal["administrador", "recepcao", "instrutor", "aluno"]


class LoginIn(BaseModel):
    email: EmailStr
    senha: str
    acesso: Literal["aluno", "equipe"] | None = None  # aba da tela de login; None aceita qualquer perfil


class CadastroIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=72)


class CadastroAlunoIn(CadastroIn):
    plano_id: int  # todo aluno já entra matriculado em um plano
    cpf: str  # obrigatório: é o que permite ligar a conta à ficha da recepção com segurança

    @field_validator("cpf", mode="before")
    @classmethod
    def _cpf(cls, v):
        cpf = normalizar_cpf(v)
        if cpf is None:
            raise ValueError("Informe o CPF.")
        return cpf


class CadastroEquipeIn(CadastroIn):
    perfil: Literal["recepcao", "instrutor"]  # administrador não se cadastra pela tela pública


class UsuarioCriarIn(CadastroIn):
    perfil: PerfilNome


class UsuarioAlterarIn(BaseModel):
    perfil: PerfilNome | None = None
    ativo: bool | None = None


class UsuarioOut(BaseModel):
    id: int
    nome: str
    email: str
    perfil: str


class UsuarioListaOut(UsuarioOut):
    ativo: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class AlunoRisco(BaseModel):
    id: int
    nome: str
    probabilidade: int
    motivo: str


class CheckinDia(BaseModel):
    dia: str
    total: int


class DashboardOut(BaseModel):
    alunos_ativos: int
    receita_mes: float
    inadimplencia_pct: float
    pagamentos_atrasados: int
    checkins_hoje: int
    checkins_por_dia: list[CheckinDia]
    alunos_em_risco: list[AlunoRisco]
    dispositivo_ia: str
    benchmark_ativo: bool = False


def cpf_valido(cpf: str) -> bool:
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for n in (9, 10):  # os dois dígitos verificadores
        soma = sum(int(cpf[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10 % 11) % 10 != int(cpf[n]):
            return False
    return True


def normalizar_cpf(v):
    """Só dígitos; "" vira None; CPF com dígito verificador errado é recusado."""
    if v in (None, ""):
        return None
    cpf = re.sub(r"\D", "", str(v))
    if not cpf_valido(cpf):
        raise ValueError("CPF inválido.")
    return cpf


class DadosAlunoIn(BaseModel):
    """Dados que o próprio aluno preenche. Campo vazio/null apaga o valor."""
    cpf: str | None = None
    data_nascimento: date | None = None
    sexo: Literal["M", "F", "O"] | None = None
    telefone: str | None = Field(None, max_length=20)
    altura_cm: float | None = Field(None, ge=50, le=260)
    peso_kg: float | None = Field(None, ge=20, le=400)

    @field_validator("cpf", mode="before")
    @classmethod
    def _cpf(cls, v):
        return normalizar_cpf(v)

    @field_validator("telefone", mode="before")
    @classmethod
    def _telefone(cls, v):
        return (str(v).strip() or None) if v is not None else None

    @field_validator("data_nascimento")
    @classmethod
    def _nascimento(cls, v):
        if v is not None and not (date(1900, 1, 1) <= v <= date.today()):
            raise ValueError("Data de nascimento inválida.")
        return v


class AssinarPlanoIn(BaseModel):
    plano_id: int


class PagarIn(BaseModel):
    forma: Literal["pix", "cartao", "boleto"]


class AlunoIn(DadosAlunoIn):
    """Cadastro de aluno feito pela equipe."""
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr | None = None

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, v):
        return (str(v).strip().lower() or None) if v is not None else None


class PlanoIn(BaseModel):
    nome: str = Field(min_length=2, max_length=80)
    valor: float = Field(ge=0, le=99_999)
    duracao_dias: int = Field(gt=0, le=3650)
    ativo: bool = True


class MatriculaIn(BaseModel):
    aluno_id: int
    plano_id: int
    data_inicio: date | None = None


class MatriculaStatusIn(BaseModel):
    status: Literal["ativa", "trancada", "cancelada", "encerrada"]


class BaixaIn(BaseModel):
    forma: Literal["pix", "cartao", "boleto", "dinheiro"]


class AlunoIdIn(BaseModel):
    aluno_id: int


class AlunoNovoIn(AlunoIn):
    """Novo aluno pela equipe: já sai matriculado."""
    plano_id: int
    data_inicio: date | None = None


class ExercicioIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    grupo_muscular: str | None = Field(None, max_length=60)
    descricao: str | None = Field(None, max_length=2000)


class TreinoItemIn(BaseModel):
    exercicio_id: int
    series: int = Field(ge=1, le=20)
    repeticoes: int = Field(ge=1, le=200)
    carga_kg: float | None = Field(None, ge=0, le=1000)
    descanso_seg: int | None = Field(None, ge=0, le=900)


class TreinoIn(BaseModel):
    aluno_id: int
    nome: str = Field(min_length=2, max_length=80)
    objetivo: str | None = Field(None, max_length=120)
    itens: list[TreinoItemIn] = Field(min_length=1, max_length=30)


class AtivoIn(BaseModel):
    ativo: bool


class SessaoItemIn(BaseModel):
    """O que o aluno fez em um exercício da sessão (campos vazios = não registrado)."""
    exercicio_id: int
    series: int | None = Field(None, ge=0, le=50)
    repeticoes: int | None = Field(None, ge=0, le=500)
    carga_kg: float | None = Field(None, ge=0, le=1000)


class SessaoIn(BaseModel):
    """Registro de uma sessão executada (o que fez e quanto fez)."""
    treino_id: int
    data: date | None = None  # dia da execução; vazio = agora
    observacao: str | None = Field(None, max_length=500)
    itens: list[SessaoItemIn] = Field(min_length=1, max_length=30)


class ApiKeyCriarIn(BaseModel):
    """Criação de uma API key. expira_em opcional (vazio = não expira)."""
    nome: str = Field(min_length=2, max_length=80)
    expira_em: date | None = None

    @field_validator("expira_em")
    @classmethod
    def _expira(cls, v):
        if v is not None and v < date.today():
            raise ValueError("A data de expiração não pode ser no passado.")
        return v
