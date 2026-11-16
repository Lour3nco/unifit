import { useEffect, useState } from "react";
import api, { mensagemErro } from "../api";
import { useAuth } from "../auth.jsx";
import BuscaAluno, { SituacaoAluno } from "../components/BuscaAluno.jsx";
import PageHeader from "../components/PageHeader.jsx";
import { data, hojeISO, moeda } from "../formato";

const FILTROS = [["", "Todas"], ["ativa", "Ativas"], ["vencida", "Vencidas"], ["trancada", "Trancadas"],
  ["cancelada", "Canceladas"], ["encerrada", "Encerradas"]];
const ROTULO = { ativa: "Ativa", vencida: "Vencida", trancada: "Trancada", cancelada: "Cancelada", encerrada: "Encerrada" };

export default function PlanosMatriculas() {
  const { usuario } = useAuth();
  const [planos, setPlanos] = useState([]);
  const [erro, setErro] = useState("");
  const [versao, setVersao] = useState(0); // muda depois de matricular, para recarregar a lista

  const carregarPlanos = () => api.get("/planos").then((r) => setPlanos(r.data)).catch((e) => setErro(mensagemErro(e)));
  useEffect(() => { carregarPlanos(); }, []);

  return (
    <>
      <SecaoPlanos planos={planos} podeEditar={usuario.perfil === "administrador"} onMudou={carregarPlanos} erroCarregar={erro} />
      <NovaMatricula planos={planos.filter((p) => p.ativo)} onMatriculou={() => setVersao((v) => v + 1)} />
      <ListaMatriculas versao={versao} />
    </>
  );
}

function SecaoPlanos({ planos, podeEditar, onMudou, erroCarregar }) {
  const [editando, setEditando] = useState(null); // null, "novo" ou id
  const [f, setF] = useState({});
  const [erro, setErro] = useState("");

  function abrir(p) {
    setErro("");
    setEditando(p ? p.id : "novo");
    setF(p ? { nome: p.nome, valor: p.valor, duracao_dias: p.duracao_dias, ativo: p.ativo }
      : { nome: "", valor: "", duracao_dias: 30, ativo: true });
  }

  async function salvar(e) {
    e.preventDefault();
    setErro("");
    const corpo = { ...f, nome: f.nome.trim(), valor: Number(String(f.valor).replace(",", ".")), duracao_dias: Number(f.duracao_dias) };
    try {
      if (editando === "novo") await api.post("/planos", corpo);
      else await api.put(`/planos/${editando}`, corpo);
      setEditando(null);
      onMudou();
    } catch (err) {
      setErro(mensagemErro(err));
    }
  }

  return (
    <>
      <PageHeader eyebrow="Gerenciar planos" title="Planos & Preços">
        {podeEditar && editando === null && <button className="btn" type="button" onClick={() => abrir(null)}>+ Criar plano</button>}
      </PageHeader>

      <div className="err" role="alert">{erro || erroCarregar}</div>

      {editando !== null && (
        <section className="card" style={{ marginBottom: 16 }}>
          <h3>{editando === "novo" ? "Novo plano" : "Editar plano"}</h3>
          <form className="form-row" onSubmit={salvar}>
            <label>Nome<input value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} maxLength={80} required /></label>
            <label>Valor (R$)<input type="number" value={f.valor} onChange={(e) => setF({ ...f, valor: e.target.value })} min="0" step="0.01" required /></label>
            <label>Duração (dias)<input type="number" value={f.duracao_dias} onChange={(e) => setF({ ...f, duracao_dias: e.target.value })} min="1" max="3650" required /></label>
            <label className="check"><input type="checkbox" checked={f.ativo} onChange={(e) => setF({ ...f, ativo: e.target.checked })} /> Disponível para venda</label>
            <div className="acoes">
              <button className="btn" type="submit">Salvar</button>
              <button className="btn-sec" type="button" onClick={() => setEditando(null)}>Cancelar</button>
            </div>
          </form>
        </section>
      )}

      <div className="planos">
        {planos.map((p, i) => {
          const destaque = planos.length >= 2 && i === 1;
          return (
            <div className={`plano ${destaque ? "destaque" : ""}`} key={p.id}>
              <div className="plano-topo">
                <h3>{p.nome}</h3>
                {destaque && <span className="tag">Popular</span>}
              </div>
              <div className="plano-sub">{p.ativo ? "Disponível para venda" : "Fora de venda"}</div>
              <div className="preco">{moeda(p.valor)}<small>{p.duracao_dias <= 31 ? "/mês" : `/${p.duracao_dias} dias`}</small></div>
              <ul className="plano-feats">
                <li>{p.duracao_dias} dias de vigência</li>
                <li>Renovação automática da mensalidade</li>
                <li>{p.ativo ? "Disponível no app do aluno" : "Indisponível para novas matrículas"}</li>
              </ul>
              <div className="plano-count"><span>Situação</span><strong>{p.ativo ? "Ativo" : "Inativo"}</strong></div>
              {podeEditar && <button className="btn-sec" type="button" onClick={() => abrir(p)}>Editar plano</button>}
            </div>
          );
        })}
        {planos.length === 0 && <div className="ph">Nenhum plano cadastrado ainda.</div>}
      </div>
      {podeEditar && <p className="hint" style={{ marginTop: 12 }}>Mudar o valor vale para as próximas matrículas; cobranças já geradas não mudam.</p>}
    </>
  );
}

