# Pipeline-Häppchen für die Präsentation

Kurze, eigenständige Erklärungen, die du beliebig in die Präsentation
einbauen kannst. Jeder Punkt = ein Slide oder eine 30-Sekunden-Erklärung.

Reihenfolge ist **nicht** verbindlich — picke heraus, was zur Story passt.

---

## A · Das große Bild (3 Bites)

### A1 — Die Plattform in einem Satz

> *"Eine Web-Plattform, die Rohdaten verschiedener Herkunft in eine
> gemeinsame Sprache übersetzt und im Browser darstellbar macht."*

Drei Säulen:

1. **Vorverarbeitung** (Python + Blender): Rohdaten → Standardformate
2. **Katalog** (`datasets.json`): zentrale Registrierung aller Datensätze
3. **Viewer** (CesiumJS, Potree, …): liest aus dem Katalog, rendert im Browser

---

### A2 — Drei Ebenen statt einer

```
        Rohdaten                    Verarbeitet                Ausgeliefert
   ┌──────────────┐              ┌──────────────┐           ┌──────────────┐
   │ .blend       │              │ 3D Tiles     │           │ Cesium       │
   │ .e57 / .las  │  scripts/    │ Potree       │  Express  │ Potree       │
   │ .pdf / .mp4  │  ──────────▶ │ Splats       │  ───────▶ │ Splat-Viewer │
   │ Fotos        │  pipeline    │ Panoramen    │  /api/    │ PDF / Video  │
   └──────────────┘              └──────────────┘           └──────────────┘
       (Archiv)                    (data/)                    (Browser)
```

**Botschaft:** *"Die drei Ebenen sind klar getrennt. Wer Rohdaten ändert,
muss die Verarbeitung neu starten. Wer den Viewer ändert, muss nichts
neu rechnen."*

---

### A3 — Warum nicht alles in Potree?

| Datentyp                      | Optimaler Renderer                |
|-------------------------------|-----------------------------------|
| Punktwolken (10 M+)           | Potree (Octree, Streaming)        |
| Punktwolken georef. + Modelle | Cesium (Globus, 3D Tiles)         |
| Gaussian Splats               | gaussian-splats-3d / Cesium-Splat |
| Panoramen                     | Pannellum                         |
| Dokumente                     | Browser PDF-Viewer                |
| Videos                        | HTML5 / YouTube-Embed             |

*"Jeder Renderer macht eine Sache richtig gut. Wir setzen den richtigen
ein — und kombinieren sie in einer einheitlichen Oberfläche."*

---

## B · Der Katalog `datasets.json` (3 Bites)

### B1 — Die zentrale Datei

Eine einzige JSON-Datei, **159 Einträge** heute, **eine Quelle der Wahrheit**.

Jeder Eintrag beantwortet drei Fragen:

| Frage                  | Feld          | Beispiel                          |
|------------------------|---------------|-----------------------------------|
| Was ist es?            | `type`        | `cesium` · `potree` · `document`  |
| Wo gehört es hin?      | `building`    | `351`                             |
| Wo liegt die Datei?    | `path`        | `/data/PDFs/351_…pdf`             |

*"Wenn das Portal nach Gebäuden gruppiert, schaut es genau in dieses Feld.
Wenn der Viewer die Layer ordnet, ebenso."*

---

### B2 — Beispiel-Eintrag

```json
{
  "id":            "doc-351-bauernhaus-eggiwil",
  "name":          "Bauernhaus Eggiwil BE — Dokumentation",
  "type":          "document",
  "source":        "report",
  "path":          "/data/PDFs/351_Bauernhaus Eggiwil BE-low.pdf",
  "building":      "351",
  "buildingName":  "Bauernhaus Eggiwil",
  "createdAt":     "2026-05-31T16:17:00.000Z"
}
```

**Das ist die ganze Magie.** Mehr braucht es nicht, damit das PDF im
Portal als Karte erscheint UND im Cesium-Viewer in der Seitenleiste
des Gebäudes 351 auftaucht.

---

### B3 — Trennung zwischen Bestand und Ableitung

Manche Felder sind **manuell** gesetzt (z. B. `building` für ein PDF).
Andere werden **automatisch abgeleitet** durch `backfill_building_phase.py`:

