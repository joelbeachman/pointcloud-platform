# Präsentation Montag — Struktur

Eine strukturierte Präsentation der Plattform, die Wissams Wunsch folgt:
*"Anwendungsfälle auflisten → pro Fall Daten → pro Fall Pipeline → pro Fall Demo."*

**Rahmensetzung:** Jede Demo wird **explizit** an die fünf
Forschungsfragen (RQ1–RQ5) gekoppelt — so wird klar, dass die
Plattform keine isolierte Lösung ist, sondern eine konkrete Antwort
auf das im Bericht (`pointclouds.tex` § 1) formulierte Problem.

Die direkten Antworten auf Wissams Fragen sind in **Teil 1** integriert,
bevor wir in die Use Cases einsteigen — so verlieren wir nicht den Überblick,
indem wir über einzelne Lösungen diskutieren.

**Dauer-Empfehlung:** 25–30 Min Präsentation + 15–20 Min Diskussion.

---

## Teil 0 · Titel, Übersicht, Forschungsfragen (2 Slides)

### Slide 0.1 — Titel

**Titel:** *Forschungsplattform Ballenberg — Stand und Anwendungsfälle*

**Slide-Inhalt:**
- Einleitungssatz: *"Eine Web-Plattform, die heterogene 3D- und Dokumentdaten zu historischen Gebäuden in einer einheitlichen Oberfläche bündelt."*
- Vier Anwendungsfälle, die heute live demonstriert werden:
  1. **UC1** — Bauphasen eines Gebäudes vergleichen (Geb. 851)
  2. **UC2** — Gebäude im Dorfkontext darstellen
  3. **UC3** — Lastverteilung im Tragwerk visualisieren
  4. **UC4** — Punktwolke, Modelle, PDF und Video pro Gebäude (Geb. 351)

### Slide 0.2 — Verortung in den Forschungsfragen

Die fünf Forschungsfragen, an denen sich die Plattform messen lässt
(aus `documentation/pointclouds.tex` § 1):

| RQ  | Frage (gekürzt)                                                                                | Adressiert in …       |
|-----|------------------------------------------------------------------------------------------------|-----------------------|
| RQ1 | Wie strukturieren wir heterogene Datensätze, damit sie **skalierbar und zukunftssicher** sind? | Teil 2 (Architektur)  |
| RQ2 | Welche Web-Plattform — oder Kombination — bietet den **besten Trade-off** für die Nutzergruppen?| Teil 1.2, UC2, UC4    |
| RQ3 | Wie standardisieren wir TLS + Photogrammetrie + Mesh in **eine Pipeline** für das Web?          | Teil 2, UC1, UC4      |
| RQ4 | Wie verknüpfen wir **semantische Metadaten** mit 3D-Visualisierungen?                          | UC4 (zentral), UC1    |
| RQ5 | Welche **Ballenberg-Datensätze** eignen sich als Prototyp, und wie kommunizieren sie an die Nutzergruppen? | Alle 4 Use Cases       |

**Botschaft:** *"Jeder Use Case ist eine konkret implementierte Antwort
auf mindestens eine Forschungsfrage. Wir zeigen heute funktionierende
Prototypen — nicht Theorie."*

---

## Teil 1 · Wissams Fragen — direkte Antworten (2 Slides)

Beide Fragen oben in der Präsentation klären, damit sie nicht später den Faden zerreißen.

### Slide 1.1 — "Was meinst du mit Datensätzen?"

**Antwort:** Alles. Die Plattform ist datentyp-agnostisch.

Eine Tabelle mit den heutigen `type`-Werten aus `datasets.json` (Stand: 159 Einträge):

| `type`         | Beschreibung                                  | Beispiel im Demo                  |
|----------------|-----------------------------------------------|-----------------------------------|
| `cesium`       | 3D Tiles (Modelle, Punktwolken georef.)       | Bauphasen von 851, Haus 351 LiDAR |
| `potree`       | Potree-Oktrees (sehr große Punktwolken)       | Haus Eggiwil 5 M Punkte           |
| `cesium-splat` | Gaussian Splats in Cesium                     | Gruppe6                           |
| `splat`        | Gaussian Splats im eigenen Viewer             | Nike-Splat                        |
| `panorama`     | Equirektangulare Panoramen                    | Haus Eggiwil 185 Scan-Positionen  |
| `e57`          | TLS-Rohscans                                  | Test Bauing                       |
| `document`     | PDFs                                          | Bauernhaus Eggiwil BE             |
| `video`        | mp4 oder YouTube-Embed                        | Drohnenflug Eggiwil 1:35–1:39     |

