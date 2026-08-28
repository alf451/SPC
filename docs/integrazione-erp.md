# Integrazione con un ERP

leank-spc non si integra con un ERP specifico: espone endpoint REST generici che qualunque sistema (SAP, Zucchetti, un gestionale interno, uno script) può chiamare per comunicare una commessa e per sapere da quale attrezzatura/posizione viene un campione misurato.

Concetti chiave (vedi anche `docs/schema.sql`, sezione "v0.2"):

- **Tool** ("attrezzatura") — generalizza qualunque cosa produca pezzi in un evento produttivo: uno stampo a iniezione, una fustella, uno stampo di pressofusione, ... Ha un `position_count`: quanti articoli produce ogni evento (es. uno stampo a 4 cavità).
- **ToolPosition** ("posizione"/cavità) — una delle N posizioni di un Tool. Un campione misurato può essere taggato con la posizione da cui proviene.
- **WorkOrder** ("commessa") — l'unità di lavoro comunicata dall'ERP: prodotto, quantità, cliente. `external_system`/`external_id` tracciano da dove viene e rendono l'endpoint **idempotente**: rimandare la stessa commessa (stesso `external_system`+`external_id`) aggiorna invece di duplicare — utile per retry o sincronizzazioni periodiche.

## Esempio end-to-end — stampo a 4 cavità (caso Mopla)

Setup una tantum (o via pannello admin, scheda non ancora presente per i Tool — usare le API direttamente per ora):

```bash
TOKEN="<access_token da POST /api/auth/login>"

# 1. Creare lo stampo con le sue 4 cavità (position_count le genera automaticamente 1..4)
curl -X POST http://127.0.0.1:8000/api/tools \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "Stampo Flangia FL-2201", "tool_type": "mold", "position_count": 4}'
# -> {"id": 12, "name": "Stampo Flangia FL-2201", "tool_type": "mold", "position_count": 4, ...}

curl http://127.0.0.1:8000/api/tools/12/positions -H "Authorization: Bearer $TOKEN"
# -> [{"id":101,"position_no":1,...}, {"id":102,"position_no":2,...}, ...]
```

Quando l'ERP apre una commessa di produzione:

```bash
curl -X POST http://127.0.0.1:8000/api/work-orders \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "order_number": "WO-2026-0417",
    "part_id": 7,
    "customer": "Cliente Finale S.p.A.",
    "quantity_ordered": 4000,
    "external_system": "GestionaleMopla",
    "external_id": "ORD-88213"
  }'
# -> {"id": 55, "order_number": "WO-2026-0417", "status": "open", ...}
```

Un secondo invio con lo **stesso** `external_system`+`external_id` (es. l'ERP che ri-sincronizza la stessa commessa con quantità aggiornata) aggiorna la riga 55 invece di crearne una seconda.

Quando l'operatore avvia il collaudo in officina, il Run viene legato a commessa e stampo:

```bash
curl -X POST http://127.0.0.1:8000/api/runs \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"routine_id": 3, "station_id": 1, "name": "Collaudo WO-2026-0417", "work_order_id": 55, "tool_id": 12}'
```

E ogni misura può essere taggata con la cavità di provenienza (`tool_position_id`, opzionale — se omesso la misura resta valida, solo senza quella granularità):

```bash
curl -X POST http://127.0.0.1:8000/api/runs/{run_id}/measurements \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"feature_id": 42, "obs_no": 1, "value": 42.031, "captured_at": "2026-08-28T10:15:00Z", "tool_position_id": 101}'
```

Le misure che arrivano dall'Edge Agent via WebSocket possono includere la stessa informazione — vedi `docs/api.md`, protocollo `reading`.

## Perché "qualsiasi ERP"

Non c'è un adattatore per un ERP specifico perché non ne serve uno: `POST /api/work-orders` è un endpoint HTTP/JSON standard, autenticato con lo stesso JWT delle altre API. Qualunque sistema che sappia fare una chiamata HTTP (o anche solo eseguire uno script/cron con `curl`) può integrarsi, senza plugin o connettori dedicati da mantenere.