| Manuelles Feld                | Abgeleitetes Feld     |
|-------------------------------|-----------------------|
| `id` `name` `type` `path`     | `building` (aus Gruppenname) |
| `building` (für Docs/Videos)  | `phase` `phaseLabel`  |
| `source`                      | `isGroupMaster`       |
|                               | `buildingName` (aus Lookup-Tabelle) |

*"Die manuellen Felder ändern sich selten. Die abgeleiteten kann man
jederzeit neu erzeugen — das macht die Plattform reproduzierbar."*

---

## C · Die Blender-Pipeline (5 Bites)

### C1 — Was Blender macht

```
Gesamtsmodell_V3.blend  (4,9 GB)
   │
   │   scripts/export_blender_glb.py
   │   (Blender headless, Python-Bibliothek bpy)
   │
   ▼
data/blender/export/
   ├── manifest.json   (Index: was wurde exportiert)
   ├── terrain.glb
   └── buildings/      (eine .glb pro Sammlung)
       ├── 1._Bauphase_851.glb
       ├── 2._Bauphase_851.glb
       └── …
```

Eine **Blender-Sammlung** = ein **GLB-Datei** = ein **3D Tile** im Web.

Das Skript läuft headless:

```bash
blender --background Gesamtsmodell_V3.blend --python scripts/export_blender_glb.py
```

---

### C2 — Vom GLB zum 3D Tile

```
buildings/*.glb
   │
   │   scripts/generate_3dtiles.py
   │   Bibliotheken: pyproj (Koordinaten), gltfpack (LODs)
   │
   ▼
data/cesium/gesamtmodell/
   ├── tileset.json                   (Hauptmodell)
   ├── tileset_2025_851.json          (alle 7 Phasen von 851)
   ├── tileset_2025_851_1._Bauphase_851.json   (einzelne Phase)
   └── buildings/
       ├── 1._Bauphase_851_lod0.glb   (100 %)
       ├── 1._Bauphase_851_lod1.glb   (30 %)
       └── 1._Bauphase_851_lod2.glb   (5 %)
```

Drei LOD-Stufen pro Gebäude — Cesium wählt automatisch nach Distanz:
- nah dran → LOD0 (volle Qualität)
- mittlere Distanz → LOD1 (30 %)
- weit weg → LOD2 (5 %)

---

### C3 — Wie ein Schweizer Gebäude auf den Globus kommt

Das Blender-Modell ist in **LV95-Koordinaten** (Schweizer Landeskoordinaten):

```
Blender lokal (0,0,0)  →  LV95 Origin (2'648'466 / 1'177'343)  →  WGS84/ECEF
```

Drei Korrekturen:

1. **LV95 → WGS84:** durch `pyproj`-Bibliothek
2. **Geoid-Korrektur:** +47,5 m (LHN95 orthometrische Höhe → WGS84-Ellipsoid)
3. **Modell-Yaw:** +2,2° (das Blender-Modell ist gegenüber Nord verdreht)

*Resultat:* CesiumJS platziert das Gebäude **zentimetergenau** auf dem Globus.

---

### C4 — Die Phase wird zum Layer

In Blender:
```
Häuser / Mit_Nummer / 2025_851 / 1. Bauphase 851  ← Sammlung mit Geometrie
```

Nach der Pipeline:
```
data/cesium/gesamtmodell/tileset_2025_851_1._Bauphase_851.json
   ↓
datasets.json:
   id: "gesamtmodell_2025_851_1._Bauphase_851"
   name: "1. Bauphase 851"
   building: "851"   ← automatisch erkannt
   phase: 1          ← automatisch aus dem Namen
```

**Konsequenz im Viewer:** unter "Gebäude 851" erscheint Phase 1 als Checkbox
in der Layer-Gruppe — ohne dass jemand den Frontend-Code angefasst hat.

---

### C5 — Der gefährliche Knackpunkt: die `.blend`-Datei

| Eigenschaft        | Wert                                             |
|--------------------|--------------------------------------------------|
| Größe              | 4,9 GB                                           |
| Inhalt             | ~70 Gebäude + Terrain + Tragwerk in EINER Datei  |
| Bus-Factor         | 1 — wer die Datei verliert, verliert alles       |
| Git-tauglich       | Nein (binär, nicht diff-bar)                     |
| Export-Dauer       | ~ 20 Minuten (volle Auflösung)                   |