Botschaft: *"Die Plattform-Logik trennt strikt 'Was ist es' (type) von 'Wo gehört es hin' (building). Jeder neue Datentyp ist eine neue Zeile in derselben Katalog-Datei."*

### Slide 1.2 — "Wie werden andere Datentypen integriert? Kann Potree alles abdecken?"

**Antwort kurz:** Potree macht nur **eine** Sache: massive Punktwolken. Für alles andere setzen wir den richtigen Renderer ein — alle in derselben Oberfläche.

Tabelle: ein Renderer pro Datentyp, alle gleichwertig im Layer-Panel kombinierbar.

| Datentyp       | Renderer                                                 |
|----------------|----------------------------------------------------------|
| 3D Tiles       | **CesiumJS 1.140** (Hauptviewer)                         |
| Potree-Wolken  | **Potree 1.8** (WebGL) / **Potree-Next** (WebGPU)        |
| Gaussian Splats| **gaussian-splats-3d** (Three.js) + Cesium-Splat-Erweiterung |
| Panoramen      | **Pannellum 2.5.6** als Overlay über Cesium              |
| PDFs           | Browser-eigener PDF-Viewer im Slide-out                  |
| Videos         | HTML5 `<video>` oder YouTube-iframe als PIP              |

**Schlüsselpunkt für Wissam:**

> Die Antwort auf "andere Datentypen" ist nicht "wir bauen Potree erweitert" —
> sondern **"alle Datentypen sind erst-klassige Layer, die kontextuell an
> ein Gebäude gekoppelt sind."** Heute Demo: in UC4 sehen Sie PDF + Video
> direkt neben der Punktwolke desselben Gebäudes (Geb. 351).

---

## Teil 2 · Plattform-Architektur (1 Slide, max. 2 Min)

Eine vereinfachte Pipeline-Skizze (Quelle: `documentation/PIPELINE.md` Abschnitt 1):

```
Rohdaten   →   Verarbeitung   →   data/   →   Express + REST API   →   Browser-Viewer
LiDAR          Python-Skripte    3D Tiles      datasets.json            Cesium · Potree
.blend         Blender headless  Potree                                 Splat · PDF
.pdf / .mp4    (gltfpack...)     Splats                                 Video · Pano
```

**Zentrale Idee:** Eine einzige Datei (`datasets.json`) verbindet alles. Sie hat 159 Einträge und ist die einzige Stelle, an der die Plattform "weiß", welche Daten zu welchem Gebäude gehören.

Schlüssel-Felder pro Eintrag (Beispiel-Eintrag zeigen):
```json
{
  "id":            "doc-351-bauernhaus-eggiwil",
  "type":          "document",
  "building":      "351",
  "buildingName":  "Bauernhaus Eggiwil",
  "path":          "/data/PDFs/351_Bauernhaus Eggiwil BE-low.pdf"
}
```

**Konsequenz:** Wir gruppieren die UI nach **`building`**, nicht nach `type`. Im Portal sieht man pro Haus EINE Karte mit allen zugehörigen Daten.

---

## Teil 3 · Use Cases (jeweils ~ 4 Min)

Für jeden Use Case dasselbe 4-teilige Schema:
**Anwendungsfall → Daten → Pipeline → Demo.**

---

### UC1 · Bauphasenvergleich (Geb. 851)

**Adressiert RQ3** (standardisierte Pipeline) **+ RQ4** (semantische Metadaten)
**+ RQ5** (Ballenberg-Prototyp).

**Anwendungsfall** *(mit Ricarda besprochen)*

> "Zeige mir, wie sich das Gebäude über sieben Bauphasen entwickelt hat,
> damit ich die Konstruktionsabfolge nachvollziehen kann."

**Forschungsbeitrag:** Ein Bauphase ist nicht nur eine Geometrie, sondern
trägt **semantische** Information (Phase Nummer, zeitliche Ordnung). Die
Plattform behandelt diese Metadaten gleichwertig zur Geometrie — die
Gruppierung im Layer-Panel folgt direkt aus dem `phase`-Feld in
`datasets.json` (→ RQ4).