function NovaMatricula({ planos, onMatriculou }) {
  const [aluno, setAluno] = useState(null);
  const [planoId, setPlanoId] = useState("");
  const [inicio, setInicio] = useState(hojeISO());
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function matricular(e) {
    e.preventDefault();
    setErro(""); setOk("");
    setEnviando(true);
    try {
      const { data: r } = await api.post("/matriculas", { aluno_id: aluno.id, plano_id: Number(planoId), data_inicio: inicio });
      setOk(r.mensagem);
      setAluno(null);
      onMatriculou();
    } catch (err) {
      setErro(mensagemErro(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="card" style={{ marginTop: 14 }}>
      <h3>Nova matrícula</h3>
      {!aluno ? (
        <BuscaAluno acao={(a) => (
          <button type="button" className="btn-sec" onClick={() => { setAluno(a); setOk(""); setErro(""); }}>Selecionar</button>
        )} />
      ) : (
        <form className="form-row" onSubmit={matricular}>
          <div className="selecionado">
            <small>Aluno</small>
            <strong>{aluno.nome}</strong>
            <SituacaoAluno a={aluno} />
            <button type="button" className="linkbtn" onClick={() => setAluno(null)}>Trocar</button>
          </div>
          <label>Plano
            <select value={planoId} onChange={(e) => setPlanoId(e.target.value)} required>
              <option value="">Escolha...</option>
              {planos.map((p) => <option key={p.id} value={p.id}>{p.nome} · {moeda(p.valor)}</option>)}
            </select>
          </label>
          <label>Início<input type="date" value={inicio} onChange={(e) => setInicio(e.target.value)} required /></label>
          <button className="btn" type="submit" disabled={enviando}>{enviando ? "Matriculando..." : "Matricular"}</button>
        </form>
      )}
      <div className="err" role="alert">{erro}</div>
      {ok && <div className="okmsg" role="status">{ok}</div>}
    </section>
  );
}

function ListaMatriculas({ versao }) {
  const [situacao, setSituacao] = useState("ativa");
  const [busca, setBusca] = useState("");
  const [lista, setLista] = useState(null);
  const [erro, setErro] = useState("");
  const [msg, setMsg] = useState("");

  const carregar = () =>
    api.get("/matriculas", { params: { situacao, busca } }).then((r) => setLista(r.data)).catch((e) => setErro(mensagemErro(e)));

  useEffect(() => {
    const id = setTimeout(carregar, 300);
    return () => clearTimeout(id);
  }, [situacao, busca, versao]);

  async function mudar(m, status, aviso) {
    if (aviso && !window.confirm(aviso)) return;
    setErro(""); setMsg("");
    try {
      const { data: r } = await api.patch(`/matriculas/${m.id}`, { status });
      setMsg(r.mensagem);
      carregar();
    } catch (err) {
      setErro(mensagemErro(err));
    }
  }

  return (
    <section className="card" style={{ marginTop: 14 }}>
      <h3>Matrículas</h3>
      <div className="toolbar">
        <select value={situacao} onChange={(e) => setSituacao(e.target.value)} aria-label="Filtrar por situação">
          {FILTROS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
        </select>
        <input type="search" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Nome do aluno" aria-label="Buscar aluno" />
      </div>
      <div className="err" role="alert">{erro}</div>
      {msg && <div className="okmsg" role="status" style={{ marginBottom: 8 }}>{msg}</div>}
      <div className="tablewrap">
        <table className="t">
          <thead><tr><th>Aluno</th><th>Plano</th><th>Início</th><th>Fim</th><th>Situação</th><th></th></tr></thead>
          <tbody>
            {(lista || []).map((m) => {
              const st = m.status === "ativa" && !m.vigente ? "vencida" : m.status;
              return (
                <tr key={m.id}>
                  <td>{m.aluno}</td><td>{m.plano}</td><td>{data(m.data_inicio)}</td><td>{data(m.data_fim)}</td>
                  <td><span className={`chip ${st}`}>{ROTULO[st] || st}</span></td>
                  <td className="acoes">
                    {m.status === "ativa" && m.vigente && <button className="btn-sec" type="button" onClick={() => mudar(m, "trancada")}>Trancar</button>}
                    {m.status === "trancada" && <button className="btn-sec" type="button" onClick={() => mudar(m, "ativa")}>Reativar</button>}
                    {(m.status === "ativa" || m.status === "trancada") && (
                      <>
                        <button className="btn-sec" type="button"
                          onClick={() => mudar(m, "encerrada", `Encerrar a matrícula de ${m.aluno}? As mensalidades em aberto serão canceladas.`)}>Encerrar</button>
                        <button className="btn-sec perigo" type="button"
                          onClick={() => mudar(m, "cancelada", `Cancelar a matrícula de ${m.aluno}? As mensalidades em aberto serão canceladas.`)}>Cancelar</button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
            {lista && lista.length === 0 && <tr><td colSpan="6" className="vazio">Nenhuma matrícula neste filtro.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
