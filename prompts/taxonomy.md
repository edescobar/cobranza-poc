# Taxonomy (starter) — refine with Martín Porta

The single highest-leverage input. Keep it **small and closed** (~8 objections, ~10 tactics). It's
mirrored in `db/schema.sql`; change it in both places (and re-label) if you edit it. Add new entries
only when a real cluster of calls doesn't fit an existing one.

## Objection types (what the debtor is doing)

| key | español |
|---|---|
| `sin_dinero` | No tiene plata / no puede pagar ahora |
| `ya_pague` | Afirma que ya pagó |
| `desconoce_deuda` | No reconoce la deuda / "¿quién habla?" |
| `posterga` | "Llámenme después / la semana que viene" |
| `pago_parcial` | Ofrece pagar solo una parte |
| `molesto` | Hostil, enojado, a la defensiva |
| `persona_equivocada` | "No soy yo / número equivocado" |
| `promesa_vaga` | Dice que va a pagar pero sin fecha |

## Tactics (the agent's move)

| key | español |
|---|---|
| `empatia_y_plan` | Validar + ofrecer plan en cuotas |
| `anclar_fecha` | Fijar fecha concreta y cercana |
| `ofrecer_cuotas` | Dividir en pagos más chicos |
| `urgencia_beneficio` | Consecuencia de no pagar / beneficio de pagar ya |
| `validar_y_verificar` | Reconocer el reclamo + ofrecer verificar |
| `reformular_monto` | Bajar a un monto inicial alcanzable |
| `prueba_social` | "Otros en tu situación resolvieron así" |
| `descuento_condicional` | Quita/descuento si paga hoy |
| `confirmar_compromiso` | Cerrar repitiendo el compromiso concreto |
| `escalar_derivar` | Derivar a humano/supervisor |

## Why closed + why we log failures too

- A small closed set makes `(objection, tactic)` countable → you can rank what converts.
- We tag **every** agent turn, winners and losers — you need the losers to rank tactics and, later,
  to build DPO pairs (winning-vs-losing move for the same objection).