**Strategie für die Zukunft** (in `PIPELINE.md` Abschnitt 5):
**eine `.blend`-Datei pro Gebäude** statt einer Monolith-Datei.
Vorteile: kleiner (~ 200 MB), parallel editierbar, in Git-LFS speicherbar.

---

## D · Die LiDAR-Pipeline (4 Bites)

### D1 — Vom Scan zum Web

```
data/laserscans/*.e57   (TLS-Rohscan, mehrere GB)
   │
   │   scripts/process.py
   │   Bibliotheken: pye57 (E57 lesen), laspy (LAS/LAZ),
   │                 numpy (Sampling), PIL (Panoramen)
   │
   ▼
data/cesium/<id>/tileset.json   ← Punktwolke als 3D Tiles
data/panoramas/<id>/             ← Panoramen aus dem Scan extrahiert
   ├── metadata.json   (Scan-Positionen in LV95 + Drehung)
   ├── scan_001.jpg
   └── ...
```

**Ein Skript, eine Zeile:**

```bash
python3 scripts/process.py scan.e57 --building-id 351 --capture-method TLS
```

Auto-Registrierung in `datasets.json`.

---

### D2 — Was eine E57-Datei alles enthält

| Komponente             | Was wir damit machen              |
|------------------------|-----------------------------------|
| 3D-Punkte mit RGB      | Punktwolke (3D Tiles oder Potree) |
| Scan-Positionen        | Klick-Marker in Cesium            |
| HQ-Panoramen           | Equirektangulare JPEGs            |
| Yaw-Werte              | Korrekte Ausrichtung der Panoramen|

Im Cesium-Viewer ergibt das: an jeder Scan-Position ein orangener Marker.
Klick → Panorama öffnet sich als Vollbild-Overlay.

---

### D3 — Punktwolke ODER Modell?

Beide. Im selben Viewer.

```
Haus Eggiwil:
  - Punktwolke (5'023'669 Punkte, LV95) → Realität gescannt
  - 3D-Modell (3 Bauphasen) → Rekonstruktion
```

**Demo-Mehrwert:** Modell-Phase einblenden und gegen die Punktwolke
abgleichen — passt die Hypothese zum gemessenen Bestand?

---

### D4 — Cesium vs. Potree für Punktwolken

| Kriterium              | Cesium (3D Tiles) | Potree            |
|------------------------|-------------------|-------------------|
| Globus-Kontext         | Ja                | Nein              |
| Größte getestete Wolke | ~ 10 M Punkte     | > 1 Mrd. Punkte   |
| Mit Modellen kombinier-| Ja                | Eingeschränkt     |
| LOD-Streaming          | Tile-basiert      | Octree-basiert    |

Heute haben wir **denselben Scan zweimal vorbereitet** — Wahl je nach
Anwendungsfall. Cesium für Kontext-Demos, Potree für Detail-Inspektion.

---

## E · Dokumente, Videos und Co. (3 Bites)

### E1 — Der einfachste Datentyp

Eine PDF zu integrieren:

1. PDF in `data/PDFs/` ablegen
2. **Zwei Zeilen** in `datasets.json` schreiben:
   ```json
   {
     "type":      "document",
     "building":  "351",
     "path":      "/data/PDFs/351_….pdf"
   }
   ```
3. Fertig. Erscheint im Portal **und** als anklickbarer Eintrag in der
   rechten Seitenleiste, wenn Gebäude 351 aktiv ist.

*Keine Code-Änderung. Keine Migration. Keine Verarbeitung.*

---

### E2 — Video: zwei Wege

**A) Eigene Datei**
```json
{ "type": "video", "path": "/data/videos/<name>.mp4", "building": "351" }
```

**B) YouTube-Embed** mit Zeitstempel
```json
{
  "type":      "video",
  "youtubeId": "Yk0Sxdykx9w",
  "start":     95,
  "end":       119,
  "building":  "351"
}
```

Im Cesium-Viewer: kompaktes Picture-in-Picture-Fenster. Die Punktwolke
bleibt im Hintergrund interaktiv.

---

### E3 — Das Muster ist datentyp-agnostisch

Heute funktioniert es für PDF + Video. **Morgen genauso für:**

