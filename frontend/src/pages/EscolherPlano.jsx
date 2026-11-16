import { useEffect, useState } from "react";
import api, { mensagemErro } from "../api";
import { useAuth } from "../auth.jsx";
import Logo from "../components/Logo.jsx";
import { moeda } from "../formato";

export default function EscolherPlano({ onEscolhido }) {
  const { usuario, sair } = useAuth();
  const [planos, setPlanos] = useState(null);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(null); // id do plano em processamento

  useEffect(() => {
    api.get("/meu/planos").then((r) => setPlanos(r.data)).catch((e) => setErro(mensagemErro(e)));
  }, []);

  async function escolher(p) {
    setErro("");
    setEnviando(p.id);
    try {
      const { data } = await api.post("/meu/matricula", { plano_id: p.id });
      onEscolhido(data.mensagem);
    } catch (e) {
      setErro(mensagemErro(e));
      setEnviando(null);
    }
  }

  return (
    <section className="planos-gate">
      <header>
        <Logo variant="horizontal" />
        <button type="button" className="linkbtn" onClick={sair}>Sair</button>
      </header>

      <div className="planos-gate-topo">
        <span className="eyebrow">Bem-vindo, {usuario.nome.split(" ")[0]}</span>
        <h1 className="title-xl">Escolha seu plano</h1>
        <p className="hint">Selecione um plano para liberar seu acesso completo ao sistema. Você pode mudar depois com a recepção.</p>
      </div>

      <div className="err" role="alert">{erro}</div>

      {!planos ? <div className="ph">Carregando planos...</div>
        : planos.length === 0 ? <div className="ph">Nenhum plano disponível no momento. Fale com a recepção.</div> : (
          <div className="planos">
            {planos.map((p, i) => {
              const destaque = planos.length >= 2 && i === 1;
              return (
                <div className={`plano ${destaque ? "destaque" : ""}`} key={p.id}>
                  <div className="plano-topo">
                    <h3>{p.nome}</h3>
                    {destaque && <span className="tag">Popular</span>}
                  </div>
                  <div className="plano-sub">Disponível para venda</div>
                  <div className="preco">{moeda(p.valor)}<small>{p.duracao_dias <= 31 ? "/mês" : `/${p.duracao_dias} dias`}</small></div>
                  <ul className="plano-feats">
                    <li>{p.duracao_dias} dias de vigência</li>
                    <li>Acesso ao app do aluno</li>
                    <li>Reserva de aulas e acompanhamento de treinos</li>
                  </ul>
                  <button className="btn" type="button" disabled={enviando === p.id} onClick={() => escolher(p)}>
                    {enviando === p.id ? "Processando..." : "Selecionar plano"}
                  </button>
                </div>
              );
            })}
          </div>
        )}
    </section>
  );
}
