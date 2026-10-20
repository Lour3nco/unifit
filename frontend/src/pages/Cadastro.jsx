import { useEffect, useState } from "react";
import api, { mensagemErro } from "../api";
import { useAuth } from "../auth.jsx";
import Abas from "../components/Abas.jsx";
import Palco from "../components/Palco.jsx";
import { cpfMascara, moeda } from "../formato";

const VAZIO = { nome: "", email: "", senha: "", confirmar: "", perfil: "recepcao", plano_id: "", cpf: "" };
const TEXTOS = {
  aluno: {
    titulo: "Crie sua conta",
    texto: "Acompanhe seus treinos, pagamentos e histórico na academia.",
  },
  equipe: {
    titulo: "Solicitar acesso",
    texto: "Para recepção e instrutores. Sua conta será liberada depois que um administrador aprovar.",
  },
};

export default function Cadastro({ aba, onAba, onLogin }) {
  const { cadastrar } = useAuth();
  const [f, setF] = useState(VAZIO);
  const [erro, setErro] = useState("");
  const [enviado, setEnviado] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [planos, setPlanos] = useState([]);
  useEffect(() => {
    api.get("/auth/planos").then((r) => setPlanos(r.data)).catch(() => setPlanos([]));
  }, []);
  const mudar = (campo, filtro = (v) => v) => (e) => setF({ ...f, [campo]: filtro(e.target.value) });
  const t = TEXTOS[aba];

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
    if (aba === "aluno" && !f.plano_id) return setErro("Escolha um plano.");
    setEnviando(true);
    try {
      if (aba === "aluno") {
        await cadastrar({ nome: f.nome.trim(), email: f.email.trim(), senha: f.senha, cpf: f.cpf, plano_id: Number(f.plano_id) }); // já entra logado e matriculado
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
        <div className="form">
          <div className="brand">Uni<b>Fit</b></div>
          <h1>Pedido enviado</h1>
          <p>{enviado}</p>
          <button className="btn" type="button" onClick={onLogin}>Voltar para o login</button>
        </div>
        <Palco />
      </section>
    );
  }

  return (
    <section className="login">
      <form onSubmit={enviar}>
        <div className="brand">Uni<b>Fit</b></div>
        <Abas aba={aba} onAba={trocar} />
        <h1>{t.titulo}</h1>
        <p>{t.texto}</p>
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
        {aba === "aluno" && (
          <label>Plano
            <select value={f.plano_id} onChange={mudar("plano_id")} required>
              <option value="">{planos.length ? "Escolha seu plano..." : "Carregando planos..."}</option>
              {planos.map((p) => (
                <option key={p.id} value={p.id}>{p.nome} · {moeda(p.valor)} · {p.duracao_dias} dias</option>
              ))}
            </select>
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
        <span className="hint">
          Já tem conta? <button type="button" className="linkbtn" onClick={onLogin}>Entrar</button>
        </span>
      </form>
      <Palco />
    </section>
  );
}
