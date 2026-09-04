# Sincronizzare le modifiche (push/pull) — promemoria rapido

Il flusso di lavoro di questo progetto: il codice si sviluppa su un PC (questo), si pubblica su GitHub (`git push`), e sul PC/server del cliente si aggiorna con `git pull`. Nessuno dei due lati fa push automaticamente.

## Pubblicare le modifiche locali (da questo PC)

```bash
git status
```
Controlla cosa sta per essere inviato — utile prima di un push per non mandare file inattesi.

```bash
git push
```
Invia i commit locali al repository GitHub (`https://github.com/alf451/SPC.git`, branch `main`). Chiede username/password (o token) solo la prima volta, poi usa le credenziali salvate da Windows/Git.

Se il push viene rifiutato con "rejected... fetch first" (qualcuno ha pushato nel frattempo, es. da un'altra macchina):
```bash
git pull
git push
```

## Aggiornare il PC/server del cliente

```bash
cd E:\leank-spc
git status
```
**Importante**: se compare qualcosa come "modified: installer/install.ps1" senza che tu abbia toccato quel file, è quasi certamente solo rumore di fine riga di Windows (vedi [`problemi-riscontrati.md`](problemi-riscontrati.md)) — verifica con `git diff installer/install.ps1` che non ci sia altro, poi:
```bash
git checkout -- installer/install.ps1
```
prima di continuare, altrimenti `git pull` si rifiuta con "local changes would be overwritten".

```bash
git pull
```
Scarica gli ultimi commit, incluso `frontend/dist/` già pronto (non serve `npm run build` sul PC del cliente).

**Dopo ogni pull, riavvia sia il backend che l'Edge Agent** se erano già in esecuzione — nessuno dei due ricarica da solo il codice aggiornato:
```bash
installer\stop.cmd
installer\start.cmd
```
Per l'Edge Agent: Ctrl+C nella sua finestra, poi rilancialo con lo stesso comando usato la prima volta (vedi `edge-agent/README.md`).

## Verificare che tutto sia allineato

```bash
git log --oneline -1
```
Confronta l'hash del commit mostrato con quello che vedi su GitHub (`https://github.com/alf451/SPC/commits/main`) — se coincide, quella macchina ha davvero l'ultima versione.

```bash
git log origin/main --oneline -1
```
Mostra l'ultimo commit **sul server GitHub** senza scaricarlo — utile per sapere se conviene fare un pull prima di iniziare a lavorare, senza doverlo prima fare per scoprirlo.
