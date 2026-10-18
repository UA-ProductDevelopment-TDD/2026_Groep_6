# Zo gebruik je Git in dit project

Je hoeft Git niet te kennen om aan dit project te werken. Volg deze stappen in **GitHub Desktop**
en je kan niets kapotmaken. Ziet iets er raar uit? **Stop en vraag het aan Michael** (git manager)
voor je zelf iets probeert op te lossen.

> GitHub Desktop is in het Engels. De namen van knoppen staan hieronder daarom in het Engels,
> zodat je ze meteen terugvindt.

---

## De gouden regels

1. **Werk nooit op `main`.** Maak altijd eerst een branch (stap 2 hieronder).
2. **Blijf in je eigen map:** `hardware/`, `software/`, `ui/` of `docs/`.
3. **Eerst pullen, op het einde pushen.** Bij elke werksessie.
4. **Kleine Pull Requests.** Eén feature of fix per Pull Request, niet een hele week werk.
5. **Geen geheimen, geen grote bestanden.** Geen wachtwoorden of API-keys. Niets groter dan een paar MB.

---

## Eenmalig instellen (10 minuten)

1. Maak een GitHub-account (als je er nog geen hebt) en stuur je **gebruikersnaam** naar Michael.
2. Aanvaard de uitnodiging in de mail van GitHub (of ga naar
   <https://github.com/UA-ProductDevelopment-TDD/2026_Groep_6> en aanvaard ze daar).
3. Installeer **GitHub Desktop**: <https://desktop.github.com>
4. Open GitHub Desktop → **Sign in to GitHub.com** → log in met je account.
5. **File → Clone repository** → kies `UA-ProductDevelopment-TDD/2026_Groep_6` →
   kies een map op je pc (bv. `Documenten\GitHub`) → **Clone**.

Je hebt het project nu als gewone map op je pc.
Je kan de bestanden openen en bewerken met eender welk programma.

---

## Elke keer dat je aan het project werkt

### 1. Haal de laatste versie op
- Zet in GitHub Desktop **Current branch** (bovenaan in het midden) op `main`.
- Klik op **Fetch origin**, en daarna op **Pull origin** als die knop verschijnt.

### 2. Maak een branch voor je taak
- Klik op **Current branch → New branch**.
- Noem hem `<jouw-rol>/<wat-je-doet>`, met enkel kleine letters en streepjes. Voorbeelden:
  - `hw/servo-calibratie`
  - `sw/wandel-script`
  - `ui/startscherm`
  - `docs/verslag-week-3`
- Controleer dat er **based on `main`** staat → **Create branch**.

### 3. Doe je werk
Bewerk, maak of verwijder bestanden in de projectmap zoals altijd. Blijf in je eigen map.

### 4. Sla een momentopname op (commit)
- Ga terug naar GitHub Desktop. Links zie je de bestanden die je veranderd hebt.
- **Controleer de lijst!** Vink alles uit wat je niet bedoeld had te veranderen.
- Schrijf linksonder een korte **samenvatting** (Summary) van wat je gedaan hebt,
  bv. *"Servo-offsets voor de voorpoten toegevoegd"*.
- Klik op **Commit to `<jouw-branch>`**.

Commit zo vaak als je wil. Elke commit is een bewaarpunt waar je naar terug kan.

### 5. Upload je branch (push)
- Klik op **Publish branch** (de eerste keer) of **Push origin** (daarna).

Je werk staat nu veilig op GitHub, maar nog niet in `main`.

### 6. Vraag om het aan `main` toe te voegen (Pull Request)
- Klik op **Create Pull Request**. Je browser opent.
- Vul de checklist in die verschijnt en klik op **Create pull request**.
- Michael krijgt automatisch een melding en bekijkt je werk.

### 7. Als Michael om aanpassingen vraagt
- Blijf op dezelfde branch, maak de aanpassingen en doe opnieuw **commit** en **push** (stap 4–5).
- De Pull Request past zich vanzelf aan. Maak geen nieuwe.

### 8. Nadat je Pull Request gemerged is
- Zet **Current branch** terug op `main` en klik op **Fetch origin** / **Pull origin**.
- Begin je volgende taak met een **nieuwe branch** (stap 2).
- Verwijder de oude branch als je wil: **Branch → Delete…**.

---

## Als er iets misloopt

**"Ik heb per ongeluk iets veranderd terwijl ik op `main` zat" (nog niet gecommit)**
Klik op **Current branch → New branch**. GitHub Desktop vraagt wat het met je wijzigingen moet doen.
Kies **Bring my changes to the new branch**. Klaar.

**"Ik heb per ongeluk op `main` gecommit" (nog niet gepusht)**
Klik linksonder op **Undo** (naast je laatste commit). Je wijzigingen komen terug.
Doe daarna de oplossing hierboven.

**"Push was rejected" / "protected branch"**
Je zit op `main`. Niemand kan rechtstreeks naar `main` pushen, en dat is met opzet.
Gebruik de oplossingen hierboven om je werk naar een branch te verplaatsen.

**"Merge conflict"**
Jij en iemand anders hebben hetzelfde stuk van hetzelfde bestand veranderd. **Geen paniek en
klik niet zomaar ergens op.** Stuur Michael een berichtje met een screenshot.

**"Ik heb iets verwijderd / kapotgemaakt"**
Nog niet gecommit? Rechtsklik op het bestand in GitHub Desktop → **Discard changes**.
Het bestand staat dan terug zoals bij je laatste commit.
Al gecommit of gepusht? Laat het Michael weten. In Git gaat nooit echt iets verloren.

**Gouden regel bij problemen:** kopieer geen commando's van het internet. Vraag het aan Michael.

---

## Grote bestanden

GitHub weigert bestanden groter dan **100 MB**, en de repo wordt traag met veel grote bestanden.

- **Oké in Git:** code, tekst, kleine afbeeldingen, pdf's, STL/STEP-exports van een paar MB.
- **Niet in Git:** video's, ruwe CAD-projecten, renders, zip-bestanden, datasets.
  Zet die op de gedeelde drive van het team en zet een **link** in een README.

---

## Woordenlijst

| Woord | Betekenis |
|---|---|
| **Repository (repo)** | De projectmap, bewaard op GitHub |
| **Clone** | De repo naar je pc downloaden (maar één keer) |
| **Branch** | Je eigen kopie om in te werken, zonder `main` aan te raken |
| **`main`** | De officiële, werkende versie van het project |
| **Commit** | Een bewaarpunt met een korte beschrijving |
| **Push** | Je commits naar GitHub uploaden |
| **Pull / Fetch** | De laatste wijzigingen van GitHub downloaden |
| **Pull Request (PR)** | Een vraag om je branch aan `main` toe te voegen |
| **Merge** | Een branch echt aan `main` toevoegen (doet Michael) |
| **Conflict** | Twee mensen hebben dezelfde regels veranderd. Vraag het aan Michael |
