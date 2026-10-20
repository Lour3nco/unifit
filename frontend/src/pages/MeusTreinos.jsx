import { useEffect, useState } from "react";
import api, { mensagemErro } from "../api";
import { FormSessao, GraficoEvolucao, HistoricoSessoes, ResumoMensal } from "../components/Evolucao.jsx";

const vazio = (v) => (v === null || v === undefined || v === "" ? "—" : v);

export default function MeusTreinos() {
  const [aba, setAba] = useState("treinos"); // treinos | evolucao
  const [r, setR] = useState(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api.get("/meu/treinos").then((x) => setR(x.data)).catch((e) => setErro(mensagemErro(e)));
  }, []);

  if (erro) return <div className="ph">{erro}</div>;
  if (!r) return <div className="ph">Carregando seus treinos...</div>;

  return (
    <>
      {!r.vinculado && (
        <div className="aviso" role="status">
          Salve seus dados em “Meus dados” para liberar seus treinos.
        </div>
      )}

      {r.vinculado && (
        <div className="abas" role="tablist" aria-label="Treinos ou evolução">
          <button type="button" role="tab" aria-selected={aba === "treinos"} onClick={() => setAba("treinos")}>Meus treinos</button>
          <button type="button" role="tab" aria-selected={aba === "evolucao"} onClick={() => setAba("evolucao")}>Minha evolução</button>
        </div>
      )}

      {aba === "treinos" ? <Fichas r={r} /> : <MinhaEvolucao treinos={r.treinos} />}
    </>
  );
}

function Fichas({ r }) {
  return (
    <>
      {r.vinculado && r.treinos.length === 0 && (
        <div className="ph">Você ainda não tem treino montado. Peça ao seu instrutor.</div>
      )}
      {r.treinos.map((t) => (
        <section className="card" key={t.id} style={{ marginBottom: 14 }}>
          <h3>{t.nome}</h3>
          {t.objetivo && <p className="hint" style={{ margin: "-8px 0 12px" }}>Objetivo: {t.objetivo}</p>}
          <div className="tablewrap">
            <table className="t">
              <thead><tr><th>Exercício</th><th>Séries</th><th>Repetições</th><th>Carga</th><th>Descanso</th></tr></thead>
              <tbody>
                {t.itens.map((i, k) => (
                  <tr key={k}><td>{vazio(i.exercicio)}</td><td>{vazio(i.series)}</td><td>{vazio(i.repeticoes)}</td>
                    <td>{i.carga != null ? `${Number(i.carga)} kg` : "—"}</td>
                    <td>{i.descanso != null ? `${i.descanso}s` : "—"}</td></tr>
                ))}
                {t.itens.length === 0 && <tr><td colSpan="5" className="vazio">Este treino ainda não tem exercícios.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </>
  );
}

function MinhaEvolucao({ treinos }) {
  const [sessoes, setSessoes] = useState(null);
  const [evolucao, setEvolucao] = useState(null);
  const [registrando, setRegistrando] = useState(false);
  const [erro, setErro] = useState("");

  const carregar = () => {
    api.get("/meu/sessoes").then((r) => setSessoes(r.data)).catch((e) => setErro(mensagemErro(e)));
    api.get("/meu/evolucao").then((r) => setEvolucao(r.data)).catch((e) => setErro(mensagemErro(e)));
  };
  useEffect(carregar, []);

  async function salvar(corpo) {
    try {
      const { data: r } = await api.post(`/meu/treinos/${corpo.treino_id}/sessoes`, corpo);
      setSessoes(r);
      setRegistrando(false);
      api.get("/meu/evolucao").then((x) => setEvolucao(x.data));
    } catch (e) {
      throw mensagemErro(e);
    }
  }

  async function excluir(id) {
    setErro("");
    try {
      await api.delete(`/meu/sessoes/${id}`);
      carregar();
    } catch (e) {
      setErro(mensagemErro(e));
    }
  }

  return (
    <>
      <div className="toolbar" style={{ marginTop: 14 }}>
        {!registrando && <button className="btn" type="button" onClick={() => setRegistrando(true)}>Registrar treino de hoje</button>}
        <div className="err" role="alert">{erro}</div>
      </div>
      {registrando && <FormSessao treinos={treinos || []} onSalvar={salvar} onCancelar={() => setRegistrando(false)} />}
      <ResumoMensal sessoes={sessoes} />
      <h3 style={{ margin: "18px 0 10px" }}>Evolução por exercício</h3>
      <GraficoEvolucao evolucao={evolucao} />
      <h3 style={{ margin: "18px 0 10px" }}>Histórico de sessões</h3>
      <HistoricoSessoes sessoes={sessoes} onExcluir={excluir} />
    </>
  );
}