- Audio-Interviews (`type: "audio"`, HTML5 `<audio>`)
- Historische Karten als georeferenzierte Overlays
- Text-Berichte als Markdown
- Bildergalerien

Jedes Mal: neue `type`-Eintrag im Katalog, ein kleiner Viewer-Komponent,
fertig. **Die Architektur muss nicht angefasst werden.**

---

## F · Die Viewer im Browser (3 Bites)

### F1 — Welcher Viewer für was

| Viewer            | Datei                  | Optimum                       |
|-------------------|------------------------|-------------------------------|
| `cesium.html`     | 4'341 Zeilen           | Alles georef. + Multi-Layer   |
| `potree18.html`   | 968 Zeilen             | Massive Punktwolken (WebGL)   |
| `potreenext.html` | 968 Zeilen             | Punktwolken auf WebGPU        |
| `splat.html`      | 269 Zeilen             | Gaussian Splats               |
| `pdf.html`        | 74 Zeilen              | PDFs einzeln                  |
| `video.html`      | 78 Zeilen              | Videos einzeln                |

Jeder Viewer **steht für sich.** Kein gemeinsames Framework, keine
gegenseitigen Abhängigkeiten — eine HTML-Datei pro Viewer.

---

### F2 — Der Cesium-Viewer im Detail

Das Schwergewicht: 4'341 Zeilen, vereint mehrere Funktionen:

- **3D Tiles** rendern (Modelle UND Punktwolken)
- **Pannellum**-Overlay für Panoramen (Klick auf Scan-Marker)
- **CustomShader** für Tragwerk-Farbgebung
- **Mess-Werkzeuge** (Distanz, Fläche, Profil, Höhe)
- **Clip Boxes** (Schnittebenen)
- **Zeitreise**-Overlay (swisstopo-WMTS, 1864–heute)
- **GCP-Editor** für Helmert-Transformation
- **Dokumente & Medien**-Seitenleiste
- **Layer-Gruppierung** nach Gebäude

*Ein Viewer, der das Schweizer Geodatenstack (LV95, Zeitreise) nativ kennt.*

---

### F3 — Was nicht zur Cesium-Komplexität gehört

Bewusste Trennung:

- **Portal** (`index.html` + `portal.js`, 222 Zeilen) → Übersicht aller Gebäude
- **PDF/Video** (separate `.html`-Dateien) → einfache, fokussierte Viewer
- **Compare** (`compare.html`) → Side-by-Side mit ziehbarem Trenner

Diese kleinen Seiten erfüllen je **einen** Zweck. So bleibt
`cesium.html` für die anspruchsvollen Aufgaben.

---

## G · Koordinatensysteme (2 Bites)

### G1 — Drei Welten, drei Koordinaten

```
Blender lokal  ←──  LV95 (Schweizer Landesvermessung)  ──→  WGS84/ECEF
(0,0,0)            (2'648'466 / 1'177'343 / 570 m)         (auf dem Globus)
```

| Welt           | Wer benutzt es           |
|----------------|--------------------------|
| Blender lokal  | Modellierer*innen        |
| LV95           | swisstopo, Behörden      |
| WGS84/ECEF     | CesiumJS, Browser-Viewer |

Die Pipeline übersetzt **automatisch** zwischen allen drei.

---

### G2 — Helmert-Transformation für freistehende Daten

Wenn ein Datensatz NICHT in LV95 vorliegt (z. B. ein Photogrammetrie-Output),
können Nutzer*innen im Cesium-Viewer Punkte am Modell anklicken und ihnen
LV95-Koordinaten zuweisen.

`scripts/helmert.py` (Horn/Kabsch via SVD) berechnet die optimale
Transformation. Das Modell springt **interaktiv** an die richtige Stelle
auf dem Globus.

---

## H · Der Server (2 Bites)

### H1 — Was Express macht

```
Node.js + Express 4   →  server.js (591 Zeilen)
```

Drei Aufgaben:

| Endpoint                    | Funktion                                       |
|-----------------------------|------------------------------------------------|
| `GET /api/datasets`         | Listet den Katalog                             |
| `GET /api/datasets/:id`     | Liefert einen Eintrag                          |
| `POST /api/datasets`        | Validiert + fügt einen Eintrag hinzu           |
| `GET /data/...`             | Statisches Ausliefern aller Daten              |
| `GET /cesium-proxy/...`     | Lädt CesiumJS vom CDN und patcht es zur Laufzeit |

