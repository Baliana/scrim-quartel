-- Schema de referência (MySQL) — gerado a partir de app/models.py.
-- As tabelas são criadas automaticamente pelo SQLAlchemy (Base.metadata.create_all);
-- este arquivo serve apenas como documentação / consulta manual do banco.

CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
    telefone VARCHAR(20) NULL COMMENT 'formato E.164, ex: +5511999999999',
    tipo ENUM('cliente','admin') NOT NULL DEFAULT 'cliente',
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em DATETIME NOT NULL,
    atualizado_em DATETIME NOT NULL
);

CREATE TABLE categorias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE,
    descricao TEXT NULL,
    criado_em DATETIME NOT NULL
);

CREATE TABLE materiais (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    descricao TEXT NULL,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    categoria_id INT NOT NULL,
    quantidade_total INT NOT NULL DEFAULT 0,
    tempo_maximo_dias INT NOT NULL DEFAULT 7,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em DATETIME NOT NULL,
    atualizado_em DATETIME NOT NULL,
    FOREIGN KEY (categoria_id) REFERENCES categorias(id)
);
-- Observação: quantidade_disponivel NÃO existe como coluna. Ela é sempre calculada
-- em tempo real (quantidade_total menos a soma dos empréstimos ativos/atrasados),
-- para nunca divergir da realidade do estoque.

CREATE TABLE emprestimos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL COMMENT 'cliente que retirou o material',
    material_id INT NOT NULL,
    registrado_por_id INT NULL COMMENT 'admin que registrou a retirada, se aplicável',
    quantidade INT NOT NULL DEFAULT 1,
    data_emprestimo DATETIME NOT NULL,
    data_devolucao_prevista DATE NOT NULL,
    data_devolucao_real DATETIME NULL,
    status ENUM('ativo','devolvido','atrasado','cancelado') NOT NULL DEFAULT 'ativo',
    criado_em DATETIME NOT NULL,
    atualizado_em DATETIME NOT NULL,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (material_id) REFERENCES materiais(id),
    FOREIGN KEY (registrado_por_id) REFERENCES usuarios(id)
);

CREATE TABLE movimentacoes_estoque (
    id INT AUTO_INCREMENT PRIMARY KEY,
    material_id INT NOT NULL,
    emprestimo_id INT NULL,
    tipo ENUM('entrada','saida','devolucao','perda','danificado','ajuste') NOT NULL,
    quantidade INT NOT NULL,
    motivo VARCHAR(255) NULL,
    usuario_id INT NOT NULL COMMENT 'quem registrou a movimentação',
    criado_em DATETIME NOT NULL,
    FOREIGN KEY (material_id) REFERENCES materiais(id),
    FOREIGN KEY (emprestimo_id) REFERENCES emprestimos(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

CREATE TABLE whatsapp_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL COMMENT 'cliente destinatário',
    emprestimo_id INT NULL,
    tipo ENUM('lembrete_devolucao','atraso','confirmacao_devolucao','outro') NOT NULL DEFAULT 'outro',
    mensagem TEXT NOT NULL,
    twilio_sid VARCHAR(64) NULL,
    status_envio ENUM('enviado','falha') NOT NULL,
    erro TEXT NULL,
    criado_em DATETIME NOT NULL,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (emprestimo_id) REFERENCES emprestimos(id)
);
