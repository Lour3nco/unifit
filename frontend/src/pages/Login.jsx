import { useState } from "react";
import { mensagemErro } from "../api";
import { useAuth } from "../auth.jsx";
import Abas from "../components/Abas.jsx";
import Logo from "../components/Logo.jsx";

const TEXTOS = {
  aluno: { sub: "Acesse sua conta de aluno", cta: "Não tem conta?", link: "Criar conta" },
  equipe: { sub: "Acesse o painel da sua academia", cta: "Novo na equipe?", link: "Solicitar acesso" },
};

export default function Login({ aba, onAba, onCadastro, onEsqueci }) {
  const { entrar, aviso } = useAuth();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const t = TEXTOS[aba] || TEXTOS.equipe;

  function trocar(nova) {
    setErro("");
    onAba(nova);
  }

  async function enviar(e) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      await entrar(email.trim(), senha, aba); // "aluno" ou "equipe": o back-end confere o perfil da conta
    } catch (err) {
      setErro(mensagemErro(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="login">
      <div className="login-hero">
        <Logo variant="horizontal" />
        <div className="tagline">
          <span className="eyebrow">Gestão de academia</span>
          <h1>Treine a sua academia para <b>crescer.</b></h1>
          <p>Alunos, planos, aulas, check-ins e financeiro em um só lugar. Menos planilha, mais resultado.</p>
        </div>
      </div>

      <form className="login-form" onSubmit={enviar}>
        <div className="form-logo"><Logo variant="compacta" /></div>
        <h2>Entrar</h2>
        <p className="sub">{t.sub}</p>
        <Abas aba={aba} onAba={trocar} />

        <label>E-mail
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="voce@unifit.com.br" autoComplete="username" required />
        </label>

        <label>
          <span className="label-row">
            <span>Senha</span>
            <button type="button" className="linkbtn" onClick={onEsqueci}>Esqueci a senha</button>
          </span>
          <input type="password" value={senha} onChange={(e) => setSenha(e.target.value)}
            placeholder="••••••••" autoComplete="current-password" required />
        </label>

        <label className="check"><input type="checkbox" defaultChecked /> Manter conectado</label>

        <div className="err" role="alert">{erro || aviso}</div>

        <button className="btn" type="submit" disabled={enviando}>
          {enviando ? "Entrando..." : "Entrar no painel"}
        </button>

        <p className="rodape">
          {t.cta} <button type="button" className="linkbtn" onClick={onCadastro}>{t.link}</button>
        </p>
      </form>
    </section>
  );
}
