# LunaVideoStudio 1.3.80

GTK4-Anwendung für Debian/Linux zum Analysieren und Umwandeln von DVD- und Blu-ray-Titeln. Die Videoverarbeitung erfolgt mit FFmpeg.

## Funktionen

- Laufzeitanzeige während des Rippens und Anzeige der Gesamtdauer nach Abschluss (auch bei Abbruch/Fehler).

- DVD-Zwischendateien für den MPlayer-Test werden unter `~/.cache/luna-video-studio/dvdtest/` statt in `/tmp` abgelegt.

- „Rippen starten“ und „1-Minuten-Test“ bleiben beide vorhanden. „Rippen starten“ verwendet für vollständige DVDs FFmpeg mit dem dvdvideo-Demuxer und dem ausgewählten DVD-Titel. Der MPlayer-Zwischenschritt bleibt dem 1-Minuten-Test vorbehalten.

- Optische Laufwerke erkennen und DVD-/Blu-ray-Medien einlesen
- DVD-/Blu-ray-Titel sowie Audio- und Untertitelspuren anzeigen, soweit die Disc und installierten Werkzeuge diese Informationen bereitstellen
- Ausgabeformate MP4, MKV und AVI auswählen
- Qualitätsprofile für die Videoencodierung
- 1-Minuten-Testclip aus der Filmmitte erstellen
- DVD-Testclip mit MPlayer-Navigation; ausgewählte DVD-Untertitel werden in das Bild eingebrannt
- Bei Blu-ray und ausgewähltem PGS-Untertitel: Bei MP4- und AVI-Ausgabe werden die Untertitel mit FFmpeg ins Videobild eingebrannt; bei MKV bleiben sie als separate auswählbare PGS-Spur erhalten.
- Disc per Schaltfläche manuell auswerfen
- Option zum automatischen Auswerfen nach erfolgreichem Rippen oder erfolgreichem 1-Minuten-Test direkt im Bereich „Quelle auswählen“
- **Neu in 1.3.36:** Schaltfläche „Rippen abbrechen“ zum Beenden des laufenden FFmpeg-/MPlayer-Prozesses

## Automatisches Auswerfen

Im Bereich **„Quelle auswählen“** befindet sich die Checkbox **„Disc nach erfolgreichem Rippen automatisch auswerfen“**.

- Standardmäßig ist die Option ausgeschaltet.
- Wenn aktiviert, wird das optische Laufwerk nach einem erfolgreich abgeschlossenen vollständigen Rippen zum Auswerfen angewiesen.
- Bei einem fehlgeschlagenen oder abgebrochenen Vorgang bleibt die Disc eingelegt.
- Wenn die Option aktiviert ist, wird die Disc auch nach einem erfolgreich erstellten 1-Minuten-Testclip ausgeworfen.
- Wenn ein VIDEO_TS-/BDMV-Ordner statt eines optischen Laufwerks als Quelle gewählt wurde, wird keine Disc ausgeworfen.
- Zum Auswerfen wird das Systemprogramm `eject` benötigt.

## Languages / Sprachen

The interface supports German and English. Choose **Deutsch** or **English** in the language selector in the header; the selection is saved in `~/.config/luna-video-studio/settings.json`.

Die Oberfläche unterstützt Deutsch und Englisch. Die Sprache lässt sich oben im Fenster auswählen und wird in `~/.config/luna-video-studio/settings.json` gespeichert.

## Installation: Debian-Paket

```

Installiere LunaVideoStudio:

```bash
sudo apt install ./LunaVideoStudio_1.3.80_all.deb
```

Starte die Anwendung über das Anwendungsmenü oder mit:

```bash
luna-video-studio
```

## ZIP-/GitHub-Version starten

Entpacke `LunaVideoStudio_1.3.80_GitHub.zip`. Im Archiv liegt der Projektordner `LunaVideoStudio`. Öffne ein Terminal in diesem Ordner und installiere die Abhängigkeiten:

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-4.0 ffmpeg mplayer mediainfo lsdvd eject mkvtoolnix pipx libbluray2 libaacs0 libbdplus0 libdvdnav4 libdvdread8t64
```

