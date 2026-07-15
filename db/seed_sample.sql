-- Sample scrubbed calls so the UI + pattern_stats work before real data lands.
-- Outcomes are set so a clear winner emerges per objection (e.g. empatia_y_plan beats
-- urgencia_beneficio for sin_dinero). Replace with real Deepgram'd calls via pipeline/.

INSERT INTO calls (call_id, customer, debtor_id_hash, source, promise_made, promise_kept) VALUES
  ('c1','DemoCo','h001','human', TRUE,  TRUE),
  ('c2','DemoCo','h002','human', TRUE,  FALSE),
  ('c3','DemoCo','h003','human', TRUE,  TRUE),
  ('c4','DemoCo','h004','human', TRUE,  TRUE),
  ('c5','DemoCo','h005','human', TRUE,  TRUE),
  ('c6','DemoCo','h006','human', TRUE,  TRUE);

INSERT INTO call_turns (call_id, turn_index, speaker, text, objection_type, tactic) VALUES
  -- c1: sin_dinero -> empatia_y_plan -> pagó
  ('c1',0,'agent','Buenas, le hablo de [EMPRESA] por un saldo pendiente.', NULL, NULL),
  ('c1',1,'debtor','Uy, no tengo plata este mes.', 'sin_dinero', NULL),
  ('c1',2,'agent','Entiendo, no hay problema. Podemos dividirlo en dos pagos chicos, asi te acomoda mejor.', NULL, 'empatia_y_plan'),

  -- c2: sin_dinero -> urgencia_beneficio -> NO pagó
  ('c2',0,'agent','Hola, le llamo de [EMPRESA] por su cuenta.', NULL, NULL),
  ('c2',1,'debtor','No puedo pagar ahora, no tengo.', 'sin_dinero', NULL),
  ('c2',2,'agent','Mire, si no regulariza hoy la deuda sigue creciendo con intereses.', NULL, 'urgencia_beneficio'),

  -- c3: pago_parcial -> reformular_monto -> pagó
  ('c3',0,'agent','Buenas, le contacto por el saldo con [EMPRESA].', NULL, NULL),
  ('c3',1,'debtor','Puedo pagar la mitad nomas.', 'pago_parcial', NULL),
  ('c3',2,'agent','Perfecto, arranquemos con esa mitad hoy y el resto lo vemos la proxima semana.', NULL, 'reformular_monto'),

  -- c4: ya_pague -> validar_y_verificar -> pagó (regularizó)
  ('c4',0,'agent','Hola, le hablo de [EMPRESA] por un pago pendiente.', NULL, NULL),
  ('c4',1,'debtor','Yo ya pague eso, no me molesten.', 'ya_pague', NULL),
  ('c4',2,'agent','Le pido disculpas. Verifiquemos juntos: me confirma la fecha y ya lo dejo registrado.', NULL, 'validar_y_verificar'),

  -- c5: posterga -> anclar_fecha -> pagó
  ('c5',0,'agent','Buenas, le llamo de [EMPRESA].', NULL, NULL),
  ('c5',1,'debtor','Llamenme la semana que viene.', 'posterga', NULL),
  ('c5',2,'agent','Dale. Dejemos agendado el viernes a la manana para el pago, asi queda cerrado.', NULL, 'anclar_fecha'),

  -- c6: sin_dinero -> empatia_y_plan -> pagó (reinforces the winner)
  ('c6',0,'agent','Hola, le contacto de [EMPRESA] por su saldo.', NULL, NULL),
  ('c6',1,'debtor','La verdad no me alcanza para pagarlo.', 'sin_dinero', NULL),
  ('c6',2,'agent','Te entiendo. Armemos un plan en cuotas comodas para que no te pese.', NULL, 'empatia_y_plan');
