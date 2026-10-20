import { useEffect, useState } from "react";
import api, { mensagemErro } from "../api";
import BuscaAluno from "../components/BuscaAluno.jsx";
import { FormSessao, GraficoEvolucao, HistoricoSessoes, ResumoMensal } from "../components/Evolucao.jsx";
import { data, numeroOuNulo } from "../formato";

const ITEM_VAZIO = { exercicio_id: "", series: 3, repeticoes: 12, carga_kg: "", descanso_seg: 60 };

export default function Treinos() {
  const [exercicios, setExercicios] = useState([]);
  const [aluno, setAluno] = useState(null);
  const [erro, setErro] = useState("");

  const carregarExercicios = () =>
    api.get("/exercicios").then((r) => setExercicios(r.data)).catch((e) => setErro(mensagemErro(e)));
  useEffect(() => { carregarExercicios(); }, []);

  return (
    <>
      <div className="err" role="alert">{erro}</div>
      <section className="card">
        <h3>Fichas de treino</h3>
        {!aluno ? (
          <BuscaAluno rotulo="Escolha o aluno" acao={(a) => (
            <button type="button" className="btn-sec" onClick={() => setAluno(a)}>Abrir fichas</button>
          )} />
        ) : (
          <div className="selecionado-linha">
            <div><small>Aluno</small><strong>{aluno.nome}</strong> <span className="hint">matrícula {aluno.numero_matricula}</span></div>
            <button type="button" className="linkbtn" onClick={() => setAluno(null)}>Trocar aluno</button>
          </div>
        )}
      </section>
      {aluno && <PainelAluno key={aluno.id} aluno={aluno} exercicios={exercicios} />}
      <Exercicios exercicios={exercicios} onMudou={carregarExercicios} />
    </>
  );
}

function PainelAluno({ aluno, exercicios }) {
  const [fichas, setFichas] = useState(null);
  const [aba, setAba] = useState("fichas"); // fichas | evolucao
  const [erro, setErro] = useState("");

  useEffect(() => {
    api.get("/treinos", { params: { aluno_id: aluno.id } }).then((r) => setFichas(r.data)).catch((e) => setErro(mensagemErro(e)));
  }, [aluno.id]);

  return (
    <>
      <div className="abas" role="tablist" aria-label="Fichas ou evolução" style={{ marginTop: 14 }}>
        <button type="button" role="tab" aria-selected={aba === "fichas"} onClick={() => setAba("fichas")}>Fichas de treino</button>
        <button type="button" role="tab" aria-selected={aba === "evolucao"} onClick={() => setAba("evolucao")}>Evolução</button>
      </div>
      <div className="err" role="alert">{erro}</div>
      {aba === "fichas"
        ? <FichasDoAluno aluno={aluno} exercicios={exercicios} fichas={fichas} setFichas={setFichas} />
        : <AcompanhamentoDoAluno aluno={aluno} fichas={fichas} />}
    </>
  );
}

function FichasDoAluno({ aluno, exercicios, fichas, setFichas }) {
  const [editando, setEditando] = useState(null); // null, "nova" ou id da ficha
  const [erro, setErro] = useState("");

  async function arquivar(f, ativo) {
    setErro("");
    try {
      const { data: r } = await api.patch(`/treinos/${f.id}`, { ativo });
      setFichas(r);
    } catch (e) {
      setErro(mensagemErro(e));
    }
  }

  return (
    <>
      <div className="toolbar" style={{ marginTop: 14 }}>
        {editando === null && <button className="btn" type="button" onClick={() => setEditando("nova")}>Nova ficha</button>}
        <div className="err" role="alert">{erro}</div>
      </div>
      {editando !== null && (
        <FormFicha aluno={aluno} exercicios={exercicios} ficha={fichas?.find((f) => f.id === editando)}
          onSalvo={(r) => { setFichas(r); setEditando(null); }} onCancelar={() => setEditando(null)} />
      )}
      {fichas && fichas.length === 0 && editando === null && <div className="ph">Este aluno ainda não tem ficha de treino.</div>}
      {(fichas || []).map((f) => (
        <section className={`card ficha ${f.ativo ? "" : "arquivada"}`} key={f.id} style={{ marginBottom: 14 }}>
          <div className="card-topo">
            <div>
              <h3>{f.nome} {!f.ativo && <span className="chip">Arquivada</span>}</h3>
              <small className="hint">{f.objetivo ? `${f.objetivo} · ` : ""}por {f.instrutor || "—"} em {data(f.criado_em)}</small>
            </div>
            <div className="acoes">
              {f.ativo && <button className="btn-sec" type="button" onClick={() => setEditando(f.id)}>Editar</button>}
              <button className="btn-sec" type="button" onClick={() => arquivar(f, !f.ativo)}>{f.ativo ? "Arquivar" : "Reativar"}</button>
            </div>
          </div>
          <TabelaItens itens={f.itens} />
        </section>
      ))}
    </>
  );
}