Keine Datenbank. Keine Anmeldung. **Bewusst minimal.**

---

### H2 — Validierung am Eingang

Beim POST eines neuen Datensatzes prüft der Server:

- Pflichtfelder vorhanden (`id`, `name`, `type`, `path`, `createdAt`)
- `type` in erlaubter Menge
- ISO-Datumsformat korrekt
- Zahlenfelder wirklich Zahlen
- Boolean-Felder wirklich Booleans

*Schema definiert in* `server.js` *Zeile 17–82.*

Das macht den Katalog auf Dauer sauber — auch wenn manuell oder via
externes Tool eingefügt wird.

---

## I · Iteration und Archivierung (3 Bites)

### I1 — Der schnelle Iterations-Loop

Geänderte Phase 1 von Gebäude 752 in 3 Befehlen:

```bash
# 1. Nur Bauphase 1 von 752 exportieren (~1 Minute)
blender ... -- --building 752 --phase 1

# 2. Nur diese Tilesets aktualisieren (--merge mode: andere bleiben)
python3 scripts/generate_3dtiles.py

# 3. Abgeleitete Felder neu setzen
python3 scripts/backfill_building_phase.py
```

Die `--building` / `--phase`-Flags beschleunigen Iterationen von
20 Minuten auf eine Minute.

---

### I2 — Was passieren WÜRDE bei Datenverlust

Was in Git steht (wird wiederhergestellt):
- Alle Skripte
- `server.js`, Viewer-Code, CSS
- `datasets.json` (Konfiguration)
- Tileset-Index-Dateien (`tileset.json` der Hauptansicht)

Was NICHT in Git steht (braucht Backup):
- `Gesamtsmodell_V3.blend` (4,9 GB)
- Alle GLB-Dateien (`data/blender/export/`, ~ 6,4 GB)
- Tileset-Inhalte (`data/cesium/`, ~ 17 GB)
- Rohscans / Panoramen / Videos

**Strategie:** externes Backup von `data/` (per `DATA_DIR`-Mount oder
periodische Synchronisation). Quellcode + Konfiguration sind in Git
abgesichert.

---

### I3 — Vorschlag für Langzeit-Archivierung

In `PIPELINE.md` Abschnitt 5.5 ausführlich beschrieben:

```
archive/
├── raw/                ← unveränderlich (TLS-Scans, PDFs, Videos)
├── source-models/      ← pro Gebäude ein eigenes .blend (statt Monolith)
└── processed/          ← regenerierbar aus raw + scripts
```

Ein **Archiv-Snapshot** = drei Artefakte:
1. `archive/raw/` + `archive/source-models/` (Eingaben)
2. Git-Commit der Plattform
3. Generierte `datasets.json`

Damit ist die Demo jederzeit von Grund auf reproduzierbar.

---

## P · Pipeline-Schritte konkret (für die Demo-Folien)

Die folgenden Abschnitte sind als **eine Folie pro Pipeline** gedacht. Jede
Pipeline = nummerierte Schritte mit Bibliothek/Tool und Eingabe → Ausgabe.

### P1 — Blender-Pipeline (UC1 · UC2 · UC3)

Vom 3D-Modell in Blender zum interaktiven Layer im Browser.

