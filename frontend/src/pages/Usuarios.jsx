import { useEffect, useState } from "react";
import api, { mensagemErro } from "../api";
import { useAuth } from "../auth.jsx";

const PERFIS = [
  ["administrador", "Administrador"],
  ["recepcao", "Recepção"],
  ["instrutor", "Instrutor"],
  ["aluno", "Aluno"],
];
const VAZIO = { nome: "", email: "", senha: "", perfil: "recepcao" };

export default function Usuarios() {
  const { usuario } = useAuth();
  const [lista, setLista] = useState([]);
  const [f, setF] = useState(VAZIO);
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [erroLista, setErroLista] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [alterando, setAlterando] = useState(null);
  const mudar = (campo) => (e) => setF({ ...f, [campo]: e.target.value });

  const carregar = () =>
    api.get("/usuarios").then((r) => setLista(r.data)).catch((e) => setErroLista(mensagemErro(e)));
  useEffect(() => { carregar(); }, []);

  async function criar(e) {
    e.preventDefault();
    setErro(""); setOk("");
    if (f.senha.length < 8) return setErro("A senha precisa ter pelo menos 8 caracteres.");
    setEnviando(true);
    try {
      await api.post("/usuarios", { ...f, nome: f.nome.trim(), email: f.email.trim() });
      setOk(`Usuário ${f.nome.trim()} cadastrado.`);
      setF(VAZIO);
      carregar();
    } catch (err) {
      setErro(mensagemErro(err));
    } finally {
      setEnviando(false);
    }
  }

  async function alterar(u, mudancas) {
    setErroLista("");
    setAlterando(u.id);
    try {
      const { data } = await api.patch(`/usuarios/${u.id}`, mudancas);
      setLista((l) => l.map((x) => (x.id === data.id ? data : x)));
    } catch (err) {
      setErroLista(mensagemErro(err));
    } finally {
      setAlterando(null);
    }
  }

  const inativos = lista.filter((u) => !u.ativo);

  return (
    <>
      <section className="card">
        <h3>Cadastrar usuário</h3>
        <form className="form-row" onSubmit={criar}>
          <label>Nome<input value={f.nome} onChange={mudar("nome")} maxLength={120} required /></label>
          <label>E-mail<input type="email" value={f.email} onChange={mudar("email")} maxLength={150} required /></label>
          <label>Senha<input type="password" value={f.senha} onChange={mudar("senha")} autoComplete="new-password" minLength={8} required /></label>
          <label>Perfil
            <select value={f.perfil} onChange={mudar("perfil")}>
              {PERFIS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
            </select>
          </label>
          <button className="btn" type="submit" disabled={enviando}>{enviando ? "Salvando..." : "Cadastrar"}</button>
        </form>
        <div className="err" role="alert">{erro}</div>
        {ok && <div className="okmsg" role="status">{ok}</div>}
      </section>

      <section className="card" style={{ marginTop: 14 }}>
        <h3>Usuários ({lista.length})</h3>
        {inativos.length > 0 && (
          <div className="aviso" role="status">
            {inativos.length === 1 ? "1 conta inativa ou aguardando aprovação" : `${inativos.length} contas inativas ou aguardando aprovação`}:
            {" "}{inativos.map((u) => u.nome).join(", ")}. Confira a função e clique em “Aprovar”.
          </div>
        )}
        <div className="err" role="alert">{erroLista}</div>
        <div className="tablewrap">
          <table className="t">
            <thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Situação</th><th></th></tr></thead>
            <tbody>
              {lista.map((u) => {
                const eu = u.id === usuario.id;
                const ocupado = alterando === u.id;
                return (
                  <tr key={u.id}>
                    <td>{u.nome}{eu && <span className="hint"> (você)</span>}</td>
                    <td>{u.email}</td>
                    <td>
                      <select className="compacto" value={u.perfil} disabled={eu || ocupado}
                        aria-label={`Perfil de ${u.nome}`} onChange={(e) => alterar(u, { perfil: e.target.value })}>
                        {PERFIS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
                      </select>
                    </td>
                    <td><span className={`chip ${u.ativo ? "ativo" : "pendente"}`}>{u.ativo ? "Ativo" : "Inativo"}</span></td>
                    <td>
                      {!eu && (
                        <button type="button" className={u.ativo ? "btn-sec" : "btn compacto"} disabled={ocupado}
                          onClick={() => alterar(u, { ativo: !u.ativo })}>
                          {u.ativo ? "Desativar" : "Aprovar"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