function AcompanhamentoDoAluno({ aluno, fichas }) {
  const [sessoes, setSessoes] = useState(null);
  const [evolucao, setEvolucao] = useState(null);
  const [registrando, setRegistrando] = useState(false);
  const [erro, setErro] = useState("");

  const carregar = () => {
    api.get("/sessoes", { params: { aluno_id: aluno.id } }).then((r) => setSessoes(r.data)).catch((e) => setErro(mensagemErro(e)));
    api.get("/evolucao", { params: { aluno_id: aluno.id } }).then((r) => setEvolucao(r.data)).catch((e) => setErro(mensagemErro(e)));
  };
  useEffect(carregar, [aluno.id]);

  async function salvar(corpo) {
    try {
      const { data: r } = await api.post(`/treinos/${corpo.treino_id}/sessoes`, corpo);
      setSessoes(r);
      setRegistrando(false);
      api.get("/evolucao", { params: { aluno_id: aluno.id } }).then((x) => setEvolucao(x.data));
    } catch (e) {
      throw mensagemErro(e);
    }
  }

  async function excluir(id) {
    setErro("");
    try {
      await api.delete(`/sessoes/${id}`);
      carregar();
    } catch (e) {
      setErro(mensagemErro(e));
    }
  }

  return (
    <>
      <div className="toolbar" style={{ marginTop: 14 }}>
        {!registrando && <button className="btn" type="button" onClick={() => setRegistrando(true)}>Registrar treino feito</button>}
        <div className="err" role="alert">{erro}</div>
      </div>
      {registrando && <FormSessao treinos={fichas || []} onSalvar={salvar} onCancelar={() => setRegistrando(false)} />}
      <ResumoMensal sessoes={sessoes} />
      <h3 style={{ margin: "18px 0 10px" }}>Evolução por exercício</h3>
      <GraficoEvolucao evolucao={evolucao} />
      <h3 style={{ margin: "18px 0 10px" }}>Histórico de sessões</h3>
      <HistoricoSessoes sessoes={sessoes} onExcluir={excluir} />
    </>
  );
}