**Daten**

- 1× "alle Phasen" Master-Tileset (`2025_851`)
- 7× einzelne Phasen-Tilesets (`1. Bauphase 851` ... `7. Bauphase 851`)
- Quelle: Blender-Sammlungen pro Phase im File `Gesamtsmodell_V3.blend`

**Pipeline**

```
Blender (.blend, 4,9 GB)
   │  scripts/export_blender_glb.py  (bpy)
   ▼
data/blender/export/buildings/{1..7}._Bauphase_851.glb    (je ~ 87 MB)
   │  scripts/generate_3dtiles.py  (pyproj, gltfpack)
   │  LV95 → ECEF Transformation
   │  LOD0 (volle Qualität) · LOD1 (30 %) · LOD2 (5 %)
   ▼
data/cesium/gesamtmodell/tileset_2025_851_*.json
   │  scripts/backfill_building_phase.py
   │  fügt building=851 / phase=N / phaseLabel hinzu
   ▼
data/datasets.json (registrierte Einträge)
   ▼
Cesium-Viewer: Layer-Panel gruppiert nach Gebäude, Phasen als klappbare Children
```

**Demo**

1. Öffne `http://localhost:3000/viewers/cesium.html?building=851`
2. Im linken Layer-Panel: "**Gebäude 851**" als Gruppen-Header mit 8 Children
3. Master-Checkbox umschalten → alle 7 Phasen auf einmal sichtbar/aus
4. Einzelne Phase 1 ↔ Phase 7 abwechselnd umschalten — Bauverlauf wird sichtbar
5. ⊕ Fly-to demonstrieren

**Talking Point:** Die Gruppierung im Layer-Panel kommt direkt aus `building` und `phase` in `datasets.json`. Wenn morgen ein 8. Bauphase exportiert wird, erscheint sie automatisch in der Gruppe — kein UI-Code muss angefasst werden.

---

### UC2 · Gebäude im Dorfkontext

**Adressiert RQ2** (Plattform-Trade-off — Kombination Cesium-Layer)
**+ RQ5** (Vermittlung an Besucher / Forscher).

**Anwendungsfall** *(mit Ricarda besprochen)*

> "Zeige mir das einzelne Gebäude eingebettet in seine ursprüngliche
> Dorfumgebung, damit Lage und Massstab erkennbar werden."

**Forschungsbeitrag:** Beantwortet RQ2 direkt: **kein** einzelner
Renderer kann diesen Use Case allein. Erst die Cesium-Plattform mit
georeferenzierter Multi-Layer-Architektur erlaubt das gleichzeitige
Einblenden von Gesamtmodell, Quartier-Layer und einzelnem Gebäude.

**Daten**

- `Gesamtmodell Eggiwil` (Haupt-Tileset: 132 Gebäude + Gelände als ein Layer)
- `Mit_Nummer (alle Phasen)` — alle nummerierten Häuser des Dorfes
- Einzelnes Gebäude (z. B. `1. Bauphase 851`) als Overlay

**Pipeline**

Identisch zu UC1 — wir nutzen einfach **mehrere** der bereits exportierten
Tilesets gleichzeitig. Das ist der Kernvorteil von 3D Tiles: jedes Gebäude
ist ein eigenständiger Layer, der mit anderen kombinierbar ist.

**Demo**

1. `cesium.html?id=gesamtmodell` — startet mit Gesamtmodell als Standardansicht
2. Add Layer → "Mit_Nummer (alle Phasen)" hinzu
3. Add Layer → "1. Bauphase 851" hinzu
4. Phase 1 von 851 wird im Dorfkontext sichtbar
5. Fly-to → zum Detail
6. Phasen weiter durchschalten → Entwicklung im Kontext

**Talking Point:** Hier zeigt sich der Vorteil der Modularität — jede Bauphase ist als eigenständiger Layer abrufbar und mit beliebig anderen Layern kombinierbar.

---

### UC3 · Lastverteilung im Tragwerk

**Adressiert RQ4** (Verknüpfung von semantischen Daten — hier:
strukturelle Eigenschaften — mit der 3D-Visualisierung)
**+ RQ5** (Konservierungs-Anwendungsfall).

**Anwendungsfall** *(mit Ricarda besprochen)*

