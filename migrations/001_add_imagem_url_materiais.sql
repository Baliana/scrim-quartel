-- Execute uma unica vez em bancos que ja existiam antes deste recurso.
-- Bancos criados pelo schema.sql atualizado ja possuem esta coluna.
ALTER TABLE materiais
    ADD COLUMN imagem_url VARCHAR(255) NULL COMMENT 'Caminho publico do PNG do material'
    AFTER codigo;
