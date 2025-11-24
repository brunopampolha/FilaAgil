PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS services;
DROP TABLE IF EXISTS units;

CREATE TABLE units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    avg_wait_minutes INTEGER DEFAULT 30,
    latitude REAL,
    longitude REAL
);

CREATE TABLE services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    avg_service_minutes INTEGER DEFAULT 12,
    FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE CASCADE
);

CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    code TEXT NOT NULL UNIQUE,
    customer_name TEXT NOT NULL,
    priority_level INTEGER DEFAULT 0, -- 0 normal, 1 prioritário, 2 especial
    status TEXT NOT NULL DEFAULT 'waiting',
    estimated_wait_minutes INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    checkin_at TEXT,
    called_at TEXT,
    FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE CASCADE,
    FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
);

INSERT INTO units (name, address, city, state, avg_wait_minutes, latitude, longitude) VALUES
('UBS Jardim Aurora', 'Av. Paulista, 1200', 'São Paulo', 'SP', 35, -23.561, -46.655),
('Poupatempo Centro', 'Rua XV de Novembro, 350', 'Campinas', 'SP', 28, -22.905, -47.060);

INSERT INTO services (unit_id, name, description, avg_service_minutes) VALUES
(1, 'Renovação de cadastro SUS', 'Atualização de dados do paciente', 10),
(1, 'Retirada de medicamentos', 'Farmácia popular local', 8),
(2, '2ª via de documento', 'Emissão rápida de RG/CPF', 15),
(2, 'Atendimento prioritário 60+', 'Serviços gerais com prioridade', 12);

INSERT INTO tickets (unit_id, service_id, code, customer_name, priority_level, status, estimated_wait_minutes, created_at, checkin_at)
VALUES
(1, 1, 'A001', 'Camila Santos', 0, 'waiting', 20, datetime('now', '-10 minutes'), NULL),
(1, 2, 'B015', 'Joaquim Oliveira', 1, 'waiting', 5, datetime('now', '-5 minutes'), NULL),
(2, 4, 'P003', 'Patrícia Souza', 0, 'called', 0, datetime('now', '-40 minutes'), datetime('now', '-5 minutes'));