> "Visualisiere die Lastverteilung im historischen Dachstuhl, damit
> kritisch beanspruchte Bereiche auf einen Blick erkennbar werden."

**Forschungsbeitrag:** Demonstriert die **Architektur-Bereitschaft**
für RQ4. Wir koppeln heute Plausibilitäts-Farben — der **Mechanismus**
(CustomShader, ein Eintrag pro Element in `datasets.json`) ist
identisch zu dem, der morgen reale FEM-Werte aufnimmt.

**Daten**

- 1× "alle Phasen" Master (`Tragwerk`)
- 7× Element-Tilesets: `Kehlbälken`, `Reihe_00` ... `Reihe_05`
- Quelle: Blender-Sammlung `Tragwerk` mit pro-Element Sub-Sammlungen

**Pipeline**

Zusätzlich zur Standard-Pipeline:
- CesiumJS **CustomShader** weist jeder Tragwerk-Element-Sammlung eine Farbe zu
- Farbskala empirisch nach erwarteter Last: rot (höchste Biegung) → grün (Mittelfeld)

```javascript
// Auszug aus cesium.html (Zeile ~1980)
const TRAGWERK_COLORS = {
  'Kehlbälken': '#e74c3c',  // rot: Biegung hoch
  'Reihe_00':   '#e67e22',  // orange: Außenfeld
  ...
  'Reihe_02':   '#2ecc71',  // grün: Mittelfeld
};
```

**Demo**

1. `cesium.html` öffnen (Standardansicht: Gesamtmodell)
2. Add Layer → "Tragwerk (alle Phasen)" → alle Elemente in ihren Farben
3. **Legende erscheint** unten links automatisch
4. Einzelne Reihen ein/ausschalten — selektive Analyse möglich

**Talking Point — wichtige Einschränkung:**
*"Die heutigen Farben sind eine **Plausibilitäts-Skala**, nicht eine berechnete Lastverteilung. Wenn ein Statiker reale FEM-Daten liefert, mappen wir die Werte 1:1 in dieselbe Shader-Logik — der Visualisierungsteil ist fertig."*

**Offene Frage an Wissam:** *Gibt es jemanden, der echte Bemessungsdaten beisteuern kann?*

---

### UC4 · Punktwolke + Modelle + PDF + Video (Geb. 351)

**Adressiert RQ1, RQ2, RQ3 UND RQ4 gleichzeitig.** Schlüssel-Demo.

**Anwendungsfall** *(neu — beantwortet Wissams Frage zu "andere Datentypen")*

> "Zeige mir alle digital verfügbaren Informationen zum Bauernhaus Eggiwil
> (Geb. 351) in einer interaktiven Oberfläche: Scan, Modell, Dokumentation,
> Videoaufnahmen."

**Forschungsbeitrag** — vier RQs in einem Use Case:

- **RQ1** *(Datenstruktur)*: Sieben Datensätze unterschiedlichen Typs werden
  durch dasselbe Schema (`building: "351"`) zu einer logischen Einheit
  verknüpft, ohne dass die Plattform "weiß", was ein Bauernhaus ist.
- **RQ2** *(Plattform-Trade-off)*: Cesium für Multi-Layer, Potree als
  Alternative für detaillierte Punktwolken-Inspektion, eigenständige
  PDF-/Video-Viewer — der Nutzer kann wählen, die Daten bleiben gleich.
- **RQ3** *(standardisierte Pipeline)*: TLS-Scan (E57) UND Blender-Modell
  UND PDF UND YouTube-Video laufen durch unterschiedliche Vorverarbeitungen,
  landen im **gleichen** Katalog.
- **RQ4** *(semantische Verknüpfung)*: PDFs erscheinen kontextuell **neben**
  der Punktwolke desselben Gebäudes — kein Suchen, kein Tab-Wechsel.

**Daten**

Sieben Einträge, ein Gebäude (`building: "351"`):

| Name                                        | Typ          | Quelle        |
|---------------------------------------------|--------------|---------------|
| Haus Eggiwil (LiDAR + Panoramen)            | `cesium`     | TLS (E57)     |
| Haus Eggiwil (Potree)                       | `potree`     | TLS (E57)     |
| 351 (alle Phasen)                           | `cesium`     | Modell        |
| 2022_351                                    | `cesium`     | Modell        |
| 2025_351                                    | `cesium`     | Modell        |
| Bauernhaus Eggiwil BE — Dokumentation       | `document`   | Bericht (PDF) |
| Drohnenflug Eggiwil (Ausschnitt)            | `video`      | YouTube       |

