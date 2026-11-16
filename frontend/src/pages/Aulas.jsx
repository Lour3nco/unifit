import { useEffect, useMemo, useState } from "react";
import api, { mensagemErro } from "../api";
import { useAuth } from "../auth.jsx";
import BuscaAluno from "../components/BuscaAluno.jsx";
import PageHeader from "../components/PageHeader.jsx";
import { hojeISO } from "../formato";

const DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]; // 0..5 (Dom fica fora da grade semanal)
const INICIO = 360, FIM = 1320; // 06:00..22:00, 1px por minuto
const ALTURA = FIM - INICIO;
const HORAS = [6, 8, 10, 12, 14, 16, 18, 20, 22];
const toMin = (hhmm) => { const [h, m] = hhmm.split(":").map(Number); return h * 60 + m; };
const addDias = (iso, n) => { const d = new Date(`${iso}T00:00:00`); d.setDate(d.getDate() + n); return d.toLocaleDateString("sv-SE"); };
const diaNum = (iso, i) => { const d = new Date(`${iso}T00:00:00`); d.setDate(d.getDate() + i); return d.getDate(); };
const MES = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString("pt-BR", { month: "short" }).replace(".", "");

export default function Aulas() {
  const { usuario } = useAuth();
  const aluno = usuario.perfil === "aluno";
  const base = aluno ? "/meu/aulas" : "/aulas";
  const [ref, setRef] = useState(hojeISO());
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState("");
  const [vista, setVista] = useState("agenda"); // agenda | performance
  const [sel, setSel] = useState(null); // ocorrência aberta no modal
  const [form, setForm] = useState(null); // "nova" ou aula (equipe)

  const carregar = () => api.get(`${base}/semana`, { params: { data: ref } })
    .then((r) => setDados(r.data)).catch((e) => setErro(mensagemErro(e)));
  useEffect(() => { carregar(); }, [ref]);

  const eyebrow = dados ? `Semana ${diaNum(dados.inicio, 0)}–${diaNum(dados.inicio, 5)} ${MES(dados.inicio)}` : "Grade de aulas";

  return (
    <>
      <PageHeader eyebrow={eyebrow} title="Aulas & Agenda">
        <div className="seg" role="tablist" aria-label="Visualização">
          <button role="tab" aria-selected={vista === "agenda"} onClick={() => setVista("agenda")}>Agenda</button>
          <button role="tab" aria-selected={vista === "performance"} onClick={() => setVista("performance")}>Performance</button>
        </div>
        {vista === "agenda" && (
          <div className="seg" aria-label="Semana">
            <button onClick={() => setRef(addDias(ref, -7))} aria-label="Semana anterior">‹</button>
            <button onClick={() => setRef(hojeISO())}>Hoje</button>
            <button onClick={() => setRef(addDias(ref, 7))} aria-label="Próxima semana">›</button>
          </div>
        )}
        {!aluno && vista === "agenda" && <button className="btn" type="button" onClick={() => setForm("nova")}>+ Nova aula</button>}
      </PageHeader>

      <div className="err" role="alert">{erro}</div>

      {vista === "performance" ? (
        aluno ? <MinhaFrequencia /> : <PerformanceEquipe />
      ) : !dados ? <div className="ph">Carregando a grade...</div> : (
        <Grade dados={dados} onAbrir={setSel} />
      )}

      {sel && (
        <ModalOcorrencia sel={sel} aluno={aluno} base={base} onFechar={() => setSel(null)}
          onMudou={() => { carregar(); setSel(null); }}
          onEditar={!aluno ? (a) => { setSel(null); setForm(a); } : undefined} />
      )}
      {form && <FormAula aula={form === "nova" ? null : form} onFechar={() => setForm(null)}
        onSalvo={() => { setForm(null); carregar(); }} />}
    </>
  );
}

