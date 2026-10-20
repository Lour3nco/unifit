import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";

const PERFIS = { administrador: "Administrador", recepcao: "Recepção", instrutor: "Instrutor", aluno: "Aluno" };

// RF02: itens do menu conforme o perfil; "rota" é o endereço da tela no navegador
export const MENU = [
  { nome: "Meus dados", rota: "/meus-dados", perfis: ["aluno"] },
  { nome: "Pagamentos", rota: "/pagamentos", perfis: ["aluno"] },
  { nome: "Dashboard", rota: "/dashboard", perfis: ["administrador", "recepcao", "instrutor"] },
  { nome: "Alunos", rota: "/alunos", perfis: ["administrador", "recepcao", "instrutor"] },
  { nome: "Planos e matrículas", rota: "/planos", perfis: ["administrador", "recepcao"] },
  { nome: "Financeiro", rota: "/financeiro", perfis: ["administrador", "recepcao"] },
  { nome: "Check-in", rota: "/check-in", perfis: ["administrador", "recepcao", "aluno"] },
  { nome: "Treinos", rota: "/treinos", perfis: ["administrador", "instrutor", "aluno"] },
  { nome: "Análise de postura", rota: "/postura", perfis: ["administrador", "instrutor"] },
  { nome: "Relatórios", rota: "/relatorios", perfis: ["administrador"] },
  { nome: "Usuários", rota: "/usuarios", perfis: ["administrador"] },
];

export default function Sidebar({ atual, onSelecionar, aberto }) {
  const { usuario, sair } = useAuth();
  const navegar = useNavigate();
  return (
    <aside className={aberto ? "open" : ""}>
      <div className="brand">Uni<b>Fit</b></div>
      <nav aria-label="Principal">
        {MENU.filter((m) => m.perfis.includes(usuario.perfil)).map((m) => (
          <button key={m.nome} aria-current={m.nome === atual ? "page" : undefined} onClick={() => onSelecionar(m.rota)}>
            {m.nome}
          </button>
        ))}
      </nav>
      <div className="who">
        <strong>{usuario.nome}</strong>
        <small>{PERFIS[usuario.perfil] || usuario.perfil}</small>
        {/* sair de propósito volta para "/" sem guardar a tela: o próximo login começa do início */}
        <button onClick={() => { sair(); navegar("/", { replace: true }); }}>Sair</button>
      </div>
    </aside>
  );
}