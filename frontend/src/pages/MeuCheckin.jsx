import { useEffect, useState } from "react";
import api, { mensagemErro } from "../api";

const dia = (v) => new Date(v).toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" });
const hora = (v) => new Date(v).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

function duracao(inicio, fim) {
  const min = Math.max(0, Math.round((new Date(fim) - new Date(inicio)) / 60000));
  return min < 60 ? `${min} min` : `${Math.floor(min / 60)}h${String(min % 60).padStart(2, "0")}`;
}

export default function MeuCheckin() {
  const [r, setR] = useState(null);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [agora, setAgora] = useState(() => new Date());

  useEffect(() => {
    api.get("/meu/checkins").then((x) => setR(x.data)).catch((e) => setErro(mensagemErro(e)));
  }, []);

  useEffect(() => { // atualiza o tempo de treino enquanto o check-in está aberto
    if (!r?.aberto) return undefined;
    const id = setInterval(() => setAgora(new Date()), 30000);
    return () => clearInterval(id);
  }, [r?.aberto]);

  async function registrar(acao) {
    setErro("");
    setEnviando(true);
    try {
      const { data } = await api.post(`/meu/${acao}`);
      setR(data);
      setAgora(new Date());
    } catch (e) {
      setErro(mensagemErro(e));
    } finally {
      setEnviando(false);
    }
  }

  if (!r) return <div className="ph">{erro || "Carregando check-ins..."}</div>;
  const aberto = r.aberto;

  return (
    <>
      <section className={`card presenca ${aberto ? "dentro" : ""}`}>
        <div>
          <small>{aberto ? "Você está na academia" : "Você não está na academia"}</small>
          <strong>{aberto ? `Desde ${hora(aberto.entrada)} · ${duracao(aberto.entrada, agora)}` : "Bom treino!"}</strong>
        </div>
        <button className="btn" type="button" disabled={enviando} onClick={() => registrar(aberto ? "checkout" : "checkin")}>
          {enviando ? "Registrando..." : aberto ? "Fazer check-out" : "Fazer check-in"}
        </button>
      </section>      <div className="err" role="alert">{erro}</div>

      <section className="card">
        <h3>Últimos registros</h3>
        <div className="tablewrap">
          <table className="t">
            <thead><tr><th>Dia</th><th>Entrada</th><th>Saída</th><th>Tempo</th></tr></thead>
            <tbody>
              {r.recentes.map((c) => (
                <tr key={c.id}>
                  <td>{dia(c.entrada)}</td>
                  <td>{hora(c.entrada)}</td>
                  <td>{c.saida ? hora(c.saida) : aberto?.id === c.id ? "Em andamento" : "Sem check-out"}</td>
                  <td>{c.saida ? duracao(c.entrada, c.saida) : "—"}</td>
                </tr>
              ))}
              {r.recentes.length === 0 && <tr><td colSpan="4" className="vazio">Nenhum check-in ainda.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