Starte die Anwendung aus dem Projektordner:

```bash
python3 src/luna_video_studio/main.py
```

Optional kann der mitgelieferte Starter verwendet werden:

```bash
chmod +x packaging/luna-video-studio
./packaging/luna-video-studio
```
## Abhängigkeiten und optionale Untertitelwerkzeuge

### Systempakete

Für die Anwendung, DVD-/Blu-ray-Analyse und das Encoding werden die folgenden Pakete benötigt:


`mkvtoolnix` stellt unter anderem `mkvmerge` bereit und wird für MKV-Werkzeuge benötigt.

### Blu-ray-PGS-Untertitel mit OCR

Für das Auslesen/OCR von Blu-ray-PGS-Bilduntertiteln kann zusätzlich `pgsrip` mit RapidOCR in einer isolierten pipx-Umgebung installiert werden:

```bash
pipx install "pgsrip[rapidocr]"
```

Falls `pipx` nach der Installation meldet, dass die ausführbaren Programme nicht im Suchpfad liegen, führe aus:

```bash
pipx ensurepath
```

Danach gegebenenfalls ab- und wieder anmelden. `pgsrip` ist ein zusätzliches Werkzeug für die Untertitelverarbeitung; die normale FFmpeg-Verarbeitung und das Einbrennen ausgewählter PGS-Spuren bei MP4/AVI benötigen weiterhin FFmpeg.

## Blu-ray-Untertitel in MP4

Blu-ray-Untertitel sind häufig PGS-Bildspuren. MP4 kann diese nicht als normale auswählbare Textspur übernehmen. Bei ausgewählter Blu-ray-PGS-Untertitelspur werden die Untertitel bei MP4- und AVI-Ausgabe mit FFmpeg ins Videobild eingebrannt. Sie sind anschließend dauerhaft sichtbar und lassen sich im fertigen Video nicht ausschalten. Bei MKV bleiben PGS-Untertitel als separate Spur erhalten. Das gewählte Ausgabeformat wird auch beim 1-Minuten-Test verwendet. Ohne ausgewählte Untertitel wird kein Untertitel eingebrannt.

## 1-Minuten-Test

1. DVD oder Blu-ray einlegen und im Bereich „Quelle auswählen“ auf **Disc einlesen** klicken.
2. Gewünschte Ton- und Untertitelspur auswählen.
3. Ausgabeordner und Zielformat wählen.
4. Auf **1-Minuten-Test** klicken.
5. Die erzeugte Datei mit dem Suffix `_TEST_1_MINUTE.mp4` prüfen.

Wenn die automatische Auswurffunktion aktiviert ist, wird die Disc auch nach einem erfolgreich erstellten 1-Minuten-Testclip ausgeworfen. Bei einem Abbruch wird sie nicht ausgeworfen.

## Hinweise zur Fehlersuche

- Prüfe, ob im Untertitel-Dropdown tatsächlich eine Sprache und nicht „Aus – keine Untertitel“ ausgewählt ist.
- Bei Fehlern notiere den letzten Fehlertext aus dem Statusbereich.
- Verschlüsselte Discs können eine passende, rechtmäßig verfügbare AACS-Konfiguration voraussetzen.
- Die Anwendung wurde in dieser Arbeitsumgebung nicht an einem physischen DVD-/Blu-ray-Laufwerk getestet. Bitte die neue Auswurffunktion zunächst mit einer entbehrlichen Disc testen.

## Projektstruktur

- `src/luna_video_studio/main.py` – Anwendung
- `packaging/` – Debian-Paket-Metadaten, Starter und Desktop-Datei
- `CHANGELOG.md` – Versionsänderungen


