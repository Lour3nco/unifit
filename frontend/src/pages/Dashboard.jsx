import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import api, { mensagemErro } from "../api";
import { useAuth } from "../auth.jsx";

const brl = (v) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const cor = (p) => (p >= 70 ? "var(--risk)" : p >= 55 ? "var(--warn)" : "var(--acc)");

export default function Dashboard() {
  const { usuario } = useAuth();
  const [d, setD] = useState(null);
  const [erro, setErro] = useState("");
  const [bench, setBench] = useState(null);
  const [erroBench, setErroBench] = useState("");
  // mesmo acesso do backend; o benchmark só existe quando BENCHMARK_ATIVO=true no servidor
  const verBench = ["administrador", "instrutor"].includes(usuario.perfil) && !!d?.benchmark_ativo;

  useEffect(() => {
    api.get("/dashboard")
      .then((r) => setD(r.data))
      .catch((e) => setErro(mensagemErro(e, "Não foi possível carregar o dashboard.")));
  }, []);

  useEffect(() => {
    if (!verBench) return;
    api.get("/dashboard/benchmark")
      .then((r) => setBench(r.data))
      .catch((e) => setErroBench(mensagemErro(e, "Não foi possível calcular o benchmark.")));
  }, [verBench]);

  if (erro) return <div className="ph">{erro}</div>;
  if (!d) return <div className="ph">Carregando indicadores...</div>;

  const maxBench = bench ? Math.max(...Object.values(bench)) : 1;

  return (
    <>
      <div className="kpis">
        <div className="kpi"><small>Alunos ativos</small><strong>{d.alunos_ativos}</strong></div>
        <div className="kpi"><small>Receita do mês</small><strong>{brl(d.receita_mes)}</strong></div>
        <div className="kpi" title="Alunos com matrícula ativa que têm alguma mensalidade vencida e não paga">
          <small>Inadimplência</small><strong>{d.inadimplencia_pct}%</strong>
          <em className="down">dos alunos ativos · {d.pagamentos_atrasados} mensalidade(s) em atraso</em></div>
        <div className="kpi"><small>Check-ins hoje</small><strong>{d.checkins_hoje}</strong></div>
      </div>

      <div className="grid">
        <section className="card">
          <h3>Check-ins nos últimos 7 dias</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={d.checkins_por_dia}>
              <CartesianGrid vertical={false} stroke="var(--line)" />
              <XAxis dataKey="dia" tick={{ fill: "var(--mute)", fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "var(--mute)", fontSize: 12 }} axisLine={false} tickLine={false} width={32} />
              <Tooltip cursor={{ fill: "var(--bg)" }} />
              <Bar dataKey="total" name="Check-ins" fill="var(--acc)" radius={[5, 5, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </section>

        <section className="card">
          <h3>Alunos em risco de evasão</h3>
          <ul className="risk">
            {d.alunos_em_risco.map((a) => (
              <li key={a.id}>
                <span>{a.nome}</span>
                <span className="p" style={{ color: cor(a.probabilidade) }}>{a.probabilidade}%</span>
                <div className="meter"><i style={{ width: `${a.probabilidade}%`, background: cor(a.probabilidade) }} /></div>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {verBench && <section className="card" style={{ marginTop: 14 }}>
        <h3>Velocidade de inferência (100 mil alunos) · IA em {d.dispositivo_ia.toUpperCase()}</h3>
        {erroBench ? <p className="hint">{erroBench}</p> : bench ? (
          <div className="bench">
            {Object.entries(bench).map(([nome, seg]) => (
              <div className="row" key={nome}>
                <span>{nome.toUpperCase()}</span>
                <i style={{ width: `${Math.max((seg / maxBench) * 100, 3)}%`, background: nome === "cuda" ? "var(--ok)" : "var(--mute)" }} />
                <span>{(seg * 1000).toFixed(1)} ms</span>
              </div>
            ))}
          </div>
        ) : <p className="hint">Calculando benchmark...</p>}
      </section>}
    </>
  );
}