export function TabelaItens({ itens }) {
  return (
    <div className="tablewrap">
      <table className="t">
        <thead><tr><th>#</th><th>Exercício</th><th>Séries</th><th>Repetições</th><th>Carga</th><th>Descanso</th></tr></thead>
        <tbody>
          {itens.map((i, k) => (
            <tr key={k}>
              <td>{k + 1}</td><td>{i.exercicio}{i.grupo_muscular && <small className="hint"> · {i.grupo_muscular}</small>}</td>
              <td>{i.series}</td><td>{i.repeticoes}</td>
              <td>{i.carga_kg != null ? `${Number(i.carga_kg)} kg` : "—"}</td>
              <td>{i.descanso_seg != null ? `${i.descanso_seg}s` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FormFicha({ aluno, exercicios, ficha, onSalvo, onCancelar }) {
  const [nome, setNome] = useState(ficha?.nome || "");
  const [objetivo, setObjetivo] = useState(ficha?.objetivo || "");
  const [itens, setItens] = useState(() => (ficha?.itens.length
    ? ficha.itens.map((i) => ({ exercicio_id: String(i.exercicio_id), series: i.series, repeticoes: i.repeticoes,
      carga_kg: i.carga_kg ?? "", descanso_seg: i.descanso_seg ?? "" }))
    : [{ ...ITEM_VAZIO }]));
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  const mudarItem = (k, campo) => (e) => setItens(itens.map((it, i) => (i === k ? { ...it, [campo]: e.target.value } : it)));
  const mover = (k, d) => {
    const n = [...itens];
    [n[k], n[k + d]] = [n[k + d], n[k]];
    setItens(n);
  };

  async function salvar(e) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    const corpo = {
      aluno_id: aluno.id, nome: nome.trim(), objetivo: objetivo.trim() || null,
      itens: itens.map((i) => ({ exercicio_id: Number(i.exercicio_id), series: Number(i.series), repeticoes: Number(i.repeticoes),
        carga_kg: numeroOuNulo(i.carga_kg), descanso_seg: numeroOuNulo(i.descanso_seg) })),
    };
    try {
      const { data: r } = ficha ? await api.put(`/treinos/${ficha.id}`, corpo) : await api.post("/treinos", corpo);
      onSalvo(r);
    } catch (err) {
      setErro(mensagemErro(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="card" style={{ marginBottom: 14 }}>
      <h3>{ficha ? `Editar ${ficha.nome}` : `Nova ficha para ${aluno.nome}`}</h3>
      <form onSubmit={salvar}>
        <div className="form-row">
          <label>Nome da ficha<input value={nome} onChange={(e) => setNome(e.target.value)} maxLength={80} placeholder="Ex.: Treino A — Pernas" required /></label>
          <label>Objetivo<input value={objetivo} onChange={(e) => setObjetivo(e.target.value)} maxLength={120} placeholder="Ex.: Hipertrofia" /></label>
        </div>
        <div className="itens">
          {itens.map((it, k) => (
            <div className="item" key={k}>
              <span className="n">{k + 1}</span>
              <label>Exercício
                <select value={it.exercicio_id} onChange={mudarItem(k, "exercicio_id")} required>
                  <option value="">Escolha...</option>
                  {exercicios.map((x) => <option key={x.id} value={x.id}>{x.nome}{x.grupo_muscular ? ` (${x.grupo_muscular})` : ""}</option>)}
                </select>
              </label>
              <label>Séries<input type="number" value={it.series} onChange={mudarItem(k, "series")} min="1" max="20" required /></label>
              <label>Repetições<input type="number" value={it.repeticoes} onChange={mudarItem(k, "repeticoes")} min="1" max="200" required /></label>
              <label>Carga (kg)<input type="number" value={it.carga_kg} onChange={mudarItem(k, "carga_kg")} min="0" max="1000" step="0.5" /></label>
              <label>Descanso (s)<input type="number" value={it.descanso_seg} onChange={mudarItem(k, "descanso_seg")} min="0" max="900" step="5" /></label>
              <div className="acoes">
                <button type="button" className="btn-sec" disabled={k === 0} onClick={() => mover(k, -1)} aria-label="Mover para cima">↑</button>
                <button type="button" className="btn-sec" disabled={k === itens.length - 1} onClick={() => mover(k, 1)} aria-label="Mover para baixo">↓</button>
                <button type="button" className="btn-sec perigo" disabled={itens.length === 1}
                  onClick={() => setItens(itens.filter((_, i) => i !== k))} aria-label="Remover exercício">Remover</button>
              </div>
            </div>
          ))}
        </div>
        <button type="button" className="btn-sec" onClick={() => setItens([...itens, { ...ITEM_VAZIO }])} disabled={itens.length >= 30}>
          + Adicionar exercício
        </button>
        <div className="err" role="alert">{erro}</div>
        <div className="acoes">
          <button className="btn" type="submit" disabled={enviando}>{enviando ? "Salvando..." : "Salvar ficha"}</button>
          <button className="btn-sec" type="button" onClick={onCancelar}>Cancelar</button>
        </div>
      </form>
    </section>
  );
}

function Exercicios({ exercicios, onMudou }) {
  const [editando, setEditando] = useState(null);
  const [f, setF] = useState({});
  const [erro, setErro] = useState("");

  function abrir(x) {
    setErro("");
    setEditando(x ? x.id : "novo");
    setF({ nome: x?.nome || "", grupo_muscular: x?.grupo_muscular || "", descricao: x?.descricao || "" });
  }

  async function salvar(e) {
    e.preventDefault();
    setErro("");
    try {
      if (editando === "novo") await api.post("/exercicios", f);
      else await api.put(`/exercicios/${editando}`, f);
      setEditando(null);
      onMudou();
    } catch (err) {
      setErro(mensagemErro(err));
    }
  }

  return (
    <section className="card" style={{ marginTop: 14 }}>
      <div className="card-topo">
        <h3>Exercícios ({exercicios.length})</h3>
        {editando === null && <button className="btn-sec" type="button" onClick={() => abrir(null)}>Novo exercício</button>}
      </div>
      {editando !== null && (
        <form className="form-row" onSubmit={salvar} style={{ marginBottom: 14 }}>
          <label>Nome<input value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} maxLength={120} required /></label>
          <label>Grupo muscular<input value={f.grupo_muscular} onChange={(e) => setF({ ...f, grupo_muscular: e.target.value })} maxLength={60} placeholder="Ex.: Pernas" /></label>
          <label>Descrição<input value={f.descricao} onChange={(e) => setF({ ...f, descricao: e.target.value })} maxLength={2000} /></label>
          <div className="acoes">
            <button className="btn" type="submit">Salvar</button>
            <button className="btn-sec" type="button" onClick={() => setEditando(null)}>Cancelar</button>
          </div>
        </form>
      )}
      <div className="err" role="alert">{erro}</div>
      <div className="tablewrap">
        <table className="t">
          <thead><tr><th>Exercício</th><th>Grupo muscular</th><th>Descrição</th><th></th></tr></thead>
          <tbody>
            {exercicios.map((x) => (
              <tr key={x.id}>
                <td>{x.nome}</td><td>{x.grupo_muscular || "—"}</td><td>{x.descricao || "—"}</td>
                <td><button className="btn-sec" type="button" onClick={() => abrir(x)}>Editar</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