**Pipeline** — drei Spuren

1. **LiDAR-Punktwolke**: `.e57` → `scripts/process.py` (pye57 + numpy) → 3D Tiles + Panorama-JPEGs + Pannellum-Metadaten
2. **Modelle**: Blender-Pipeline (siehe UC1)
3. **PDF/Video**: direkter Eintrag in `datasets.json`. Statisch ausgeliefert von Express. PDF → iframe-Slide-out. Video → YouTube-Embed als PIP.

```
data/laserscans/<scan>.e57   ─→  process.py  ─→  data/cesium/haus-eggiwil/  
data/blender/...             ─→  Blender-Pipeline (UC1)
data/PDFs/*.pdf              ─→  manuell in datasets.json eintragen
data/videos/*.mp4 ODER       ─→  manuell in datasets.json (youtubeId)
```

**Demo** — Schlüssel-Demo der Sitzung

1. **Portal öffnen** (`http://localhost:3000`) — eine Karte pro Haus mit Buttons "3D-Viewer", "Potree", "PDF", "Video"
2. Karte "**351 — Bauernhaus Eggiwil**" → **"Im 3D-Viewer öffnen"**
3. Cesium-Viewer lädt **alle** zum Gebäude gehörenden Datensätze gleichzeitig:
   - LiDAR-Punktwolke standardmäßig sichtbar (Standardregel: Punktwolke an, Modelle aus)
   - 3 Modell-Layer geladen aber unsichtbar — zum An/Aus-Schalten bereit
   - Rechte Seitenleiste: "**Dokumente & Medien · 351 — Bauernhaus Eggiwil**" listet PDF + Video
4. **PDF anklicken** → Slide-out öffnet sich neben der 3D-Szene; **Punktwolke bleibt interaktiv** (Klick zum Beweis: PDF auf, gleichzeitig Punktwolke drehen)
5. **Video anklicken** → YouTube-PIP startet bei 1:35 (Drohnenausschnitt der Stallscheune in Meggen — ach, gleicher Workflow für Eggiwil-Videos)
6. Modell-Phase einzuschalten und gegen die Punktwolke abzugleichen

**Talking Point — zentrale Antwort an Wissam:**

> "Andere Datentypen werden NICHT in einem separaten Tab eingebaut. Sie sind
> **kontextuell zum aktiven Gebäude** in der 3D-Szene verlinkt. Das Muster
> ist datentyp-agnostisch — derselbe Mechanismus funktioniert morgen für
> Audio-Interviews, Texte oder historische Karten."

---

## Teil 4 · Stand der Dinge & offene Punkte (2 Slides)

### Slide 4.1 — Was funktioniert heute

| Status | Komponente                                        |
|--------|---------------------------------------------------|
| ✓      | 159 Datensätze in 94 Gebäuden katalogisiert        |
| ✓      | Vollständige Blender-Pipeline (export → 3D Tiles → Web) |
| ✓      | Vier Renderer parallel: Cesium, Potree (1.8 + Next), Splat |
| ✓      | Phasen-Gruppierung im Layer-Panel                  |
| ✓      | Dokumente & Medien pro Gebäude                     |
| ✓      | Helmert-Georeferenzierung (LV95 → WGS84/ECEF)      |
| ✓      | Swisstopo-Zeitreise-Overlay (1864–heute)           |
| ✓      | Cesium-Viewer 4341 Zeilen, ein Drittel davon Geo-Logik |

### Slide 4.2 — Offene Punkte & Roadmap

**Bekannte Schwachstellen:**

- **Blender-Datei** ist 4,9 GB — Risiko für Datenverlust und langsame Iteration. Lösung in `PIPELINE.md`: per-Gebäude-`.blend` statt Monolith.
- **Gebäude 752** — Bauphase 1 vs. 2 müssen in Blender sauber strukturiert werden. Heute: workaround via `MANUAL_RELABELS` im Backfill-Skript.
- **`datasets.json`** wird bei 500+ Einträgen zum Konfliktherd. Lösung: ein Dataset pro Datei in `data/datasets/`.