| #  | Was passiert                                  | Tool / Bibliothek         | Eingabe → Ausgabe                                  |
|----|-----------------------------------------------|---------------------------|----------------------------------------------------|
| 1  | Modellierer\*in baut Sammlung in Blender      | Blender (GUI)             | – → Sammlung `1. Bauphase 851`                     |
| 2  | Headless-Export starten                       | Blender CLI               | `.blend` → Aufruf von `export_blender_glb.py`      |
| 3  | Pro Sammlung eine GLB schreiben               | `bpy.ops.export_scene.gltf` | Sammlung → `buildings/1._Bauphase_851.glb`        |
| 4  | Manifest mit Hierarchie + Bbox schreiben      | reines Python             | alle GLBs → `manifest.json`                        |
| 5  | LV95 → WGS84 → ECEF Transformation berechnen  | `pyproj`                  | LV95-Origin → 4×4-Matrix                           |
| 6  | LOD-Stufen pro GLB erzeugen (100 / 30 / 5 %)  | `gltfpack` (CLI)          | `*.glb` → `*_lod0.glb` `*_lod1.glb` `*_lod2.glb`   |
| 7  | Tileset-JSON schreiben (Master + pro Phase)   | reines Python             | manifest + LODs → `tileset_*.json`                 |
| 8  | Einträge in den Katalog registrieren          | reines Python             | Pfade → Einträge in `datasets.json`                |
| 9  | Abgeleitete Felder setzen (building, phase, …) | reines Python             | `datasets.json` → angereicherter Katalog           |
| 10 | Statisches Ausliefern via Express             | Node.js + Express         | Dateisystem → HTTP                                 |
| 11 | Im Browser laden, Layer im Panel              | CesiumJS 1.140            | `tileset.json` → 3D-Szene                          |

**Auf einer Folie:**
```
Blender-Sammlung
    → GLB     (export_blender_glb.py · bpy)
    → LOD-GLB (gltfpack)
    → 3D Tile (generate_3dtiles.py · pyproj)
    → Katalog (backfill_building_phase.py)
    → Browser (CesiumJS 1.140)
```

**Kommando-Sequenz** (für die Folie "wie iteriert man"):
```bash
blender --background <file> --python scripts/export_blender_glb.py -- --building 752 --phase 1
python3 scripts/generate_3dtiles.py
python3 scripts/backfill_building_phase.py
```

---

### P2 — LiDAR-Pipeline (UC4 Punktwolke Haus Eggiwil)

Vom terrestrischen Laserscan zum verlinkten Panorama im Browser.

| #  | Was passiert                                       | Tool / Bibliothek       | Eingabe → Ausgabe                                |
|----|----------------------------------------------------|-------------------------|--------------------------------------------------|
| 1  | TLS-Scan im Feld erstellen                         | Scanner (Leica / Faro)  | Realität → `.e57`-Datei                          |
| 2  | Plattform-Skript mit Metadaten aufrufen            | `process.py` (CLI)      | `scan.e57` + Flags → Verarbeitung startet        |
| 3  | E57 entpacken: Punkte, Positionen, Panoramen       | `pye57`                 | `.e57` → numpy-Arrays + JPEGs                    |
| 4  | Punkte downsamplen (Poisson / uniform / voxel)     | `numpy`                 | 5 M Punkte → mehrere LOD-Stufen                  |
| 5  | LOD-Stufen erzeugen (100 / 20 / 5 %)               | `numpy`                 | Voll → reduziert                                 |
| 6  | Als 3D Tiles serialisieren                         | reines Python           | Punkte + Farben → `tileset.json` + `*.pnts`      |
| 7  | Panoramen als equirektangulare JPEGs schreiben     | `PIL`                   | E57-Panoramen → `panoramas/<id>/*.jpg`           |
| 8  | Scan-Positionen mit LV95 + Yaw speichern           | reines Python           | E57-Metadaten → `panoramas/<id>/metadata.json`   |
| 9  | Eintrag in Katalog (mit `panoramasPath`)           | reines Python           | → `datasets.json`                                |
| 10 | Statisches Ausliefern via Express                  | Node.js + Express       | Dateisystem → HTTP                               |
| 11 | Im Browser: Punktwolke + Scan-Marker rendern       | CesiumJS                | tileset + Positionen → 3D-Szene + Klick-Marker   |
| 12 | Klick auf Marker → Panorama als Overlay            | Pannellum 2.5.6         | JPEG → vollbild-interaktives Panorama            |

**Auf einer Folie:**
```
.e57 (Scan)
    → Punkte    (pye57, numpy)        → 3D Tiles    → Cesium
    → Panoramen (PIL)                 → JPEG-Folder → Pannellum-Overlay
    → Positionen                      → metadata.json → Klick-Marker
```

**Ein Kommando, alles:**
```bash
python3 scripts/process.py data/laserscans/haus-eggiwil.e57 \
        --building-id 351 --capture-method TLS --has-color
```

---

### P3 — Dokumente und Videos (UC4 PDF + Drohnenflug)

Der kürzeste Weg ins System. **Keine Verarbeitung — nur Katalogeintrag.**

