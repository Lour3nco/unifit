import { useEffect, useState } from "react";
import api, { mensagemErro } from "../api";
import BuscaAluno from "../components/BuscaAluno.jsx";
import { hora } from "../formato";

export default function CheckinRecepcao() {
  const [r, setR] = useState(null);
  const [erro, setErro] = useState("");
  const [msg, setMsg] = useState("");
  const [aviso, setAviso] = useState("");
  const [versao, setVersao] = useState(0);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api.get("/checkins/hoje").then((x) => setR(x.data)).catch((e) => setErro(mensagemErro(e)));
  }, []);

  async function registrar(aluno_id, nome, saida) {
    setErro(""); setMsg(""); setAviso("");
    setEnviando(true);
    try {
      const { data } = await api.post(saida ? "/checkins/saida" : "/checkins", { aluno_id });
      setR(data);
      setMsg(`${saida ? "Check-out" : "Check-in"} de ${nome} registrado.`);
      if (data.aviso) setAviso(`${nome}: ${data.aviso}`);
      setVersao((v) => v + 1);
    } catch (e) {
      setErro(mensagemErro(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <div className="kpis">
        <div className="kpi"><small>Na academia agora</small><strong>{r ? r.presentes : "—"}</strong></div>
        <div className="kpi"><small>Check-ins hoje</small><strong>{r ? r.total : "—"}</strong></div>
      </div>

      <section className="card" style={{ marginTop: 14 }}>
        <h3>Registrar entrada ou saída</h3>
        <BuscaAluno versao={versao} acao={(a) => (
          <div className="acoes">
            {!a.vigente && !a.na_academia && <small className="down">sem plano ativo</small>}
            {a.na_academia
              ? <button type="button" className="btn-sec" disabled={enviando} onClick={() => registrar(a.id, a.nome, true)}>Check-out</button>
              : <button type="button" className="btn compacto" disabled={enviando || !a.vigente}
                  title={a.vigente ? undefined : "Faça uma nova matrícula antes do check-in"}
                  onClick={() => registrar(a.id, a.nome, false)}>Check-in</button>}
          </div>
        )} />
        <div className="err" role="alert">{erro}</div>
        {msg && <div className="okmsg" role="status">{msg}</div>}
        {aviso && <div className="aviso" role="alert" style={{ marginTop: 8, marginBottom: 0 }}>{aviso}</div>}
      </section>

      <section className="card" style={{ marginTop: 14 }}>
        <h3>Movimento de hoje</h3>
        <div className="tablewrap">
          <table className="t">
            <thead><tr><th>Aluno</th><th>Entrada</th><th>Saída</th><th></th></tr></thead>
            <tbody>
              {(r?.registros || []).map((c) => (
                <tr key={c.id}>
                  <td>{c.aluno}</td><td>{hora(c.entrada)}</td>
                  <td>{c.saida ? hora(c.saida) : c.aberto ? <span className="chip ativa">Na academia</span> : "Sem check-out"}</td>
                  <td>{c.aberto && (
                    <button type="button" className="btn-sec" disabled={enviando} onClick={() => registrar(c.aluno_id, c.aluno, true)}>Check-out</button>
                  )}</td>
                </tr>
              ))}
              {r && r.registros.length === 0 && <tr><td colSpan="4" className="vazio">Nenhum check-in hoje.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