function Grade({ dados, onAbrir }) {
  return (
    <div className="tablewrap">
      <div className="agenda">
        <div className="agenda-head">
          <div className="dia" aria-hidden="true" />
          {DIAS.map((nome, i) => {
            const hoje = addDias(dados.inicio, i) === hojeISO();
            return <div className={`dia ${hoje ? "hoje" : ""}`} key={nome}><small>{nome}</small><strong>{diaNum(dados.inicio, i)}</strong></div>;
          })}
        </div>
        <div className="agenda-body">
          <div className="agenda-times" style={{ minHeight: ALTURA }}>
            {HORAS.map((h) => <span key={h} style={{ top: h * 60 - INICIO }}>{String(h).padStart(2, "0")}:00</span>)}
          </div>
          {DIAS.map((nome, i) => (
            <div className="agenda-col" key={nome} style={{ minHeight: ALTURA }}>
              {dados.aulas.filter((a) => a.dia_semana === i).map((a) => {
                const top = toMin(a.hora_inicio) - INICIO;
                const height = Math.max(toMin(a.hora_fim) - toMin(a.hora_inicio), 30);
                const destaque = !!a.minha_reserva_id;
                return (
                  <button type="button" key={a.aula_id} className={`agenda-evt ${destaque ? "destaque" : ""} ${a.lotada ? "lotada" : ""}`}
                    style={{ top, height }} onClick={() => onAbrir(a)}>
                    <div className="hora">{a.hora_inicio} – {a.hora_fim}</div>
                    <div className="nome">{a.nome}</div>
                    <div className="prof">{a.instrutor || "—"}</div>
                    <div className="lot">{a.reservados}/{a.capacidade}{destaque ? " · reservado" : a.lotada ? " · lotada" : ""}</div>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ModalOcorrencia({ sel, aluno, base, onFechar, onMudou, onEditar }) {
  const [roster, setRoster] = useState(null);
  const [erro, setErro] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!aluno) api.get(`/aulas/${sel.aula_id}/reservas`, { params: { data: sel.data } })
      .then((r) => setRoster(r.data)).catch((e) => setErro(mensagemErro(e)));
  }, [aluno, sel]);

  const acao = async (fn) => { setErro(""); setBusy(true); try { await fn(); } catch (e) { setErro(mensagemErro(e)); setBusy(false); } };
  const reservar = () => acao(async () => { await api.post(`${base}/${sel.aula_id}/reservar`, { data: sel.data }); onMudou(); });
  const cancelar = () => acao(async () => { await api.delete(`${base.replace("/aulas", "")}/reservas/${sel.minha_reserva_id}`); onMudou(); });
  const checkin = () => acao(async () => { await api.post(`/meu/reservas/${sel.minha_reserva_id}/checkin`); onMudou(); });

  async function presenca(rid, presente) {
    setErro("");
    try {
      await api.patch(`/reservas/${rid}`, { presente });
      setRoster((rs) => rs.map((x) => (x.reserva_id === rid ? { ...x, presente } : x)));
    } catch (e) { setErro(mensagemErro(e)); }
  }
  async function reservarAluno(a) {
    setErro("");
    try {
      const { data } = await api.post(`/aulas/${sel.aula_id}/reservas`, { data: sel.data, aluno_id: a.id });
      if (data.aviso) window.alert(data.aviso); // aluno com mensalidade em atraso: a equipe reserva, mas cobra
      onMudou();
    }
    catch (e) { setErro(mensagemErro(e)); }
  }

  return (
    <div className="modal-bg" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-topo">
          <div>
            <h3>{sel.nome}</h3>
            <p className="hint">{sel.hora_inicio} – {sel.hora_fim} · {sel.instrutor || "sem instrutor"} · {sel.reservados}/{sel.capacidade} vagas</p>
          </div>
          <button className="modal-fechar" onClick={onFechar} aria-label="Fechar">×</button>
        </div>
        <div className="err" role="alert">{erro}</div>

        {aluno ? (
          <div className="acoes" style={{ marginTop: 10 }}>
            {/* mesmas regras da API: check-in só no dia; não cancela aula passada nem com presença */}
            {sel.minha_reserva_id ? (
              <>
                {sel.eu_presente ? <span className="chip ativo">Presença confirmada</span>
                  : sel.data === hojeISO() ? <button className="btn" type="button" disabled={busy} onClick={checkin}>Fazer check-in</button>
                  : sel.data > hojeISO() ? <span className="hint">Check-in liberado no dia da aula</span>
                  : <span className="chip inativo">Sem presença</span>}
                {!sel.eu_presente && sel.data >= hojeISO() && (
                  <button className="btn-sec perigo" type="button" disabled={busy} onClick={cancelar}>Cancelar reserva</button>
                )}
              </>
            ) : sel.data < hojeISO() ? <span className="chip inativo">Aula encerrada</span>
              : sel.lotada ? <span className="chip inativo">Aula lotada</span>
              : <button className="btn" type="button" disabled={busy} onClick={reservar}>Reservar vaga</button>}
          </div>
        ) : (
          <>
            <div className="card-topo" style={{ marginTop: 14 }}>
              <h4 style={{ margin: 0 }}>Reservados ({roster ? roster.length : "…"}/{sel.capacidade})</h4>
              {onEditar && <button className="card-link" type="button" onClick={() => onEditar(sel.aula_id)}>Editar aula</button>}
            </div>
            {!roster ? <p className="hint">Carregando...</p> : roster.length === 0 ? <p className="hint">Nenhum aluno reservado.</p> : (
              <div>
                {roster.map((r) => (
                  <div className="reserva-linha" key={r.reserva_id}>
                    <span>{r.aluno} <small className="hint">· {r.matricula}</small></span>
                    <label className="inline" style={{ fontWeight: 600 }}>
                      <input type="checkbox" checked={r.presente} onChange={(e) => presenca(r.reserva_id, e.target.checked)} /> Presente
                    </label>
                  </div>
                ))}
              </div>
            )}
            {!sel.lotada && (
              <div style={{ marginTop: 14 }}>
                <h4>Reservar para um aluno</h4>
                <BuscaAluno rotulo="Buscar aluno" acao={(a) => (
                  <button type="button" className="btn-sec" onClick={() => reservarAluno(a)}>Reservar</button>
                )} />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function FormAula({ aula, onFechar, onSalvo }) {
  const [f, setF] = useState(() => ({
    nome: aula?.nome || "", instrutor_id: aula?.instrutor_id ? String(aula.instrutor_id) : "",
    dia_semana: aula?.dia_semana ?? 0, hora_inicio: aula?.hora_inicio || "06:30",
    hora_fim: aula?.hora_fim || "07:30", capacidade: aula?.capacidade || 20,
  }));
  const [instrutores, setInstrutores] = useState(null);
  const [erro, setErro] = useState("");
  const [busy, setBusy] = useState(false);
  const idAula = aula && typeof aula === "object" ? aula.id || aula.aula_id : null;

  useEffect(() => {
    // só o admin consegue listar usuários; nos demais perfis o campo de instrutor fica oculto
    api.get("/usuarios").then((r) => setInstrutores(r.data.filter((u) => u.perfil === "instrutor"))).catch(() => setInstrutores([]));
  }, []);

  async function salvar(e) {
    e.preventDefault();
    setErro(""); setBusy(true);
    const corpo = {
      nome: f.nome.trim(), instrutor_id: f.instrutor_id ? Number(f.instrutor_id) : null,
      dia_semana: Number(f.dia_semana), hora_inicio: f.hora_inicio, hora_fim: f.hora_fim, capacidade: Number(f.capacidade),
    };
    try {
      if (idAula) await api.put(`/aulas/${idAula}`, corpo); else await api.post("/aulas", corpo);
      onSalvo();
    } catch (err) { setErro(mensagemErro(err)); setBusy(false); }
  }

  async function arquivar() {
    if (!idAula || !window.confirm("Arquivar esta aula? Ela some da grade.")) return;
    try { await api.patch(`/aulas/${idAula}`, { ativo: false }); onSalvo(); } catch (e) { setErro(mensagemErro(e)); }
  }

  return (
    <div className="modal-bg" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-topo">
          <h3>{idAula ? "Editar aula" : "Nova aula"}</h3>
          <button className="modal-fechar" onClick={onFechar} aria-label="Fechar">×</button>
        </div>
        <form onSubmit={salvar} className="form-row">
          <label>Nome<input value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} maxLength={80} required /></label>
          {instrutores && instrutores.length > 0 && (
            <label>Instrutor
              <select value={f.instrutor_id} onChange={(e) => setF({ ...f, instrutor_id: e.target.value })}>
                <option value="">Sem instrutor</option>
                {instrutores.map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}
              </select>
            </label>
          )}
          <label>Dia da semana
            <select value={f.dia_semana} onChange={(e) => setF({ ...f, dia_semana: e.target.value })}>
              {["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"].map((d, i) => <option key={i} value={i}>{d}</option>)}
            </select>
          </label>
          <label>Início<input type="time" value={f.hora_inicio} onChange={(e) => setF({ ...f, hora_inicio: e.target.value })} required /></label>
          <label>Término<input type="time" value={f.hora_fim} onChange={(e) => setF({ ...f, hora_fim: e.target.value })} required /></label>
          <label>Capacidade<input type="number" value={f.capacidade} onChange={(e) => setF({ ...f, capacidade: e.target.value })} min="1" max="200" required /></label>
          <div className="acoes">
            <button className="btn" type="submit" disabled={busy}>{busy ? "Salvando..." : "Salvar"}</button>
            <button className="btn-sec" type="button" onClick={onFechar}>Cancelar</button>
            {idAula && <button className="btn-sec perigo" type="button" onClick={arquivar}>Arquivar</button>}
          </div>
        </form>
        <div className="err" role="alert">{erro}</div>
      </div>
    </div>
  );
}

function MinhaFrequencia() {
  const [d, setD] = useState(null);
  const [erro, setErro] = useState("");
  useEffect(() => { api.get("/meu/aulas/frequencia").then((r) => setD(r.data)).catch((e) => setErro(mensagemErro(e))); }, []);
  if (erro) return <div className="ph">{erro}</div>;
  if (!d) return <div className="ph">Carregando sua frequência...</div>;
  const lista = (itens, vazio) => itens.length ? (
    <ul className="lista">{itens.map((i) => (
      <li key={i.reserva_id}>{new Date(`${i.data}T00:00:00`).toLocaleDateString("pt-BR")} · <strong>{i.aula}</strong> · {i.hora_inicio}
        {i.presente ? <span className="chip ativo" style={{ marginLeft: 8 }}>Presente</span> : null}</li>
    ))}</ul>
  ) : <p className="hint">{vazio}</p>;
  return (
    <>
      <div className="mini-kpis" style={{ marginBottom: 16 }}>
        <div><small>Reservas</small><strong>{d.reservas}</strong></div>
        <div><small>Presenças</small><strong>{d.presencas}</strong></div>
        <div><small>Assiduidade</small><strong>{d.presenca_pct}%</strong></div>
      </div>
      <section className="card" style={{ marginBottom: 14 }}><h3>Próximas aulas</h3>{lista(d.proximas, "Você não tem aulas reservadas.")}</section>
      <section className="card"><h3>Histórico</h3>{lista(d.recentes, "Sem aulas anteriores.")}</section>
    </>
  );
}

function PerformanceEquipe() {
  const [d, setD] = useState(null);
  const [erro, setErro] = useState("");
  useEffect(() => { api.get("/aulas/performance").then((r) => setD(r.data)).catch((e) => setErro(mensagemErro(e))); }, []);
  if (erro) return <div className="ph">{erro}</div>;
  if (!d) return <div className="ph">Carregando performance...</div>;
  return (
    <>
      <div className="mini-kpis" style={{ marginBottom: 16 }}>
        <div><small>Aulas ativas</small><strong>{d.aulas_ativas}</strong></div>
        <div><small>Reservas</small><strong>{d.reservas_total}</strong></div>
        <div><small>Presenças</small><strong>{d.presencas_total}</strong></div>
        <div><small>Taxa de presença</small><strong>{d.presenca_pct}%</strong></div>
      </div>
      <div className="grid2">
        <section className="card">
          <h3>Lotação por aula</h3>
          <div className="tablewrap"><table className="t">
            <thead><tr><th>Aula</th><th>Capac.</th><th>Reservas</th><th>Presenças</th></tr></thead>
            <tbody>
              {d.por_aula.map((a, k) => <tr key={k}><td>{a.nome}</td><td>{a.capacidade}</td><td>{a.reservas}</td><td>{a.presencas}</td></tr>)}
              {d.por_aula.length === 0 && <tr><td colSpan="4" className="vazio">Sem dados ainda.</td></tr>}
            </tbody>
          </table></div>
        </section>
        <section className="card">
          <h3>Por instrutor</h3>
          <div className="tablewrap"><table className="t">
            <thead><tr><th>Instrutor</th><th>Aulas</th><th>Reservas</th><th>Presenças</th></tr></thead>
            <tbody>
              {d.por_instrutor.map((a, k) => <tr key={k}><td>{a.instrutor}</td><td>{a.aulas}</td><td>{a.reservas}</td><td>{a.presencas}</td></tr>)}
              {d.por_instrutor.length === 0 && <tr><td colSpan="4" className="vazio">Sem dados ainda.</td></tr>}
            </tbody>
          </table></div>
        </section>
      </div>
    </>
  );
}
