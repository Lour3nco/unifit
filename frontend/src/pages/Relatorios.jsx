import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import api, { mensagemErro } from "../api";
import { data, dataHora, moeda } from "../formato";

const SITUACOES = [["ativa", "Ativas"], ["vencida", "Vencidas"], ["trancada", "Trancadas"], ["encerrada", "Encerradas"], ["cancelada", "Canceladas"]];
const MES = (m) => new Date(`${m}-01T00:00:00`).toLocaleDateString("pt-BR", { month: "short", year: "2-digit" }).replace(". de ", "/");
const corRisco = (p) => (p >= 70 ? "var(--risk)" : p >= 55 ? "var(--warn)" : "var(--acc)");
const dica = { background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 8, color: "var(--ink)" };
const eixo = { fill: "var(--mute)", fontSize: 12 };

// gráfico de barras de uma série só: o título do card nomeia a série, sem legenda
function Barras({ dados, x, y, nome, formato = (v) => v, altura = 220 }) {
  return (
    <ResponsiveContainer width="100%" height={altura}>
      <BarChart data={dados} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--line)" />
        <XAxis dataKey={x} tick={eixo} axisLine={false} tickLine={false} interval="preserveStartEnd" />
        <YAxis tick={eixo} axisLine={false} tickLine={false} width={56} tickFormatter={formato} allowDecimals={false} />
        <Tooltip cursor={{ fill: "var(--bg)" }} contentStyle={dica} formatter={(v) => [formato(v), nome]} />
        <Bar dataKey={y} name={nome} fill="var(--acc)" radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export default function Relatorios() {
  const [meses, setMeses] = useState(6);
  const [r, setR] = useState(null);
  const [erro, setErro] = useState("");
  const [msg, setMsg] = useState("");
  const [calculando, setCalculando] = useState(false);

  const carregar = () => api.get("/relatorios", { params: { meses } }).then((x) => setR(x.data)).catch((e) => setErro(mensagemErro(e)));
  useEffect(() => { carregar(); }, [meses]);

  async function calcularEvasao() {
    setErro(""); setMsg("");
    setCalculando(true);
    try {
      const { data: x } = await api.post("/relatorios/evasao", null, { timeout: 5 * 60 * 1000 });
      setMsg(x.mensagem);
      await carregar();
    } catch (e) {
      setErro(mensagemErro(e));
    } finally {
      setCalculando(false);
    }
  }

  if (!r) return <div className="ph">{erro || "Montando relatórios..."}</div>;

  const mensal = r.mensal.map((m) => ({ ...m, rotulo: MES(m.mes) }));
  const totalReceita = r.mensal.reduce((s, m) => s + m.receita, 0);
  const totalNovas = r.mensal.reduce((s, m) => s + m.novas_matriculas, 0);
  const totalRetornos = r.mensal.reduce((s, m) => s + m.retornos, 0);
  const totalVigentes = r.por_plano.reduce((s, p) => s + p.alunos, 0);

  return (
    <>
      <div className="toolbar">
        <label className="inline">Período
          <select value={meses} onChange={(e) => setMeses(Number(e.target.value))}>
            <option value={3}>Últimos 3 meses</option><option value={6}>Últimos 6 meses</option><option value={12}>Últimos 12 meses</option>
          </select>
        </label>
      </div>
      <div className="err" role="alert">{erro}</div>

      <div className="kpis">
        <div className="kpi"><small>Receita no período</small><strong>{moeda(totalReceita)}</strong></div>
        <div className="kpi" title="Primeira matrícula de cada aluno. Renovações não contam.">
          <small>Novos alunos</small><strong>{totalNovas}</strong>
          {totalRetornos > 0 && <em>+ {totalRetornos} ex-aluno(s) voltaram</em>}</div>
        <div className="kpi"><small>Alunos com plano vigente</small><strong>{totalVigentes}</strong></div>
        <div className="kpi"><small>Check-ins no período</small><strong>{r.frequencia.total}</strong></div>
      </div>

      <div className="grid2" style={{ marginTop: 14 }}>
        <section className="card"><h3>Receita recebida por mês</h3>
          <Barras dados={mensal} x="rotulo" y="receita" nome="Receita" formato={(v) => moeda(v).replace(",00", "")} /></section>
        <section className="card"><h3>Novos alunos por mês</h3>
          <Barras dados={mensal} x="rotulo" y="novas_matriculas" nome="Novos alunos" /></section>
        <section className="card"><h3>Check-ins por dia da semana</h3>
          <Barras dados={r.frequencia.por_dia} x="dia" y="total" nome="Check-ins" /></section>
        <section className="card"><h3>Check-ins por horário de entrada</h3>
          <Barras dados={r.frequencia.por_hora} x="hora" y="total" nome="Check-ins" /></section>
      </div>

      <div className="grid2" style={{ marginTop: 14 }}>
        <section className="card">
          <h3>Matrículas por situação</h3>
          <div className="mini-kpis">
            {SITUACOES.map(([k, n]) => <div key={k}><small>{n}</small><strong>{r.situacao_matriculas[k] || 0}</strong></div>)}
          </div>
        </section>
        <section className="card">
          <h3>Planos vigentes</h3>
          <div className="tablewrap">
            <table className="t">
              <thead><tr><th>Plano</th><th>Alunos</th><th>Valor somado</th></tr></thead>
              <tbody>
                {r.por_plano.map((p) => <tr key={p.plano}><td>{p.plano}</td><td>{p.alunos}</td><td>{moeda(p.receita_ciclo)}</td></tr>)}
                {r.por_plano.length === 0 && <tr><td colSpan="3" className="vazio">Nenhum plano vigente.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section className="card" style={{ marginTop: 14 }}>
        <div className="card-topo">
          <div>
            <h3>Risco de evasão</h3>
            <small className="hint">{r.evasao.data ? `Último cálculo em ${data(r.evasao.data)}` : "Ainda não calculado."} Usa frequência
              (proporcional ao tempo de casa), dias sem treinar, atrasos, tempo de casa e valor mensal do plano de cada aluno com plano vigente.</small>
          </div>
          <button className="btn" type="button" onClick={calcularEvasao} disabled={calculando}>
            {calculando ? "Calculando..." : "Calcular agora"}</button>
        </div>
        {msg && <div className="okmsg" role="status" style={{ marginBottom: 8 }}>{msg}</div>}
        <ul className="risk">
          {r.evasao.alunos.map((a) => (
            <li key={a.aluno_id}>
              <span>{a.aluno} <small className="hint">· {a.numero_matricula}</small></span>
              <span className="p">{a.probabilidade}%</span>
              <div className="meter"><i style={{ width: `${a.probabilidade}%`, background: corRisco(a.probabilidade) }} /></div>
            </li>
          ))}
          {r.evasao.data && r.evasao.alunos.length === 0 && <li className="hint">Nenhum aluno analisado.</li>}
        </ul>
      </section>

      <div className="grid2" style={{ marginTop: 14 }}>
        <section className="card">
          <h3>Inadimplentes ({r.inadimplentes.length})</h3>
          <div className="tablewrap">
            <table className="t">
              <thead><tr><th>Aluno</th><th>Mensalidades</th><th>Total</th><th>Desde</th></tr></thead>
              <tbody>
                {r.inadimplentes.map((i) => (
                  <tr key={i.aluno_id}><td>{i.aluno}<small className="hint"> · {i.numero_matricula}</small></td>
                    <td>{i.mensalidades}</td><td>{moeda(i.total)}</td><td>{data(i.desde)}</td></tr>
                ))}
                {r.inadimplentes.length === 0 && <tr><td colSpan="4" className="vazio">Nenhuma mensalidade em atraso.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
        <section className="card">
          <h3>Sem treinar há 14 dias ou mais ({r.sumidos.length})</h3>
          <div className="tablewrap">
            <table className="t">
              <thead><tr><th>Aluno</th><th>Último check-in</th><th>Dias</th></tr></thead>
              <tbody>
                {r.sumidos.map((s) => (
                  <tr key={s.aluno_id}><td>{s.aluno}<small className="hint"> · {s.numero_matricula}</small></td>
                    <td>{s.ultimo_checkin ? dataHora(s.ultimo_checkin) : "Nunca"}</td><td>{s.dias ?? "—"}</td></tr>
                ))}
                {r.sumidos.length === 0 && <tr><td colSpan="3" className="vazio">Todos os alunos com plano vigente treinaram nos últimos 14 dias.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </>
  );
}
