// Cabeçalho padrão das telas: rótulo pequeno (eyebrow) + título grande + ações opcionais à direita.
export default function PageHeader({ eyebrow, title, children }) {
  return (
    <header className="pagehead">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1 className="title-xl">{title}</h1>
      </div>
      {children && <div className="acoes">{children}</div>}
    </header>
  );
}
