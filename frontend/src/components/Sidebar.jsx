import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import Logo from "./Logo.jsx";

const PERFIS = { administrador: "Administrador", recepcao: "Recepção", instrutor: "Instrutor", aluno: "Aluno" };

// RF02: itens do menu conforme o perfil. "rota" = endereço; "eyebrow" = rótulo pequeno do cabeçalho.
export const MENU = [
  { nome: "Meus dados", rota: "/meus-dados", eyebrow: "Minha conta", icone: "id", perfis: ["aluno"] },
  { nome: "Pagamentos", rota: "/pagamentos", eyebrow: "Financeiro", icone: "card", perfis: ["aluno"] },
  { nome: "Dashboard", rota: "/dashboard", eyebrow: "Visão geral", icone: "grid", perfis: ["administrador", "recepcao", "instrutor"] },
  { nome: "Alunos", rota: "/alunos", eyebrow: "Cadastro", icone: "users", perfis: ["administrador", "recepcao", "instrutor"] },
  { nome: "Planos e matrículas", rota: "/planos", eyebrow: "Gerenciar planos", icone: "tag", perfis: ["administrador", "recepcao"] },
  { nome: "Aulas & Agenda", rota: "/aulas", eyebrow: "Grade de aulas", icone: "calendar", perfis: ["administrador", "recepcao", "instrutor", "aluno"] },
  { nome: "Financeiro", rota: "/financeiro", eyebrow: "Contas e recebimentos", icone: "dollar", perfis: ["administrador", "recepcao"] },
  { nome: "Check-in", rota: "/check-in", eyebrow: "Acesso à academia", icone: "check", perfis: ["administrador", "recepcao", "aluno"] },
  { nome: "Treinos", rota: "/treinos", eyebrow: "Fichas e evolução", icone: "dumbbell", perfis: ["administrador", "instrutor", "aluno"] },
  { nome: "Análise de postura", rota: "/postura", eyebrow: "IA de vídeo", icone: "activity", perfis: ["administrador", "instrutor"] },
  { nome: "Relatórios", rota: "/relatorios", eyebrow: "Indicadores", icone: "chart", perfis: ["administrador"] },
  { nome: "Usuários", rota: "/usuarios", eyebrow: "Equipe e acessos", icone: "shield", perfis: ["administrador"] },
];

// ícones de linha (traçado), 24x24, herdam currentColor
const P = {
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z",
  users: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
  tag: "M20.59 13.41 13.42 20.58a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82zM7 7h.01",
  calendar: "M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
  dollar: "M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6",
  check: "M9 12l2 2 4-4M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z",
  dumbbell: "M6.5 6.5l11 11M21 21l-1-1M3 3l1 1M18 22l4-4M2 6l4-4M6.5 10.5l-3 3M13.5 17.5l3-3",
  activity: "M22 12h-4l-3 9L9 3l-3 9H2",
  chart: "M3 3v18h18M7 16V9M12 16V5M17 16v-6",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  id: "M3 5h18v14H3zM7 9h4M7 13h10M7 17h6",
  card: "M2 7h20v10H2zM2 11h20",
};

function Icone({ nome }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={P[nome] || P.grid} />
    </svg>
  );
}

const iniciais = (nome) => nome.trim().split(/\s+/).slice(0, 2).map((p) => p[0]).join("").toUpperCase();

export default function Sidebar({ atual, onSelecionar, aberto }) {
  const { usuario, sair } = useAuth();
  const navegar = useNavigate();
  return (
    <aside className={aberto ? "open" : ""}>
      <Logo />
      <div className="menu-label">Menu</div>
      <nav aria-label="Principal">
        {MENU.filter((m) => m.perfis.includes(usuario.perfil)).map((m) => (
          <button key={m.nome} className="navitem" aria-current={m.nome === atual ? "page" : undefined}
            onClick={() => onSelecionar(m.rota)}>
            <span className="navicon"><Icone nome={m.icone} /></span>
            <span>{m.nome}</span>
          </button>
        ))}
      </nav>
      <div className="who">
        <span className="avatar" aria-hidden="true">{iniciais(usuario.nome)}</span>
        <span className="meta">
          <strong>{usuario.nome}</strong>
          <small>{PERFIS[usuario.perfil] || usuario.perfil}</small>
        </span>
        {/* sair volta para "/" sem guardar a tela: o próximo login começa do início */}
        <button className="sair" type="button" aria-label="Sair" title="Sair"
          onClick={() => { sair(); navegar("/", { replace: true }); }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
          </svg>
        </button>
      </div>
    </aside>
  );
}
