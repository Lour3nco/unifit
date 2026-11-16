import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import api, { mensagemErro } from "../api";
import Logo from "../components/Logo.jsx";

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

// "(11) 98888-7777" enquanto digita
const telefoneMascara = (v) => {
  const d = v.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 2) return d;
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
};

/** Pede o link de troca de senha por e-mail ou SMS. */
export default function EsqueciSenha({ onVoltar }) {
  const [canal, setCanal] = useState("email");
  const [valor, setValor] = useState("");
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [enviando, setEnviando] = useState(false);

  function trocar(novo) {
    setCanal(novo); setValor(""); setErro(""); setOk("");
  }

  async function enviar(e) {
    e.preventDefault();
    setErro(""); setOk("");
    setEnviando(true);
    try {
      const corpo = canal === "email" ? { email: valor.trim() } : { telefone: valor };
      const { data } = await api.post("/auth/esqueci-senha", corpo);
      setOk(data.mensagem);
    } catch (err) {
      setErro(mensagemErro(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="login">
      <Hero />
      <form className="login-form" onSubmit={enviar}>
        <div className="form-logo"><Logo variant="compacta" /></div>
        <h2>Esqueci a senha</h2>
        <p className="sub">Enviamos um link para você criar uma nova senha.</p>

        <div className="abas" role="tablist" aria-label="Receber o link por">
          <button type="button" role="tab" aria-selected={canal === "email"} onClick={() => trocar("email")}>E-mail</button>
          <button type="button" role="tab" aria-selected={canal === "sms"} onClick={() => trocar("sms")}>Telefone (SMS)</button>
        </div>

        {canal === "email" ? (
          <label>E-mail da conta
            <input type="email" value={valor} onChange={(e) => setValor(e.target.value)}
              placeholder="voce@unifit.com.br" autoComplete="username" required />
          </label>
        ) : (
          <label>Celular cadastrado
            <input type="tel" value={valor} onChange={(e) => setValor(telefoneMascara(e.target.value))}
              placeholder="(11) 98888-7777" autoComplete="tel" required />
            <small className="hint">O telefone precisa estar no seu cadastro de aluno. Equipe: use o e-mail.</small>
          </label>
        )}

        <div className="err" role="alert">{erro}</div>
        {ok && <div className="okmsg" role="status">{ok}</div>}

        <button className="btn" type="submit" disabled={enviando}>
          {enviando ? "Enviando..." : canal === "email" ? "Enviar link por e-mail" : "Enviar link por SMS"}
        </button>
        <p className="rodape"><button type="button" className="linkbtn" onClick={onVoltar}>Voltar para o login</button></p>
      </form>
    </section>
  );
}

/** Aberta pelo link do e-mail/SMS: /redefinir-senha?token=... */
export function RedefinirSenha({ onVoltar }) {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [senha, setSenha] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function enviar(e) {
    e.preventDefault();
    setErro("");
    if (senha.length < 8) return setErro("A senha precisa ter pelo menos 8 caracteres.");
    if (senha !== confirmar) return setErro("As senhas não conferem.");
    setEnviando(true);
    try {
      const { data } = await api.post("/auth/redefinir-senha", { token, senha });
      setOk(data.mensagem);
    } catch (err) {
      setErro(mensagemErro(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="login">
      <Hero />
      <form className="login-form" onSubmit={enviar}>
        <div className="form-logo"><Logo variant="compacta" /></div>
        <h2>Nova senha</h2>
        {!token ? (
          <div className="err" role="alert">Link incompleto. Abra o link exatamente como recebeu ou peça um novo.</div>
        ) : ok ? (
          <div className="okmsg" role="status">{ok}</div>
        ) : (
          <>
            <p className="sub">Escolha uma senha com pelo menos 8 caracteres.</p>
            <label>Nova senha
              <input type="password" value={senha} onChange={(e) => setSenha(e.target.value)}
                autoComplete="new-password" minLength={8} maxLength={72} required />
            </label>
            <label>Repita a nova senha
              <input type="password" value={confirmar} onChange={(e) => setConfirmar(e.target.value)}
                autoComplete="new-password" required />
            </label>
            <div className="err" role="alert">{erro}</div>
            <button className="btn" type="submit" disabled={enviando}>{enviando ? "Salvando..." : "Salvar nova senha"}</button>
          </>
        )}
        <p className="rodape"><button type="button" className="linkbtn" onClick={onVoltar}>Ir para o login</button></p>
      </form>
    </section>
  );
}
