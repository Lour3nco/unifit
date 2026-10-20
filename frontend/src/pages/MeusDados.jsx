import { useEffect, useState } from "react";
import api, { mensagemErro } from "../api";
import { useAuth } from "../auth.jsx";
import { cpfMascara, numeroOuNulo } from "../formato";

const STATUS = { pago: "Pago", paga: "Pago", pendente: "Pendente", atrasado: "Em atraso", atrasada: "Em atraso",
  ativa: "Ativa", ativo: "Ativa", vencida: "Vencida", cancelada: "Cancelada" };
const rotuloStatus = (s) => STATUS[s] || (s ? s.charAt(0).toUpperCase() + s.slice(1) : "—");

const data = (v) => (v ? new Date(String(v).length <= 10 ? `${v}T00:00:00` : v).toLocaleDateString("pt-BR") : "—");
const dataHora = (v) => (v ? new Date(v).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—");
const moeda = (v) => (v === null || v === undefined ? "—" : Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }));

export default function MeusDados() {
  const { usuario } = useAuth();
  const [r, setR] = useState(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api.get("/meu/resumo").then((x) => setR(x.data)).catch((e) => setErro(mensagemErro(e)));
  }, []);

  if (erro) return <div className="ph">{erro}</div>;
  if (!r) return <div className="ph">Carregando seus dados...</div>;

  // cobrança realmente em aberto (pendente/atrasada)
  const emAberto = [...r.pagamentos].reverse().find((p) => ["pendente", "atrasado", "atrasada"].includes(p.status));
  // sem nada em aberto: mostramos a renovação a vencer no fim da matrícula (só exibição, não cria cobrança)
  const m = r.matricula;
  const hojeStr = new Date().toLocaleDateString("sv-SE");
  const renovacao = !emAberto && m && m.status === "ativa" && m.fim
    ? { valor: m.valor, vencimento: m.fim, vencida: String(m.fim).slice(0, 10) < hojeStr }
    : null;

  return (
    <>
      <p className="boasvindas">Olá, {usuario.nome.split(" ")[0]}.</p>

      {!r.vinculado && (
        <div className="aviso" role="status">
          Complete e salve seus dados no fim da página para liberar check-in, pagamentos e treinos.
        </div>
      )}

      <div className="kpis">
        <div className="kpi"><small>Plano</small><strong>{r.matricula?.plano || "—"}</strong>
          {r.matricula && <em><span className={`chip ${r.matricula.status}`}>{rotuloStatus(r.matricula.status)}</span></em>}</div>
        <div className="kpi"><small>Matrícula válida até</small><strong>{data(r.matricula?.fim)}</strong></div>
        <div className="kpi"><small>Próximo pagamento</small>
          <strong>{emAberto ? moeda(emAberto.valor) : renovacao ? moeda(renovacao.valor) : "Em dia"}</strong>
          {emAberto
            ? <em className={emAberto.status.startsWith("atras") ? "down" : ""}>vence em {data(emAberto.vencimento)}</em>
            : renovacao && <em className={renovacao.vencida ? "down" : ""}>{renovacao.vencida ? "venceu em" : "a vencer em"} {data(renovacao.vencimento)}</em>}</div>
        <div className="kpi"><small>Check-ins em 30 dias</small><strong>{r.checkins.ultimos_30_dias}</strong></div>
      </div>

      <div className="grid">
        <section className="card">
          <h3>Pagamentos</h3>
          <div className="tablewrap">
            <table className="t">
              <thead><tr><th>Vencimento</th><th>Valor</th><th>Pago em</th><th>Situação</th></tr></thead>
              <tbody>
                {r.pagamentos.map((p, i) => (
                  <tr key={i}><td>{data(p.vencimento)}</td><td>{moeda(p.valor)}</td><td>{data(p.pago_em)}</td>
                    <td><span className={`chip ${p.status}`}>{rotuloStatus(p.status)}</span></td></tr>
                ))}
                {r.pagamentos.length === 0 && <tr><td colSpan="4" className="vazio">Nenhum pagamento registrado.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>

        <section className="card">
          <h3>Histórico de check-ins</h3>
          <ul className="lista">
            {r.checkins.recentes.map((c, i) => <li key={i}>{dataHora(c)}</li>)}
            {r.checkins.recentes.length === 0 && <li className="vazio">Nenhum check-in ainda.</li>}
          </ul>
        </section>
      </div>

      <FormDados usuario={r.usuario} perfil={r.perfil} numeroMatricula={r.numero_matricula} onSalvo={(perfil) => setR({ ...r, perfil, vinculado: true })} />
    </>
  );
}

