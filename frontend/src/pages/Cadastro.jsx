import { useState } from "react";
import api, { mensagemErro } from "../api";
import { useAuth } from "../auth.jsx";
import Abas from "../components/Abas.jsx";
import Logo from "../components/Logo.jsx";
import { cpfMascara } from "../formato";

const VAZIO = { nome: "", email: "", senha: "", confirmar: "", perfil: "recepcao", cpf: "" };
const TEXTOS = {
  aluno: { titulo: "Crie sua conta", texto: "Acompanhe seus treinos, pagamentos e histórico na academia." },
  equipe: { titulo: "Solicitar acesso", texto: "Para recepção e instrutores. Sua conta é liberada depois que um administrador aprovar." },
};

function Hero() {
  return (
    <div className="login-hero">
      <Logo variant="horizontal" />
      <div className="tagline">
        <span className="eyebrow">Gestão de academia</span>
        <h1>Treine a sua academia para <b>crescer.</b></h1>
        <p>Alunos, planos, aulas, check-ins e financeiro em um só lugar. Menos planilha, mais resultado.</p>
      </div>
    </div>
  );
}

export default function Cadastro({ aba, onAba, onLogin }) {
  const { cadastrar } = useAuth();
  const [f, setF] = useState(VAZIO);
  const [erro, setErro] = useState("");
  const [enviado, setEnviado] = useState("");
  const [enviando, setEnviando] = useState(false);
  const mudar = (campo, filtro = (v) => v) => (e) => setF({ ...f, [campo]: filtro(e.target.value) });
  const t = TEXTOS[aba] || TEXTOS.equipe;

  function trocar(nova) {
    setErro("");
    setEnviado("");
    onAba(nova);
  }

  async function enviar(e) {
    e.preventDefault();
    setErro("");
    if (f.nome.trim().length < 2) return setErro("Digite seu nome completo.");
    if (f.senha.length < 8) return setErro("A senha precisa ter pelo menos 8 caracteres.");
    if (f.senha !== f.confirmar) return setErro("As senhas não são iguais.");
    if (aba === "aluno" && f.cpf.replace(/\D/g, "").length !== 11) return setErro("Informe o CPF completo.");
    setEnviando(true);
    try {
      if (aba === "aluno") {
        await cadastrar({ nome: f.nome.trim(), email: f.email.trim(), senha: f.senha, cpf: f.cpf });
      } else {
        const { data } = await api.post("/auth/cadastro-equipe",
          { nome: f.nome.trim(), email: f.email.trim(), senha: f.senha, perfil: f.perfil });
        setEnviado(data.mensagem);
        setF(VAZIO);
      }
    } catch (err) {
      setErro(mensagemErro(err));
    } finally {
      setEnviando(false);
    }
  }

  if (enviado) {
    return (
      <section className="login">
        <Hero />
        <div className="login-form">
          <div className="form-logo"><Logo variant="compacta" /></div>
          <h2>Pedido enviado</h2>
          <p className="sub">{enviado}</p>
          <button className="btn" type="button" onClick={onLogin}>Voltar para o login</button>
        </div>
      </section>
    );
  }

  return (
    <section className="login">
      <Hero />
      <form className="login-form" onSubmit={enviar}>
        <div className="form-logo"><Logo variant="compacta" /></div>
        <h2>{t.titulo}</h2>
        <p className="sub">{t.texto}</p>
        <Abas aba={aba} onAba={trocar} />

        <label>Nome completo
          <input value={f.nome} onChange={mudar("nome")} autoComplete="name" maxLength={120} required />
        </label>
        <label>E-mail
          <input type="email" value={f.email} onChange={mudar("email")} autoComplete="email" maxLength={150} required />
        </label>
        {aba === "aluno" && (
          <label>CPF
            <input value={f.cpf} onChange={mudar("cpf", cpfMascara)} inputMode="numeric" placeholder="000.000.000-00" required />
          </label>
        )}
        {aba === "equipe" && (
          <label>Função
            <select value={f.perfil} onChange={mudar("perfil")}>
              <option value="recepcao">Recepção</option>
              <option value="instrutor">Instrutor</option>
            </select>
          </label>
        )}
        <label>Senha
          <input type="password" value={f.senha} onChange={mudar("senha")} autoComplete="new-password" minLength={8} required />
        </label>
        <label>Confirmar senha
          <input type="password" value={f.confirmar} onChange={mudar("confirmar")} autoComplete="new-password" required />
        </label>

        <div className="err" role="alert">{erro}</div>
        <button className="btn" type="submit" disabled={enviando}>
          {enviando ? "Enviando..." : aba === "aluno" ? "Criar conta" : "Solicitar acesso"}
        </button>
        <p className="rodape">
          Já tem conta? <button type="button" className="linkbtn" onClick={onLogin}>Entrar</button>
        </p>
      </form>
    </section>
  );
}