## Hintergrund: DVD-Titelauswahl

Der vollständige DVD-Rip verwendet FFmpeg mit dem dvdvideo-Demuxer und dem ausgewählten DVD-Titel. Der 1-Minuten-Test verwendet weiterhin MPlayer für DVD-Navigation und Untertitelauswahl und FFmpeg für die Erstellung des Testclips. Für Blu-ray verwenden beide Aktionen dieselbe ausgewählte MPLS-Playlist und denselben FFmpeg-Streamindex.

## Änderungen in 1.3.74

- Sichtbare Sprachauswahl „Deutsch / English“ oben rechts ergänzt. Die Auswahl wird gespeichert. Beim Sprachwechsel bleiben die tatsächlich erkannten Audio- und Untertitelspuren erhalten.
- DVD-Analyse behandelt ungültige/nicht-UTF-8-Bytes in Werkzeugausgaben tolerant, statt beim Einlesen mit `UnicodeDecodeError` abzubrechen. Das betrifft besonders DVD-Namen und Metadaten; andere DVDs behalten den bisherigen Analysepfad.
- Die Anwendung bietet die Option "Audio automatisch normalisieren (−16 LUFS)". Sie ist standardmäßig aktiviert und verwendet FFmpeg `loudnorm` mit einem Zielwert von −16 LUFS und True Peak −1,5 dB. Die Einstellung kann vor dem Rippen deaktiviert werden. Minutentest und normaler Rip verwenden dieselbe Einstellung; auch der DVD-MPlayer-Zwischenschritt berücksichtigt sie.
## Version 1.3.36

- Fortschrittsanzeige aktualisiert sich während des FFmpeg-Encoding anhand der verarbeiteten Laufzeit.
- FFmpeg-Statusausgabe wird separat gelesen, damit die Anwendung während des Encodings nicht auf das Ende warten muss.
- DVD-Titel werden weiterhin über den ausgewählten `dvdvideo`-Titelparameter verarbeitet; bitte nach dem Update kontrollieren, dass nur der gewünschte Haupttitel ausgegeben wird.


## Titelauswahl (1.3.36)
Nach dem Einlesen wird zunächst der längste erkannte Titel vorgeschlagen. Du kannst in der Titelliste den gewünschten Film anklicken. Nur der ausgewählte Titel wird für den vollständigen Rip und den 1-Minuten-Test verwendet; Ton- und Untertitelspuren werden passend zum Titel angezeigt.


### Blu-ray-Untertitel in 1.3.59

Die Zuordnung von Blu-ray-Sprachmetadaten erfolgt über die Stream-PID, und die ausgewählte PGS-Spur wird im FFmpeg-Filter über ihren globalen Streamindex angesprochen. Bitte den Ein-Minuten-Test mit der eigenen Disc durchführen; eine erfolgreiche Hardware-/Disc-Prüfung ist nicht Bestandteil des Quellpakets.

- Version 1.3.56: DVD-Minuten-Test verifiziert die ausgewählte Untertitelsprache über MPlayers eigene SID-/Sprach-Erkennung; wenn die Sprache nicht eindeutig bestätigt werden kann, wird der Test abgebrochen statt eine falsche Sprache einzubrennen.


## Änderungen in 1.3.79

- Vollständiger DVD-Rip wieder auf den FFmpeg-`dvdvideo`-Pfad mit expliziter Auswahl des erkannten DVD-Titels umgestellt. Der MPlayer-Rohvideo-Zwischenschritt wird nur noch für den 1-Minuten-Test verwendet, da er bei vollständigen DVD-Rips offenbar nur einen Teil des Films lieferte.
- Der Blu-ray-Pfad und die Auswahl des Blu-ray-Streams wurden nicht gezielt verändert.
- README mit dem neuen Versionsstand und der getrennten DVD-Verarbeitung aktualisiert.
