import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import Login from "./pages/Login.jsx";
import Cadastro from "./pages/Cadastro.jsx";
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
import Sidebar, { MENU } from "./components/Sidebar.jsx";

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

  if (carregando) return null;
  if (semConexao) {
    return (
      <section className="erro-pagina" role="alert">
        <div className="brand">Uni<b>Fit</b></div>
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
    if (pathname !== "/" && pathname !== "/cadastro") return <Navigate to="/" replace state={{ voltar: pathname }} />;
    return pathname === "/cadastro"
      ? <Cadastro aba={aba} onAba={mudarAba} onLogin={() => navegar("/")} />
      : <Login aba={aba} onAba={mudarAba} onCadastro={() => navegar("/cadastro")} />;
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
        <div className="top">
          <div>
            <button className="menu" onClick={() => setMenuAberto(!menuAberto)}
              aria-expanded={menuAberto} aria-label="Abrir menu">Menu</button>
            <h2>{atual}</h2>
            <span>{new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })}</span>
          </div>
        </div>
        {atual === "Dashboard" ? <Dashboard />
          : atual === "Usuários" ? <Usuarios />
          : atual === "Meus dados" ? <MeusDados />
          : atual === "Pagamentos" ? <MeusPagamentos />
          : atual === "Check-in" ? (usuario.perfil === "aluno" ? <MeuCheckin /> : <CheckinRecepcao />)
          : atual === "Alunos" ? <Alunos />
          : atual === "Planos e matrículas" ? <PlanosMatriculas />
          : atual === "Financeiro" ? <Financeiro />
          : atual === "Treinos" ? (usuario.perfil === "aluno" ? <MeusTreinos /> : <Treinos />)
          : atual === "Análise de postura" ? <Postura />
          : atual === "Relatórios" ? <Relatorios />
          : null}
      </main>
    </div>
  );
}