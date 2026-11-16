// Marca UniFit (pacote oficial). variant "compacta" (padrão, p/ sidebar) ou "horizontal" (telas grandes).
const ARQ = {
  compacta: "/brand/unifit-logo-compacta-fundo-escuro.svg",
  horizontal: "/brand/unifit-logo-horizontal-fundo-escuro.svg",
};

export default function Logo({ variant = "compacta" }) {
  return (
    <span className={`logo logo-${variant}`}>
      <img src={ARQ[variant] || ARQ.compacta} alt="UniFit" />
    </span>
  );
}
