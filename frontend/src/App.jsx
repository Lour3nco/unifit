import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import api from "./api";
import { useAuth } from "./auth.jsx";
import Login from "./pages/Login.jsx";
import Cadastro from "./pages/Cadastro.jsx";
import EscolherPlano from "./pages/EscolherPlano.jsx";
import EsqueciSenha, { RedefinirSenha } from "./pages/EsqueciSenha.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import MeusDados from "./pages/MeusDados.jsx";
import MeusTreinos from "./pages/MeusTreinos.jsx";
import MeuCheckin from "./pages/MeuCheckin.jsx";
import MeusPagamentos from "./pages/MeusPagamentos.jsx";
import Alunos from "./pages/Alunos.jsx";
import PlanosMatriculas from "./pages/PlanosMatriculas.jsx";
import Financeiro from "./pages/Financeiro.jsx";
import CheckinRecepcao from "./pages/CheckinRecepcao.jsx";
import Treinos from "./pages/Treinos.jsx";
import Postura from "./pages/Postura.jsx";
import Relatorios from "./pages/Relatorios.jsx";
import Usuarios from "./pages/Usuarios.jsx";
import Aulas from "./pages/Aulas.jsx";
import Sidebar, { MENU } from "./components/Sidebar.jsx";
import PageHeader from "./components/PageHeader.jsx";
import Logo from "./components/Logo.jsx";

// telas que montam o próprio cabeçalho (com ações à direita); as demais usam o cabeçalho padrão
const HEADER_PROPRIO = new Set(["/dashboard", "/aulas", "/alunos", "/planos"]);

// o aluno só acessa o sistema com um plano ativo (matrícula vigente)
function temPlanoAtivo(resumo) {
  const m = resumo?.matricula;
  if (!m || m.status !== "ativa") return false;
  if (m.fim && String(m.fim).slice(0, 10) < new Date().toLocaleDateString("sv-SE")) return false;
  return true;
}

function abaSalva() {
  try {
    return localStorage.getItem("gymai_aba") === "equipe" ? "equipe" : "aluno";
  } catch {
    return "aluno";
  }
}

export default function App() {
  const { usuario, carregando, semConexao, verificar } = useAuth();
  const { pathname, state } = useLocation();
  const navegar = useNavigate();
  const [aba, setAba] = useState(abaSalva); // lembra a última aba usada neste navegador
  const [menuAberto, setMenuAberto] = useState(false);
  const [planoOk, setPlanoOk] = useState(null); // null = verificando; só importa para o aluno

  useEffect(() => {
    if (!usuario) { setPlanoOk(null); return; }
    if (usuario.perfil !== "aluno") { setPlanoOk(true); return; }
    setPlanoOk(null);
    api.get("/meu/resumo").then((r) => setPlanoOk(temPlanoAtivo(r.data))).catch(() => setPlanoOk(true));
  }, [usuario]);

  if (carregando) return null;
  // o link do e-mail/SMS abre esta tela mesmo com alguém logado neste navegador
  if (pathname === "/redefinir-senha") return <RedefinirSenha onVoltar={() => navegar("/", { replace: true })} />;
  if (semConexao) {
    return (
      <section className="erro-pagina" role="alert">
        <Logo />
        <strong className="codigo">503</strong>
        <h1>Serviço indisponível</h1>
        <p>Não conseguimos carregar esta página agora. Aguarde alguns instantes e tente novamente.</p>
        <button type="button" className="btn" onClick={verificar}>Tentar novamente</button>
      </section>
    );
  }
  if (!usuario) {
    const mudarAba = (nova) => {
      setAba(nova);
      try { localStorage.setItem("gymai_aba", nova); } catch { /* sem armazenamento: só não lembra */ }
    };
    // sem login, endereço de tela interna volta para "/" (guardando a tela em "voltar": quem abriu um
    // link ou teve a sessão expirada volta para ela depois de entrar)
    if (!["/", "/cadastro", "/esqueci-senha"].includes(pathname)) return <Navigate to="/" replace state={{ voltar: pathname }} />;
    if (pathname === "/esqueci-senha") return <EsqueciSenha onVoltar={() => navegar("/")} />;
    return pathname === "/cadastro"
      ? <Cadastro aba={aba} onAba={mudarAba} onLogin={() => navegar("/")} />
      : <Login aba={aba} onAba={mudarAba} onCadastro={() => navegar("/cadastro")} onEsqueci={() => navegar("/esqueci-senha")} />;
  }

  // aluno sem plano ativo (ex.: 1º login após o cadastro): escolhe um plano antes de entrar
  if (usuario.perfil === "aluno") {
    if (planoOk === null) return null; // verificando o plano
    if (!planoOk) {
      return (
        <EscolherPlano onEscolhido={(mensagem) => {
          setPlanoOk(true);
          navegar("/pagamentos", { replace: true, state: { mensagem } }); // leva para a primeira mensalidade
        }} />
      );
    }
  }

  // endereço sem tela ou de uma tela que o perfil não acessa: vai para a tela guardada antes do login
  // (se o perfil puder vê-la) ou para a primeira tela do menu
  const permitidas = MENU.filter((m) => m.perfis.includes(usuario.perfil));
  const item = permitidas.find((m) => m.rota === pathname);
  if (!item) {
    const destino = permitidas.find((m) => m.rota === state?.voltar) || permitidas[0];
    return <Navigate to={destino.rota} replace />;
  }
  const atual = item.nome;

  return (
    <div className="app">
      <Sidebar atual={atual} onSelecionar={(rota) => { navegar(rota); setMenuAberto(false); }} aberto={menuAberto} />
      {menuAberto && <div className="backdrop" onClick={() => setMenuAberto(false)} aria-hidden="true" />}
      <main>
        <button className="menu-btn" onClick={() => setMenuAberto(!menuAberto)}
          aria-expanded={menuAberto} aria-label="Abrir menu">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M3 6h18M3 12h18M3 18h18" /></svg>
          Menu
        </button>
        {!HEADER_PROPRIO.has(item.rota) && <PageHeader eyebrow={item.eyebrow} title={atual} />}
        {atual === "Dashboard" ? <Dashboard />
          : atual === "Usuários" ? <Usuarios />
          : atual === "Meus dados" ? <MeusDados />
          : atual === "Pagamentos" ? <MeusPagamentos />
          : atual === "Check-in" ? (usuario.perfil === "aluno" ? <MeuCheckin /> : <CheckinRecepcao />)
          : atual === "Alunos" ? <Alunos />
          : atual === "Planos e matrículas" ? <PlanosMatriculas />
          : atual === "Aulas & Agenda" ? <Aulas />
          : atual === "Financeiro" ? <Financeiro />
          : atual === "Treinos" ? (usuario.perfil === "aluno" ? <MeusTreinos /> : <Treinos />)
          : atual === "Análise de postura" ? <Postura />
          : atual === "Relatórios" ? <Relatorios />
          : null}
      </main>
    </div>
  );
}