const paraForm = (p) => ({
  cpf: cpfMascara(p.cpf), data_nascimento: p.data_nascimento ? String(p.data_nascimento).slice(0, 10) : "",
  sexo: (p.sexo || "").trim(), telefone: p.telefone || "",
  altura_cm: p.altura_cm ?? "", peso_kg: p.peso_kg ?? "",
});

function FormDados({ usuario, perfil, numeroMatricula, onSalvo }) {
  const [f, setF] = useState(() => paraForm(perfil));
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [enviando, setEnviando] = useState(false);
  const mudar = (campo, filtro = (v) => v) => (e) => { setOk(""); setF({ ...f, [campo]: filtro(e.target.value) }); };

  const altura = Number(f.altura_cm), peso = Number(f.peso_kg);
  const imc = altura > 0 && peso > 0 ? (peso / (altura / 100) ** 2).toFixed(1) : null;

  async function salvar(e) {
    e.preventDefault();
    setErro(""); setOk("");
    setEnviando(true);
    try {
      const { data: salvo } = await api.put("/meu/dados", {
        cpf: f.cpf || null, data_nascimento: f.data_nascimento || null, sexo: f.sexo || null,
        telefone: f.telefone || null, altura_cm: numeroOuNulo(f.altura_cm), peso_kg: numeroOuNulo(f.peso_kg),
      });
      setF(paraForm(salvo));
      setOk("Dados salvos.");
      onSalvo(salvo);
    } catch (err) {
      setErro(mensagemErro(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="card" style={{ marginTop: 14 }}>
      <h3>Meus dados</h3>
      <dl className="dl" style={{ marginBottom: 16 }}>
        {numeroMatricula && <div><dt>Nº de matrícula</dt><dd>{numeroMatricula}</dd></div>}
        <div><dt>Nome</dt><dd>{usuario.nome}</dd></div>
        <div><dt>E-mail de acesso</dt><dd>{usuario.email}</dd></div>
        {imc && <div><dt>IMC</dt><dd>{imc}</dd></div>}
      </dl>
      <form className="form-row" onSubmit={salvar}>
        <label>CPF
          <input value={f.cpf} onChange={mudar("cpf", cpfMascara)} inputMode="numeric" placeholder="000.000.000-00" />
        </label>
        <label>Data de nascimento
          <input type="date" value={f.data_nascimento} onChange={mudar("data_nascimento")} max={new Date().toLocaleDateString("sv-SE")} />
        </label>
        <label>Sexo
          <select value={f.sexo} onChange={mudar("sexo")}>
            <option value="">Não informar</option>
            <option value="M">Masculino</option>
            <option value="F">Feminino</option>
            <option value="O">Outro</option>
          </select>
        </label>
        <label>Telefone
          <input type="tel" value={f.telefone} onChange={mudar("telefone")} maxLength={20} autoComplete="tel" placeholder="(00) 00000-0000" />
        </label>
        <label>Altura (cm)
          <input type="number" value={f.altura_cm} onChange={mudar("altura_cm")} min="50" max="260" step="0.5" inputMode="decimal" />
        </label>
        <label>Peso (kg)
          <input type="number" value={f.peso_kg} onChange={mudar("peso_kg")} min="20" max="400" step="0.1" inputMode="decimal" />
        </label>
        <button className="btn" type="submit" disabled={enviando}>{enviando ? "Salvando..." : "Salvar dados"}</button>
      </form>
      <div className="err" role="alert">{erro}</div>
      {ok && <div className="okmsg" role="status">{ok}</div>}
    </section>
  );
}