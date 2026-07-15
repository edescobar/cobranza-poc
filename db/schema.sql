-- cobranza-poc — pattern store (call_turns) + rollup (pattern_stats)
-- The unit of a "pattern" is: situation (objection) -> move (tactic) -> outcome (paid?).

-- ---- reference taxonomy (small + closed; refine with Martín Porta) ----
CREATE TABLE objection_types (
  objection_type TEXT PRIMARY KEY,
  description_es  TEXT NOT NULL
);

CREATE TABLE tactics (
  tactic         TEXT PRIMARY KEY,
  description_es TEXT NOT NULL
);

-- ---- calls + turns ----
CREATE TABLE calls (
  call_id         TEXT PRIMARY KEY,
  customer        TEXT,
  debtor_id_hash  TEXT,
  source          TEXT DEFAULT 'human',      -- 'human' | 'ai'
  call_ts         TIMESTAMPTZ,
  promise_made    BOOLEAN,
  promise_kept    BOOLEAN,
  amount_promised NUMERIC,
  amount_paid     NUMERIC,
  days_to_payment INT
);

CREATE TABLE call_turns (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  call_id           TEXT NOT NULL REFERENCES calls(call_id) ON DELETE CASCADE,
  turn_index        INT  NOT NULL,
  speaker           TEXT NOT NULL CHECK (speaker IN ('agent','debtor')),
  text              TEXT NOT NULL,           -- PII-scrubbed
  seconds_into_call NUMERIC,
  objection_type    TEXT REFERENCES objection_types(objection_type),  -- set on debtor turns
  tactic            TEXT REFERENCES tactics(tactic),                  -- set on agent turns
  sentiment         TEXT,
  UNIQUE (call_id, turn_index)
);
CREATE INDEX idx_turns_call ON call_turns(call_id, turn_index);

-- each agent MOVE paired with the objection it answered (the debtor turn right before it)
CREATE VIEW pattern_moves AS
SELECT a.call_id, a.turn_index, d.objection_type, a.tactic
FROM call_turns a
JOIN call_turns d
  ON d.call_id   = a.call_id
 AND d.turn_index = a.turn_index - 1
 AND d.speaker   = 'debtor'
WHERE a.speaker = 'agent'
  AND a.tactic         IS NOT NULL
  AND d.objection_type IS NOT NULL;

-- which tactic converts best per objection (this IS the pattern library the API retrieves from)
CREATE VIEW pattern_stats AS
SELECT m.objection_type,
       m.tactic,
       COUNT(*)                                                    AS n,
       ROUND(AVG((COALESCE(c.promise_kept, FALSE))::int)::numeric, 3) AS conversion_rate
FROM pattern_moves m
JOIN calls c ON c.call_id = m.call_id
GROUP BY m.objection_type, m.tactic;

-- ---- seed the closed taxonomy (reference data, always present) ----
INSERT INTO objection_types (objection_type, description_es) VALUES
  ('sin_dinero',        'Dice que no tiene plata o no puede pagar ahora'),
  ('ya_pague',          'Afirma que ya pagó la deuda'),
  ('desconoce_deuda',   'No reconoce la deuda o pregunta quién habla'),
  ('posterga',          'Pide que lo llamen después / la semana que viene'),
  ('pago_parcial',      'Ofrece pagar solo una parte'),
  ('molesto',           'Responde hostil, enojado o a la defensiva'),
  ('persona_equivocada','Dice que no es la persona / número equivocado'),
  ('promesa_vaga',      'Dice que va a pagar pero sin fecha concreta');

INSERT INTO tactics (tactic, description_es) VALUES
  ('empatia_y_plan',      'Validar la situación y ofrecer un plan de pago en cuotas'),
  ('anclar_fecha',        'Fijar una fecha concreta y cercana de pago'),
  ('ofrecer_cuotas',      'Dividir el monto en pagos más chicos y alcanzables'),
  ('urgencia_beneficio',  'Explicar la consecuencia de no pagar o el beneficio de pagar ya'),
  ('validar_y_verificar', 'Reconocer el reclamo y ofrecer verificar el pago o los datos'),
  ('reformular_monto',    'Bajar a un monto inicial que el deudor sí puede pagar'),
  ('prueba_social',       'Mencionar que otros en su situación resolvieron así'),
  ('descuento_condicional','Ofrecer una quita o descuento si paga hoy'),
  ('confirmar_compromiso','Cerrar repitiendo y confirmando el compromiso concreto'),
  ('escalar_derivar',     'Derivar a un humano o supervisor cuando conviene');
