import { useState } from "react";
import { mensagemErro } from "../api";
import { useAuth } from "../auth.jsx";
import Abas from "../components/Abas.jsx";
import Palco from "../components/Palco.jsx";

const TEXTOS = {
  aluno: {
    titulo: "Área do aluno",
    texto: "Entre para ver seu plano, pagamentos, check-ins e treinos.",
    cadastro: "Não tem conta?",
    link: "Criar conta",
  },
  equipe: {
    titulo: "Gestão da academia",
    texto: "Acesso de administração, recepção e instrutores: alunos, pagamentos, treinos e risco de evasão.",
    cadastro: "Novo na equipe?",
    link: "Solicitar acesso",
  },
};

export default function Login({ aba, onAba, onCadastro }) {
  const { entrar, aviso } = useAuth();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const t = TEXTOS[aba];

  function trocar(nova) {
    setErro("");
    onAba(nova);
  }

  async function enviar(e) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      await entrar(email.trim(), senha, aba);
    } catch (err) {
      setErro(mensagemErro(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="login">
      <form onSubmit={enviar}>
        <div className="brand">Uni<b>Fit</b></div>
        <Abas aba={aba} onAba={trocar} />
        <h1>{t.titulo}</h1>
        <p>{t.texto}</p>
        <label>E-mail
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
        </label>
        <label>Senha
          <input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" required />
        </label>
        <div className="err" role="alert">{erro || aviso}</div>
        <button className="btn" type="submit" disabled={enviando}>{enviando ? "Entrando..." : "Entrar"}</button>
        <span className="hint">
          {t.cadastro} <button type="button" className="linkbtn" onClick={onCadastro}>{t.link}</button>
        </span>
      </form>
      <Palco />
    </section>
  );
}
