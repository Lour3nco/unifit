import { useEffect, useState } from "react";
import api, { mensagemErro } from "../api";

const FORMAS = [["pix", "Pix"], ["cartao", "Cartão de crédito"], ["boleto", "Boleto"]];
const STATUS = { pago: "Pago", pendente: "Pendente", atrasado: "Em atraso", cancelado: "Cancelado" };

const data = (v) => (v ? new Date(`${String(v).slice(0, 10)}T00:00:00`).toLocaleDateString("pt-BR") : "—");
const moeda = (v) => Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const hojeISO = () => new Date().toLocaleDateString("sv-SE"); // AAAA-MM-DD no fuso local

export default function MeusPagamentos() {
  const [r, setR] = useState(null);
  const [planos, setPlanos] = useState([]);
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [pagando, setPagando] = useState(null); // id do pagamento com a escolha de forma aberta
  const [forma, setForma] = useState("pix");
  const [enviando, setEnviando] = useState(false);

  const carregar = () =>
    Promise.all([api.get("/meu/resumo"), api.get("/meu/planos")])
      .then(([a, b]) => { setR(a.data); setPlanos(b.data); })
      .catch((e) => setErro(mensagemErro(e)));
  useEffect(() => { carregar(); }, []);

  async function executar(fn) {
    setErro(""); setOk("");
    setEnviando(true);
    try {
      const { data: resp } = await fn();
      setOk(resp.mensagem);
      setPagando(null);
      await carregar();
    } catch (e) {
      setErro(mensagemErro(e));
    } finally {
      setEnviando(false);
    }
  }

  if (!r) return <div className="ph">{erro || "Carregando pagamentos..."}</div>;

  const m = r.matricula;
  const vigente = m && m.status === "ativa" && (!m.fim || String(m.fim).slice(0, 10) >= hojeISO());
  const situacao = (p) => (p.status === "pendente" && String(p.vencimento).slice(0, 10) < hojeISO() ? "atrasado" : p.status);

  return (
    <>
      <div className="aviso" role="note">
        Pague na recepção ou por Pix, cartão ou boleto e clique em “Informar pagamento”. A mensalidade só
        fica como paga depois que a recepção confirmar o recebimento.
      </div>
      <div className="err" role="alert">{erro}</div>
      {ok && <div className="okmsg" role="status" style={{ marginBottom: 14 }}>{ok}</div>}

      {vigente ? (
        <div className="kpis">
          <div className="kpi"><small>Plano</small><strong>{m.plano}</strong></div>
          <div className="kpi"><small>Válido até</small><strong>{data(m.fim)}</strong></div>
        </div>
      ) : (
        <section className="card">
          <h3>{m ? "Seu plano venceu. Escolha um novo plano" : "Escolha seu plano"}</h3>
          <div className="planos">
            {planos.map((p) => (
              <div className="plano" key={p.id}>
                <strong>{p.nome}</strong>
                <span className="preco">{moeda(p.valor)}</span>
                <small>{p.duracao_dias} dias de acesso</small>
                <button className="btn" type="button" disabled={enviando}
                  onClick={() => executar(() => api.post("/meu/matricula", { plano_id: p.id }))}>
                  Contratar
                </button>
              </div>
            ))}
            {planos.length === 0 && <p className="hint">Nenhum plano disponível no momento.</p>}
          </div>
        </section>
      )}

      <section className="card" style={{ marginTop: 14 }}>
        <h3>Mensalidades</h3>
        <div className="tablewrap">
          <table className="t">
            <thead><tr><th>Vencimento</th><th>Valor</th><th>Situação</th><th>Pago em</th><th></th></tr></thead>
            <tbody>
              {r.pagamentos.map((p) => {
                const st = situacao(p);
                const aberto = st === "pendente" || st === "atrasado";
                const informado = aberto && p.informado_em;
                return (
                  <tr key={p.id}>
                    <td>{data(p.vencimento)}</td>
                    <td>{moeda(p.valor)}</td>
                    <td>{informado
                      ? <span className="chip pendente">Aguardando confirmação</span>
                      : <span className={`chip ${st}`}>{STATUS[st] || st}</span>}</td>
                    <td>{p.pago_em ? `${data(p.pago_em)}${p.forma ? ` · ${p.forma}` : ""}`
                      : informado ? <small className="hint">Informado em {new Date(p.informado_em).toLocaleDateString("pt-BR")} · {p.informado_forma}</small> : "—"}</td>
                    <td>
                      {aberto && !informado && pagando !== p.id && (
                        <button type="button" className="btn compacto" onClick={() => { setPagando(p.id); setForma("pix"); }}>
                          Informar pagamento
                        </button>
                      )}
                      {pagando === p.id && (
                        <div className="pagar">
                          <select className="compacto" value={forma} onChange={(e) => setForma(e.target.value)}
                            aria-label="Forma de pagamento">
                            {FORMAS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
                          </select>
                          <button type="button" className="btn compacto" disabled={enviando}
                            onClick={() => executar(() => api.post(`/meu/pagamentos/${p.id}/informar`, { forma }))}>
                            {enviando ? "Enviando..." : "Informar"}
                          </button>
                          <button type="button" className="btn-sec" onClick={() => setPagando(null)}>Cancelar</button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
              {r.pagamentos.length === 0 && <tr><td colSpan="5" className="vazio">Nenhuma mensalidade ainda.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
