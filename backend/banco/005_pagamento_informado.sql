-- O aluno não dá mais baixa sozinho: ele "informa" que pagou e a recepção confirma (ou recusa) no Financeiro.
-- Enquanto não é confirmada, a mensalidade continua pendente/atrasada.
ALTER TABLE "unifit".pagamentos ADD COLUMN IF NOT EXISTS informado_em timestamp with time zone;
ALTER TABLE "unifit".pagamentos ADD COLUMN IF NOT EXISTS informado_forma character varying(30);
