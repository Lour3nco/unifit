import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { dataHora, hojeISO, numeroOuNulo } from "../formato";

const dica = { background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 8, color: "var(--ink)" };
const eixo = { fill: "var(--mute)", fontSize: 12 };
const diaCurto = (v) => (v ? new Date(v).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }) : "—");
const kg = (v) => (v === null || v === undefined ? "—" : `${Number(v)} kg`);

// Normaliza os itens de uma ficha (equipe usa carga_kg; área do aluno usa carga) para o formulário.
export function itensParaRegistro(ficha) {
  return (ficha?.itens || [])
    .filter((i) => i.exercicio_id != null)
    .map((i) => ({
      exercicio_id: String(i.exercicio_id),
      exercicio: i.exercicio,
      series: i.series ?? "",
      repeticoes: i.repeticoes ?? "",
      carga_kg: (i.carga_kg ?? i.carga) ?? "",
    }));
}

// ---- Formulário: registrar o que foi feito numa sessão ----
export function FormSessao({ treinos, onSalvar, onCancelar }) {
  const comId = (treinos || []).filter((t) => (t.itens || []).some((i) => i.exercicio_id != null));
  const [treinoId, setTreinoId] = useState(comId[0]?.id ? String(comId[0].id) : "");
  const [data, setData] = useState(hojeISO());
  const [observacao, setObservacao] = useState("");
  const [itens, setItens] = useState(() => itensParaRegistro(comId[0]));
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  function trocarTreino(id) {
    setTreinoId(id);
    setItens(itensParaRegistro(comId.find((t) => String(t.id) === String(id))));
  }
  const mudar = (k, campo) => (e) => setItens(itens.map((it, i) => (i === k ? { ...it, [campo]: e.target.value } : it)));

  async function enviar(e) {
    e.preventDefault();
    setErro("");
    if (!treinoId) return setErro("Escolha um treino.");
    setEnviando(true);
    const corpo = {
      treino_id: Number(treinoId),
      data: data || null,
      observacao: observacao.trim() || null,
      itens: itens.map((i) => ({
        exercicio_id: Number(i.exercicio_id),
        series: numeroOuNulo(i.series),
        repeticoes: numeroOuNulo(i.repeticoes),
        carga_kg: numeroOuNulo(i.carga_kg),
      })),
    };
    try {
      await onSalvar(corpo);
    } catch (err) {
      setErro(err);
      setEnviando(false);
    }
  }

  if (comId.length === 0) {
    return <div className="ph">É preciso ter uma ficha de treino com exercícios para registrar a execução.</div>;
  }

  return (
    <section className="card" style={{ marginBottom: 14 }}>
      <h3>Registrar treino feito</h3>
      <form onSubmit={enviar}>
        <div className="form-row">
          <label>Ficha
            <select value={treinoId} onChange={(e) => trocarTreino(e.target.value)} required>
              {comId.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
            </select>
          </label>
          <label>Data<input type="date" value={data} max={hojeISO()} onChange={(e) => setData(e.target.value)} /></label>
        </div>
        <div className="itens">
          {itens.map((it, k) => (
            <div className="item" key={k}>
              <span className="n">{k + 1}</span>
              <label>Exercício<input value={it.exercicio || ""} disabled /></label>
              <label>Séries feitas<input type="number" value={it.series} onChange={mudar(k, "series")} min="0" max="50" /></label>
              <label>Repetições<input type="number" value={it.repeticoes} onChange={mudar(k, "repeticoes")} min="0" max="500" /></label>
              <label>Carga (kg)<input type="number" value={it.carga_kg} onChange={mudar(k, "carga_kg")} min="0" max="1000" step="0.5" /></label>
            </div>
          ))}
        </div>
        <label>Observação<input value={observacao} onChange={(e) => setObservacao(e.target.value)} maxLength={500} placeholder="Como foi o treino? (opcional)" /></label>
        <div className="err" role="alert">{erro}</div>
        <div className="acoes">
          <button className="btn" type="submit" disabled={enviando}>{enviando ? "Salvando..." : "Salvar registro"}</button>
          <button className="btn-sec" type="button" onClick={onCancelar}>Cancelar</button>
        </div>
      </form>
    </section>
  );
}

// ---- Histórico de sessões registradas ----
export function HistoricoSessoes({ sessoes, onExcluir }) {
  if (!sessoes) return <div className="ph">Carregando histórico...</div>;
  if (sessoes.length === 0) return <div className="ph">Nenhum treino registrado ainda.</div>;
  return (
    <div className="itens">
      {sessoes.map((s) => (
        <section className="card" key={s.id} style={{ padding: 14 }}>
          <div className="card-topo">
            <div>
              <strong>{s.treino || "Treino"}</strong>{" "}
              <span className="hint">{dataHora(s.data)}</span>
            </div>
            {onExcluir && <button className="btn-sec perigo" type="button" onClick={() => onExcluir(s.id)}>Excluir</button>}
          </div>
          <div className="tablewrap">
            <table className="t">
              <thead><tr><th>Exercício</th><th>Séries</th><th>Repetições</th><th>Carga</th></tr></thead>
              <tbody>
                {s.itens.map((i, k) => (
                  <tr key={k}>
                    <td>{i.exercicio}{i.grupo_muscular && <small className="hint"> · {i.grupo_muscular}</small>}</td>
                    <td>{i.series ?? "—"}</td><td>{i.repeticoes ?? "—"}</td><td>{kg(i.carga_kg)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {s.observacao && <p className="hint" style={{ margin: "10px 0 0" }}>“{s.observacao}”</p>}
        </section>
      ))}
    </div>
  );
}

// ---- Performance por mês (volume total treinado e nº de treinos) ----
const fmtKg = (v) => `${Math.round(v).toLocaleString("pt-BR")} kg`;
const rotuloMes = (ym) => {
  const [y, m] = ym.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("pt-BR", { month: "short", year: "2-digit" }).replace(". de ", "/").replace(".", "");
};

function porMes(sessoes) {
  const mapa = new Map(); // "AAAA-MM" -> { mes, rotulo, sessoes, volume }
  for (const s of sessoes) {
    const d = new Date(s.data);
    const ym = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const reg = mapa.get(ym) || { mes: ym, rotulo: rotuloMes(ym), sessoes: 0, volume: 0 };
    reg.sessoes += 1;
    for (const i of s.itens) {
      if (i.series && i.repeticoes && i.carga_kg != null) reg.volume += i.series * i.repeticoes * Number(i.carga_kg);
    }
    mapa.set(ym, reg);
  }
  return [...mapa.values()].sort((a, b) => a.mes.localeCompare(b.mes));
}

export function ResumoMensal({ sessoes }) {
  const dados = useMemo(() => porMes(sessoes || []), [sessoes]);
  if (!sessoes || sessoes.length === 0) return null;
  const agora = new Date();
  const ymAtual = `${agora.getFullYear()}-${String(agora.getMonth() + 1).padStart(2, "0")}`;
  const atual = dados.find((d) => d.mes === ymAtual) || { sessoes: 0, volume: 0 };
  const mediaVol = atual.sessoes ? atual.volume / atual.sessoes : 0;
  return (
    <section className="card" style={{ marginBottom: 14 }}>
      <h3>Performance por mês</h3>
      <div className="mini-kpis" style={{ marginBottom: 14 }}>
        <div><small>Treinos neste mês</small><strong>{atual.sessoes}</strong></div>
        <div><small>Volume neste mês</small><strong>{fmtKg(atual.volume)}</strong></div>
        <div><small>Média por treino</small><strong>{fmtKg(mediaVol)}</strong></div>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={dados} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--line)" />
          <XAxis dataKey="rotulo" tick={eixo} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={eixo} axisLine={false} tickLine={false} width={48}
            tickFormatter={(v) => (v >= 1000 ? `${(v / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}k` : `${v}`)} />
          <Tooltip cursor={{ fill: "var(--bg)" }} contentStyle={dica}
            formatter={(v, _n, p) => [`${fmtKg(v)} · ${p.payload.sessoes} treino(s)`, "Volume"]} />
          <Bar dataKey="volume" name="Volume" fill="var(--acc)" radius={[4, 4, 0, 0]} maxBarSize={48} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <p className="hint" style={{ margin: "10px 0 0" }}>Volume = soma de séries × repetições × carga registradas em cada treino.</p>
    </section>
  );
}

// ---- Gráfico de evolução por exercício ----
function variacao(pontos) {
  const comCarga = pontos.filter((p) => p.carga_kg != null);
  if (comCarga.length < 2) return null;
  const ini = comCarga[0].carga_kg;
  const fim = comCarga[comCarga.length - 1].carga_kg;
  if (!ini) return { ini, fim, pct: null };
  return { ini, fim, pct: Math.round(((fim - ini) / ini) * 100) };
}

function CartaoExercicio({ ex }) {
  const dados = useMemo(
    () => ex.pontos.filter((p) => p.carga_kg != null).map((p) => ({ dia: diaCurto(p.data), carga: p.carga_kg })),
    [ex.pontos],
  );
  const v = variacao(ex.pontos);
  return (
    <section className="card" style={{ marginBottom: 14 }}>
      <div className="card-topo">
        <h3 style={{ margin: 0 }}>{ex.exercicio}{ex.grupo_muscular && <small className="hint"> · {ex.grupo_muscular}</small>}</h3>
        <span className="hint">{ex.pontos.length} registro(s)</span>
      </div>
      {v && (
        <p className="hint" style={{ margin: "-6px 0 12px" }}>
          Carga: {kg(v.ini)} → {kg(v.fim)}{" "}
          {v.pct != null && <strong style={{ color: v.pct >= 0 ? "var(--ok)" : "var(--risk)" }}>({v.pct >= 0 ? "+" : ""}{v.pct}%)</strong>}
        </p>
      )}
      {dados.length >= 2 ? (
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={dados} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--line)" />
            <XAxis dataKey="dia" tick={eixo} axisLine={false} tickLine={false} interval="preserveStartEnd" />
            <YAxis tick={eixo} axisLine={false} tickLine={false} width={48} tickFormatter={(v2) => `${v2}`} />
            <Tooltip contentStyle={dica} formatter={(val) => [`${val} kg`, "Carga"]} />
            <Line type="monotone" dataKey="carga" stroke="var(--acc)" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <p className="hint">Registre a carga em pelo menos duas sessões para ver o gráfico de evolução.</p>
      )}
    </section>
  );
}

export function GraficoEvolucao({ evolucao }) {
  if (!evolucao) return <div className="ph">Carregando evolução...</div>;
  if (evolucao.length === 0) return <div className="ph">Sem dados de evolução ainda. Registre os treinos feitos para acompanhar o progresso.</div>;
  return <>{evolucao.map((ex) => <CartaoExercicio key={ex.exercicio_id} ex={ex} />)}</>;
}
