import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import api, { mensagemErro } from "../api";
import BuscaAluno from "../components/BuscaAluno.jsx";
import { dataHora } from "../formato";

// ordem fixa das séries (cores validadas para fundo claro e escuro em styles.css)
const SERIES = [["joelho", "Joelho", "var(--s1)"], ["quadril", "Quadril", "var(--s2)"],
  ["cotovelo", "Cotovelo", "var(--s3)"], ["tronco", "Inclinação do tronco", "var(--s4)"]];
const NOMES = { joelho: "Joelho", quadril: "Quadril", cotovelo: "Cotovelo", tronco: "Inclinação do tronco",
  joelho_esq: "Joelho esq.", joelho_dir: "Joelho dir.", quadril_esq: "Quadril esq.", quadril_dir: "Quadril dir.",
  cotovelo_esq: "Cotovelo esq.", cotovelo_dir: "Cotovelo dir." };

export default function Postura() {
  const [aluno, setAluno] = useState(null);
  const [exercicios, setExercicios] = useState([]);
  const [exercicioId, setExercicioId] = useState("");
  const [video, setVideo] = useState(null);
  const [etapa, setEtapa] = useState(""); // texto de progresso enquanto envia/analisa
  const [erro, setErro] = useState("");
  const [sessao, setSessao] = useState(null);
  const [historico, setHistorico] = useState([]);

  useEffect(() => {
    api.get("/exercicios").then((r) => setExercicios(r.data)).catch((e) => setErro(mensagemErro(e)));
  }, []);

  const carregarHistorico = (id) =>
    api.get("/postura", { params: { aluno_id: id } }).then((r) => setHistorico(r.data)).catch(() => setHistorico([]));

  // a análise roda numa fila no servidor: enquanto estiver "processando", consulta o resultado a cada 3 s
  const processando = sessao?.status === "processando";
  useEffect(() => {
    if (!processando) return undefined;
    const id = setInterval(() => {
      api.get(`/postura/${sessao.id}`).then((r) => {
        if (r.data.status === "processando") return;
        setSessao(r.data);
        carregarHistorico(r.data.aluno_id);
      }).catch(() => { /* tenta de novo no próximo intervalo */ });
    }, 3000);
    return () => clearInterval(id);
  }, [processando, sessao?.id]);

  function escolher(a) {
    setAluno(a);
    setSessao(null);
    carregarHistorico(a.id);
  }

  async function analisar(e) {
    e.preventDefault();
    setErro(""); setSessao(null);
    const corpo = new FormData();
    corpo.append("aluno_id", aluno.id);
    corpo.append("exercicio_id", exercicioId);
    corpo.append("video", video);
    setEtapa("Enviando vídeo... 0%");
    try {
      const { data } = await api.post("/postura", corpo, {
        timeout: 10 * 60 * 1000,
        onUploadProgress: (p) => {
          const pct = p.total ? Math.round((p.loaded / p.total) * 100) : 0;
          setEtapa(pct < 100 ? `Enviando vídeo... ${pct}%` : "Colocando o vídeo na fila...");
        },
      });
      setSessao(data);
      carregarHistorico(aluno.id);
    } catch (err) {
      setErro(mensagemErro(err, "Não foi possível analisar o vídeo."));
    } finally {
      setEtapa("");
    }
  }

  async function abrir(id) {
    setErro("");
    try {
      const { data } = await api.get(`/postura/${id}`);
      setSessao(data);
    } catch (err) {
      setErro(mensagemErro(err));
    }
  }

  return (
    <>
      <section className="card">
        <h3>Nova análise</h3>
        {!aluno ? (
          <BuscaAluno rotulo="Escolha o aluno" acao={(a) => <button type="button" className="btn-sec" onClick={() => escolher(a)}>Selecionar</button>} />
        ) : (
          <form className="form-row" onSubmit={analisar}>
            <div className="selecionado">
              <small>Aluno</small><strong>{aluno.nome}</strong>
              <button type="button" className="linkbtn" onClick={() => { setAluno(null); setSessao(null); }}>Trocar</button>
            </div>
            <label>Exercício
              <select value={exercicioId} onChange={(e) => setExercicioId(e.target.value)} required>
                <option value="">Escolha...</option>
                {exercicios.map((x) => <option key={x.id} value={x.id}>{x.nome}</option>)}
              </select>
            </label>
            <label>Vídeo
              <input type="file" accept="video/*" onChange={(e) => setVideo(e.target.files[0] || null)} required />
            </label>
            <button className="btn" type="submit" disabled={!!etapa}>{etapa ? "Enviando..." : "Analisar"}</button>
          </form>
        )}
        {etapa && <p className="hint" role="status">{etapa}</p>}
        <div className="err" role="alert">{erro}</div>
        <p className="hint">Dica: filme de lado, com o corpo inteiro no quadro, câmera parada e boa luz. Até 100 MB; são analisados até 60 quadros.</p>
      </section>

      {sessao && <Resultado s={sessao} />}

      {aluno && (
        <section className="card" style={{ marginTop: 14 }}>
          <h3>Histórico de {aluno.nome}</h3>
          <div className="tablewrap">
            <table className="t">
              <thead><tr><th>Data</th><th>Exercício</th><th>Vídeo</th><th>Repetições</th><th>Alertas</th><th></th></tr></thead>
              <tbody>
                {historico.map((h) => (
                  <tr key={h.id}>
                    <td>{dataHora(h.criado_em)}</td><td>{h.exercicio}</td><td>{h.video_nome}</td>
                    {h.status === "concluida"
                      ? <><td>{h.repeticoes ?? "—"}</td><td>{h.alertas}</td></>
                      : <td colSpan="2"><span className={`chip ${h.status === "erro" ? "atrasado" : "pendente"}`}>
                          {h.status === "erro" ? "Erro" : "Processando"}</span></td>}
                    <td><button className="btn-sec" type="button" onClick={() => abrir(h.id)}>Ver</button></td>
                  </tr>
                ))}
                {historico.length === 0 && <tr><td colSpan="6" className="vazio">Nenhuma análise ainda.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}

function Resultado({ s }) {
  if (s.status !== "concluida") {
    return (
      <section className="card" style={{ marginTop: 14 }} role="status">
        <h3>{s.exercicio} · {s.aluno} · {dataHora(s.criado_em)}</h3>
        {s.status === "erro"
          ? <div className="err">{s.erro || "Não foi possível analisar o vídeo."}</div>
          : <p className="hint">Analisando com IA... em CPU pode levar até 1 minuto (mais se houver outros vídeos na fila).
              Pode sair desta tela: o resultado fica no histórico.</p>}
      </section>
    );
  }
  const r = s.resultado;
  const p = r.resumo[r.articulacao_principal];
  const series = SERIES.filter(([k]) => r.serie.some((q) => q[k] != null));
  const linhas = Object.entries(r.resumo).filter(([k]) => NOMES[k]);

  return (
    <section className="card" style={{ marginTop: 14 }}>
      <h3>{s.exercicio} · {s.aluno} · {dataHora(s.criado_em)}</h3>
      <div className="kpis">
        <div className="kpi"><small>Repetições</small><strong>{r.repeticoes}</strong></div>
        <div className="kpi"><small>{NOMES[r.articulacao_principal]} (mín. → máx.)</small>
          <strong>{p ? `${Math.round(p.min)}° → ${Math.round(p.max)}°` : "—"}</strong></div>
        <div className="kpi"><small>Pessoa detectada</small><strong>{r.quadros_com_pessoa}/{r.quadros_analisados}</strong>
          <em>quadros</em></div>
        <div className="kpi"><small>Velocidade da IA ({r.dispositivo.toUpperCase()})</small>
          <strong>{s.fps_processado ?? "—"} fps</strong><em>vídeo original a {s.fps_original} fps</em></div>
      </div>

      <div className="alertas">
        {r.alertas.length === 0
          ? <p className="alerta ok"><b aria-hidden="true">✓</b> Nenhum problema evidente nos ângulos medidos.</p>
          : r.alertas.map((a) => <p className="alerta" key={a}><b aria-hidden="true">!</b> {a}</p>)}
        <p className="hint">Leitura automática para apoiar o instrutor, não substitui a avaliação presencial.</p>
      </div>

      <div className="grid">
        <div>
          <h4>Ângulos ao longo do vídeo</h4>
          {series.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={r.serie} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--line)" />
                <XAxis dataKey="t" tickFormatter={(t) => `${t}s`} tick={{ fill: "var(--mute)", fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 180]} ticks={[0, 45, 90, 135, 180]} tickFormatter={(v) => `${v}°`} width={40}
                  tick={{ fill: "var(--mute)", fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 8, color: "var(--ink)" }}
                  labelFormatter={(t) => `${t}s`} formatter={(v, n) => [v == null ? "—" : `${v}°`, n]} />
                <Legend wrapperStyle={{ fontSize: 13, color: "var(--ink)" }} />
                {series.map(([k, nome, cor]) => (
                  <Line key={k} dataKey={k} name={nome} stroke={cor} strokeWidth={2} dot={false} connectNulls
                    activeDot={{ r: 4, stroke: "var(--panel)", strokeWidth: 2 }} isAnimationActive={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          ) : <p className="hint">Sem ângulos medidos: a pessoa não foi detectada no vídeo.</p>}
        </div>
        <div>
          <h4>Momento de maior flexão</h4>
          {r.imagem ? <img className="quadro" src={r.imagem} alt={`Esqueleto detectado no ponto mais flexionado do ${NOMES[r.articulacao_principal]}`} />
            : <p className="hint">Sem imagem: nenhum quadro com a pessoa detectada.</p>}
        </div>
      </div>

      {linhas.length > 0 && (
        <div className="tablewrap" style={{ marginTop: 14 }}>
          <table className="t">
            <thead><tr><th>Medida</th><th>Mínimo</th><th>Máximo</th><th>Amplitude</th><th>Visível em</th></tr></thead>
            <tbody>
              {linhas.map(([k, v]) => (
                <tr key={k}><td>{NOMES[k]}</td><td>{Math.round(v.min)}°</td><td>{Math.round(v.max)}°</td>
                  <td>{Math.round(v.amplitude)}°</td><td>{Math.round(v.cobertura * 100)}% dos quadros</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="hint">Modelo: {r.modelo} · {r.quadros_analisados} quadros em {r.tempo_ia_seg}s · vídeo de {s.duracao_seg}s ({s.video_nome})</p>
    </section>
  );
}
