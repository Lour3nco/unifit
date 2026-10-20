import axios from "axios";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("gymai_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function mensagemErro(err, padrao = "Algo deu errado. Tente novamente.") {
  if (!err.response) return "Erro 503: serviço indisponível no momento. Tente novamente em alguns instantes.";
  const detalhe = err.response.data?.detail;
  if (typeof detalhe === "string") return detalhe;
  if (Array.isArray(detalhe)) {
    // mensagens dos nossos validadores vêm como "Value error, CPF inválido."; as padrão (em inglês) não são mostradas
    const msg = String(detalhe[0]?.msg || "");
    return msg.startsWith("Value error, ") ? msg.slice(13) : "Dados inválidos. Confira os campos e tente de novo.";
  }
  return padrao;
}

export default api;