**Fragen für die Sitzung:**

1. *Welche **echten** Bemessungsdaten** kann ein Statiker liefern? (UC3)*
2. *Welche weiteren Datentypen sind im Zeitrahmen relevant — Audio, Pläne, historische Karten? (UC4 erweitern)*
3. *Pro Gebäude oder über das ganze Dorf hinweg — wie priorisieren wir die nächsten Datenerfassungen?*

---

## Teil 5 · Rückbindung an die Forschungsfragen (1 Slide — Abschluss)

Eine kompakte Matrix als Schlussbild:

| RQ  | Stand                                          | Gezeigt in        | Lücke / nächster Schritt                              |
|-----|------------------------------------------------|-------------------|-------------------------------------------------------|
| RQ1 | Schema steht, 159 Einträge, reproduzierbar     | Teil 2            | Migration zu pro-Datei-Katalog ab ~500 Einträgen      |
| RQ2 | Multi-Renderer-Architektur funktioniert        | Teil 1.2, UC2, UC4| Personas (Konservator / Forscher / Besucher) belegen  |
| RQ3 | Pipeline für TLS + Modell + Splat steht        | Teil 2, UC1, UC4  | Photogrammetrie-Spur erweitern (z. Z. COLMAP extern)  |
| RQ4 | PDF / Video kontextuell verknüpft (Geb. 351)   | UC4               | Reale FEM-Daten (UC3); Erweiterung auf Audio / Karten |
| RQ5 | Vier Use Cases live, davon einer mit allen Datentypen | UC1–UC4      | Nutzergruppen-Validierung in einer Pilotstudie         |

**Schlussbotschaft** (eine Folie / ein Satz):

> *"Die Plattform liefert eine konkrete, lauffähige Antwort auf RQ1, RQ3
> und RQ4. RQ2 und RQ5 brauchen für die endgültige Beantwortung Daten von
> realen Nutzerinnen und Nutzern — das ist der nächste Forschungsschritt
> über die Plattform-Entwicklung hinaus."*

---

## Anhang · Demo-Vorbereitung (nicht in Präsentation, nur intern)

**Vor der Sitzung prüfen:**

```bash
# 1. Server läuft
curl -s http://localhost:3000/api/health

# 2. Tilesets vorhanden
ls data/cesium/gesamtmodell/tileset.json && \
  ls data/cesium/gesamtmodell/tileset_2025_851_1._Bauphase_851.json

# 3. PDF und Video vorhanden
ls "data/PDFs/351_Bauernhaus Eggiwil BE-low.pdf"
curl -s http://localhost:3000/api/datasets/vid-351-drone-yk0sxdykx9w
```

**Demo-URLs für die Sitzung:**

| UC  | URL                                                                |
|-----|--------------------------------------------------------------------|
| UC1 | `http://localhost:3000/viewers/cesium.html?building=851`           |
| UC2 | `http://localhost:3000/viewers/cesium.html?id=gesamtmodell` + Add Layer |
| UC3 | `http://localhost:3000/viewers/cesium.html` + Add Tragwerk Layer    |
| UC4 | `http://localhost:3000` → Karte 351 → "Im 3D-Viewer öffnen"        |

**Reihenfolge der Demos:** UC4 zuerst nach den einleitenden Slides — beantwortet beide Wissams-Fragen direkt und visuell. UC1/2/3 danach in beliebiger Reihenfolge.

**Falls Internet ausfällt:** Cesium wird von CDN geproxied (siehe `server.js` Zeile 501); YouTube-Video funktioniert nicht offline. UC1, UC2, UC3 laufen vollständig lokal.

---

## Notiz zum finalen Präsentationsdokument

Diese Struktur ist die Diskussionsvorlage für Montag. Für die **endgültige
Präsentation** (laut Wissam) kann sie als Skelett dienen, ergänzt um:

- Konkrete Bildschirmaufnahmen jeder Demo
- Kennzahlen (Punktdichte, Bauphasen-Anzahl, etc.)
- Mögliche Erweiterungen pro UC

Die Reihenfolge und das 4-teilige Schema (**Anwendung → Daten → Pipeline → Demo**)
sollten beibehalten werden, damit Wissams Anliegen "Überblick statt Einzeldiskussion"
gewahrt bleibt.
