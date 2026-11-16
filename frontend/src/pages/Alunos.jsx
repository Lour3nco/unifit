import { useEffect, useMemo, useState } from "react";
import api, { mensagemErro } from "../api";
import { useAuth } from "../auth.jsx";
import PageHeader from "../components/PageHeader.jsx";
import { cpfMascara, data, dataHora, hojeISO, moeda, numeroOuNulo } from "../formato";

const VAZIO = { nome: "", email: "", cpf: "", data_nascimento: "", sexo: "", telefone: "", altura_cm: "", peso_kg: "" };
const paraForm = (a) => ({
  nome: a.nome || "", email: a.email || "", cpf: cpfMascara(a.cpf),
  data_nascimento: a.data_nascimento ? String(a.data_nascimento).slice(0, 10) : "",
  sexo: (a.sexo || "").trim(), telefone: a.telefone || "", altura_cm: a.altura_cm ?? "", peso_kg: a.peso_kg ?? "",
});

const iniciais = (nome) => (nome || "?").trim().split(/\s+/).slice(0, 2).map((p) => p[0]).join("").toUpperCase();
const categoria = (a) => (a.atrasados > 0 ? "pendente" : a.vigente ? "ativo" : a.matricula_status ? "pendente" : "inativo");
const ROTULO = { ativo: "Ativo", pendente: "Pendente", inativo: "Inativo" };
const FILTROS = [["todos", "Todos"], ["ativo", "Ativos"], ["pendente", "Pendentes"], ["inativo", "Inativos"]];
const PAGINA = 8;

