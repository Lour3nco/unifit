"""Gera banco/schema.sql com a estrutura atual do schema "unifit" (tipos, sequências, tabelas e restrições).

    python exportar_schema.py

Rode de novo sempre que mudar o banco, para o arquivo acompanhar o código. Não exporta dados.
"""
# pyright: reportMissingImports=false
from pathlib import Path

from sqlalchemy import text

from app.database import DB_SCHEMA, engine

S = f'"{DB_SCHEMA}"'
saida = [f"-- Estrutura do schema {DB_SCHEMA} (gerado por exportar_schema.py; não editar à mão)",
         f"CREATE SCHEMA IF NOT EXISTS {S};", ""]

with engine.connect() as c:
    for nome, rotulos in c.execute(text("""
            select t.typname, array_agg(quote_literal(e.enumlabel) order by e.enumsortorder)
            from pg_type t join pg_enum e on e.enumtypid = t.oid join pg_namespace n on n.oid = t.typnamespace
            where n.nspname = :s group by t.typname order by t.typname"""), {"s": DB_SCHEMA}):
        saida.append(f"CREATE TYPE {S}.{nome} AS ENUM ({', '.join(rotulos)});")
    saida.append("")

    for (seq,) in c.execute(text("select sequencename from pg_sequences where schemaname = :s order by 1"),
                            {"s": DB_SCHEMA}):
        saida.append(f"CREATE SEQUENCE IF NOT EXISTS {S}.{seq};")
    saida.append("")

    tabelas = c.execute(text("select tablename from pg_tables where schemaname = :s order by 1"), {"s": DB_SCHEMA}).scalars().all()
    for tab in tabelas:
        colunas = c.execute(text("""
            select a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull, pg_get_expr(d.adbin, d.adrelid)
            from pg_attribute a left join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum
            where a.attrelid = (:t)::regclass and a.attnum > 0 and not a.attisdropped order by a.attnum"""),
                             {"t": f'{S}.{tab}'}).all()
        linhas = [f"    {n} {tipo}" + (f" DEFAULT {padrao}" if padrao else "") + (" NOT NULL" if nn else "")
                  for n, tipo, nn, padrao in colunas]
        restricoes = c.execute(text("""
            select conname, pg_get_constraintdef(oid) from pg_constraint
            where conrelid = (:t)::regclass and contype in ('p', 'u', 'c') order by contype desc, conname"""),
                               {"t": f'{S}.{tab}'}).all()
        linhas += [f"    CONSTRAINT {n} {d}" for n, d in restricoes]
        saida += [f"CREATE TABLE {S}.{tab} (", ",\n".join(linhas), ");", ""]

    # chaves estrangeiras por último: as tabelas referenciadas já existem
    for tab, n, d in c.execute(text("""
            select rel.relname, con.conname, pg_get_constraintdef(con.oid) from pg_constraint con
            join pg_class rel on rel.oid = con.conrelid join pg_namespace ns on ns.oid = rel.relnamespace
            where ns.nspname = :s and con.contype = 'f' order by 1, 2"""), {"s": DB_SCHEMA}):
        saida.append(f"ALTER TABLE {S}.{tab} ADD CONSTRAINT {n} {d};")

destino = Path(__file__).parent / "banco" / "schema.sql"
destino.parent.mkdir(exist_ok=True)
destino.write_text("\n".join(saida) + "\n", encoding="utf-8")
print(f"Gerado {destino} ({len(tabelas)} tabelas)")
