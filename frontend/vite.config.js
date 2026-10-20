import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// host: true faz o Vite escutar em toda a rede (0.0.0.0), para acessar de outro aparelho pelo IP do PC.
// /api é repassado ao backend: o navegador fala só com o Vite (mesma origem), então funciona igual pelo
// IP da rede ou por localhost, sem depender do IP do PC no frontend/.env.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.API_PROXY_TARGET || "http://localhost:8000",
        rewrite: (caminho) => caminho.replace(/^\/api/, ""),
        xfwd: true, // repassa o IP real do aluno (o limite de login por IP depende disso)
      },
    },
  },
});