| #  | Was passiert                                   | Tool / Bibliothek    | Eingabe → Ausgabe                              |
|----|------------------------------------------------|----------------------|------------------------------------------------|
| 1  | PDF in Ordner `data/PDFs/` ablegen             | manuell              | Datei → Pfad                                   |
| 2  | Eintrag in `datasets.json` schreiben (Hand)    | manuell              | `{type, building, path}` → Katalog             |
| 3  | Express liefert PDF statisch aus               | Node.js + Express    | Datei → HTTP                                   |
| 4  | Portal zeigt PDF unter Haus-Karte              | `portal.js`          | Katalog → Karten-UI                            |
| 5  | Cesium-Seitenleiste zeigt PDF wenn Geb. aktiv  | `cesium.html`        | `building`-Feld → kontextuelle Liste           |
| 6  | Klick → Slide-out mit Browser-PDF-Viewer       | iframe               | Datei-URL → eingebettete Ansicht               |

**Video-Variante (YouTube):**

| #  | Was passiert                                  | Tool / Bibliothek | Eingabe → Ausgabe                       |
|----|-----------------------------------------------|-------------------|-----------------------------------------|
| 1  | Video-Quelle bestimmen (URL, Zeitstempel)     | manuell           | YouTube-ID + Start / End in Sekunden    |
| 2  | Eintrag in `datasets.json` mit `youtubeId`    | manuell           | → Katalog                               |
| 3  | Cesium-Seitenleiste zeigt Video kontextuell   | `cesium.html`     | Katalog → Liste                         |
| 4  | Klick → Picture-in-Picture-iframe             | YouTube-Embed     | Embed-URL → PIP-Fenster                 |

**Auf einer Folie:**
> *"PDF integrieren = Datei ablegen + zwei Zeilen JSON. Keine Skript-Ausführung.
> Genauso für Audio, historische Karten, oder Text-Berichte: derselbe
> Mechanismus, andere Endung."*

---

### P4 — Was im Browser passiert, wenn ein Haus geöffnet wird

Konkrete Abfolge, wenn ein\*e Nutzer\*in im Portal "351 — Bauernhaus
Eggiwil" → "Im 3D-Viewer öffnen" klickt:

| #  | Was passiert                                                     | Wer macht's              |
|----|------------------------------------------------------------------|--------------------------|
| 1  | Browser springt nach `cesium.html?building=351`                  | Portal-Link              |
| 2  | URL-Parameter `building=351` wird gelesen                        | `cesium.html` Init       |
| 3  | Katalog wird geladen (`GET /api/datasets`)                       | Express → `datasets.json`|
| 4  | Datensätze mit `building === "351"` werden ausgewählt            | `cesium.html`            |
| 5  | Punktwolke (LiDAR) wird als Layer hinzugefügt — **sichtbar**     | CesiumJS                 |
| 6  | 3 Modell-Tilesets werden als Layer hinzugefügt — **unsichtbar**  | CesiumJS                 |
| 7  | Kamera fliegt zur sichtbaren Punktwolke                          | CesiumJS                 |
| 8  | Rechte Seitenleiste filtert PDF + Video für Geb. 351             | `cesium.html`            |
| 9  | Layer-Panel gruppiert die 4 Tilesets unter "351 — Bauernhaus…"   | `cesium.html`            |
| 10 | Scan-Positionen erscheinen als orangene Klick-Marker             | Pannellum-Integration    |

**Botschaft auf der Folie:**
> *"Ein Klick → 4 Layer geladen, 2 Medien verlinkt, Kamera positioniert.
> Die ganze Logik liest aus `building: \"351\"` in `datasets.json`."*

---

## Empfehlungen zur Slide-Auswahl

**Wenn du nur 5 Minuten für Pipeline hast:** A1, A2, B1, C1, F1.

**Wenn du 10 Minuten Pipeline machen willst:** + B2, C2, D1, E1, I1.

**Bei tieferen technischen Rückfragen ziehbar:** C3 (Koordinaten), C5
(Blender-Problem), D4 (Cesium vs. Potree), G1/G2 (Koordinatenwelten).

**Vermeiden in der ersten Sitzung:** H1, H2, F3 (Server-Details — zu
technisch für den Überblick, eher für eine Folgepräsentation).