export default function Alunos() {
  const { usuario } = useAuth();
  const podeEditar = ["administrador", "recepcao"].includes(usuario.perfil);
  const [busca, setBusca] = useState("");
  const [filtro, setFiltro] = useState("todos");
  const [pagina, setPagina] = useState(1);
  const [lista, setLista] = useState(null);
  const [erro, setErro] = useState("");
  const [editando, setEditando] = useState(null);

  const carregar = (termo) =>
    api.get("/alunos", { params: { busca: termo } }).then((r) => setLista(r.data)).catch((e) => setErro(mensagemErro(e)));

  useEffect(() => {
    const id = setTimeout(() => carregar(busca), 300);
    return () => clearTimeout(id);
  }, [busca]);

  useEffect(() => { setPagina(1); }, [filtro, busca]);

  function salvo(aluno) {
    setLista((l) => (l.some((x) => x.id === aluno.id) ? l.map((x) => (x.id === aluno.id ? aluno : x)) : [aluno, ...l]));
    setEditando(null);
  }

  const filtrada = useMemo(
    () => (lista || []).filter((a) => filtro === "todos" || categoria(a) === filtro),
    [lista, filtro],
  );
  const totalPaginas = Math.max(1, Math.ceil(filtrada.length / PAGINA));
  const visiveis = filtrada.slice((pagina - 1) * PAGINA, pagina * PAGINA);
  const ativos = (lista || []).filter((a) => categoria(a) === "ativo").length;
  const alunoEditado = lista?.find((a) => a.id === editando);

  function exportar() {
    const linhas = [["Matrícula", "Nome", "E-mail", "CPF", "Telefone", "Plano", "Situação", "Vencimento", "Último check-in"]];
    filtrada.forEach((a) => linhas.push([a.numero_matricula, a.nome, a.email || "", a.cpf ? cpfMascara(a.cpf) : "",
      a.telefone || "", a.plano || "", ROTULO[categoria(a)], a.matricula_fim ? data(a.matricula_fim) : "",
      a.ultimo_checkin ? dataHora(a.ultimo_checkin) : ""]));
    const csv = linhas.map((l) => l.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(";")).join("\n");
    const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" }));
    const a = document.createElement("a");
    a.href = url; a.download = "alunos-unifit.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <PageHeader eyebrow={`Cadastro${lista ? ` · ${ativos} ativos` : ""}`} title="Alunos">
        <button className="btn-sec" type="button" onClick={exportar} disabled={!lista}>Exportar</button>
        {podeEditar && <button className="btn" type="button" onClick={() => setEditando("novo")}>+ Novo aluno</button>}
      </PageHeader>

      {editando !== null && (
        <FormAluno key={editando} aluno={alunoEditado} onSalvo={salvo} onCancelar={() => setEditando(null)} />
      )}

      <div className="toolbar">
        <div className="searchbox" style={{ flex: "1 1 280px" }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>
          <input type="search" value={busca} onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por nome, CPF ou e-mail" aria-label="Buscar aluno" />
        </div>
        <div className="seg" role="tablist" aria-label="Filtrar por situação">
          {FILTROS.map(([v, r]) => (
            <button key={v} role="tab" aria-selected={filtro === v} onClick={() => setFiltro(v)}>{r}</button>
          ))}
        </div>
      </div>

      <section className="card">
        <div className="err" role="alert">{erro}</div>
        {!lista ? <p className="hint">Carregando...</p> : (
          <div className="tablewrap">
            <table className="t">
              <thead><tr><th>Aluno</th><th>Plano</th><th>Último check-in</th><th>Vencimento</th><th>Status</th><th></th></tr></thead>
              <tbody>
                {visiveis.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <div className="avatar-cel">
                        <span className="avatar-ini">{iniciais(a.nome)}</span>
                        <div>
                          <div className="nome">{a.nome}{a.na_academia && <span className="chip ativa" style={{ marginLeft: 8 }}>Na academia</span>}</div>
                          <div className="sub">{a.email || (a.cpf ? cpfMascara(a.cpf) : `Matrícula ${a.numero_matricula}`)}</div>
                        </div>
                      </div>
                    </td>
                    <td>{a.plano || "—"}</td>
                    <td>{a.ultimo_checkin ? dataHora(a.ultimo_checkin) : "—"}</td>
                    <td>{a.matricula_fim ? data(a.matricula_fim) : "—"}</td>
                    <td><span className={`chip ${categoria(a)}`}>{ROTULO[categoria(a)]}</span></td>
                    <td style={{ textAlign: "right" }}>
                      {podeEditar && <button type="button" className="rowmenu" aria-label="Editar aluno" onClick={() => setEditando(a.id)}>•••</button>}
                    </td>
                  </tr>
                ))}
                {filtrada.length === 0 && <tr><td colSpan="6" className="vazio">Nenhum aluno encontrado.</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {lista && filtrada.length > 0 && (
        <div className="toolbar" style={{ justifyContent: "space-between", marginTop: 16 }}>
          <span className="hint">
            Mostrando {(pagina - 1) * PAGINA + 1}–{Math.min(pagina * PAGINA, filtrada.length)} de {filtrada.length} alunos
          </span>
          <div className="paginacao">
            <button type="button" onClick={() => setPagina((p) => Math.max(1, p - 1))} disabled={pagina === 1} aria-label="Anterior">‹</button>
            {Array.from({ length: totalPaginas }, (_, i) => i + 1)
              .filter((n) => n === 1 || n === totalPaginas || Math.abs(n - pagina) <= 1)
              .map((n, i, arr) => (
                <span key={n} style={{ display: "contents" }}>
                  {i > 0 && n - arr[i - 1] > 1 && <button type="button" disabled>…</button>}
                  <button type="button" aria-current={n === pagina} onClick={() => setPagina(n)}>{n}</button>
                </span>
              ))}
            <button type="button" onClick={() => setPagina((p) => Math.min(totalPaginas, p + 1))} disabled={pagina === totalPaginas} aria-label="Próxima">›</button>
          </div>
        </div>
      )}
    </>
  );
}

function FormAluno({ aluno, onSalvo, onCancelar }) {
  const [f, setF] = useState(() => (aluno ? paraForm(aluno) : VAZIO));
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [planos, setPlanos] = useState([]);
  const [matricula, setMatricula] = useState({ plano_id: "", data_inicio: hojeISO() });
  const mudar = (campo, filtro = (v) => v) => (e) => setF({ ...f, [campo]: filtro(e.target.value) });

  useEffect(() => {
    if (!aluno) api.get("/planos").then((r) => setPlanos(r.data.filter((p) => p.ativo))).catch(() => {});
  }, [aluno]);

  async function salvar(e) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    const corpo = {
      nome: f.nome.trim(), email: f.email.trim() || null, cpf: f.cpf || null, data_nascimento: f.data_nascimento || null,
      sexo: f.sexo || null, telefone: f.telefone || null, altura_cm: numeroOuNulo(f.altura_cm), peso_kg: numeroOuNulo(f.peso_kg),
    };
    try {
      const { data: salvo } = aluno ? await api.put(`/alunos/${aluno.id}`, corpo)
        : await api.post("/alunos", { ...corpo, plano_id: Number(matricula.plano_id), data_inicio: matricula.data_inicio });
      onSalvo(salvo);
    } catch (err) {
      setErro(mensagemErro(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="card" style={{ marginBottom: 16 }}>
      <h3>{aluno ? `Editar ${aluno.nome} · matrícula ${aluno.numero_matricula}` : "Novo aluno"}</h3>
      <form className="form-row" onSubmit={salvar}>
        <label>Nome completo<input value={f.nome} onChange={mudar("nome")} maxLength={120} required /></label>
        <label>E-mail<input type="email" value={f.email} onChange={mudar("email")} maxLength={150} /></label>
        <label>CPF<input value={f.cpf} onChange={mudar("cpf", cpfMascara)} inputMode="numeric" placeholder="000.000.000-00" /></label>
        <label>Data de nascimento<input type="date" value={f.data_nascimento} onChange={mudar("data_nascimento")} max={hojeISO()} /></label>
        <label>Sexo
          <select value={f.sexo} onChange={mudar("sexo")}>
            <option value="">Não informado</option><option value="M">Masculino</option>
            <option value="F">Feminino</option><option value="O">Outro</option>
          </select>
        </label>
        <label>Telefone<input type="tel" value={f.telefone} onChange={mudar("telefone")} maxLength={20} /></label>
        <label>Altura (cm)<input type="number" value={f.altura_cm} onChange={mudar("altura_cm")} min="50" max="260" step="0.5" /></label>
        <label>Peso (kg)<input type="number" value={f.peso_kg} onChange={mudar("peso_kg")} min="20" max="400" step="0.1" /></label>
        {!aluno && (
          <>
            <label>Plano
              <select value={matricula.plano_id} onChange={(e) => setMatricula({ ...matricula, plano_id: e.target.value })} required>
                <option value="">Escolha...</option>
                {planos.map((p) => <option key={p.id} value={p.id}>{p.nome} · {moeda(p.valor)}</option>)}
              </select>
            </label>
            <label>Início do plano
              <input type="date" value={matricula.data_inicio} onChange={(e) => setMatricula({ ...matricula, data_inicio: e.target.value })} required />
            </label>
          </>
        )}
        <div className="acoes">
          <button className="btn" type="submit" disabled={enviando}>{enviando ? "Salvando..." : "Salvar"}</button>
          <button className="btn-sec" type="button" onClick={onCancelar}>Cancelar</button>
        </div>
      </form>
      <div className="err" role="alert">{erro}</div>
      {!aluno && <p className="hint">O número de matrícula é gerado ao salvar, junto com a primeira mensalidade do plano.
        Se o aluno criar uma conta no app com o mesmo e-mail, ela é ligada a este cadastro.</p>}
    </section>
  );
}
