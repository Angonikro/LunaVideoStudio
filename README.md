# LunaVideoStudio 1.3.85

LunaVideoStudio ist eine GTK4-Anwendung für Debian/Linux zum Analysieren und Umwandeln von DVD- und Blu-ray-Titeln in MP3 MKV AVI. Die Videoverarbeitung erfolgt mit FFmpeg.

## Funktionen

- DVD- und Blu-ray-Medien sowie Titel analysieren
- Erkannte Audio- und Untertitelspuren anzeigen und auswählen
- Ausgabeformate MP4, MKV und AVI
- Qualitätsprofile und optionale Audio-Lautheitsnormalisierung (−16 LUFS)
- 1-Minuten-Testclip aus der Filmmitte erstellen
- Bei DVD-MP4-Ausgabe ausgewählte Untertitel über FFmpeg ins Bild einbrennen, sofern die Disc-/FFmpeg-Metadaten die Zuordnung eindeutig ermöglichen
- Blu-ray-PGS-Untertitel bei MP4-/AVI-Ausgabe ins Bild einbrennen; bei MKV als separate Spur übernehmen
- Laufzeit- und Fortschrittsanzeige
- Rippen abbrechen
- Laufwerk manuell auswerfen oder optional nach erfolgreichem Rip/Test automatisch auswerfen
- Deutsche und englische Benutzeroberfläche

## Installation: Debian-Paket

```bash
sudo apt install ./luna-video-studio_1.3.85_all.deb
```

Start über das Anwendungsmenü oder mit:

```bash
luna-video-studio
```

## ZIP-/GitHub-Version starten

Archiv entpacken und im Projektordner die benötigten Pakete installieren:

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-4.0 ffmpeg mediainfo lsdvd eject libbluray2 libaacs0 libbdplus0 libdvdnav4 libdvdread8t64
```

Anwendung starten:

```bash
python3 src/luna_video_studio/main.py
```

Alternativ den Starter verwenden:

```bash
chmod +x packaging/luna-video-studio
./packaging/luna-video-studio
```

## Hinweise zum DVD-Minuten-Test

Der DVD-Minuten-Test verwendet denselben FFmpeg-basierten Lese-, Audio- und Untertitelpfad wie der vollständige DVD-Rip. Der Test erstellt einen etwa 60 Sekunden langen Ausschnitt aus der Filmmitte. Bei MP4 und ausgewählten DVD-Untertiteln ermittelt FFprobe die verfügbaren Untertitelstreams und deren Sprachmetadaten. Kann die gewünschte Spur nicht eindeutig zugeordnet werden, kann der Vorgang mit einer Fehlermeldung abbrechen, statt stillschweigend eine andere Sprache einzubrennen.

## Optionale Werkzeuge

Für zusätzliche MKV-Werkzeuge kann `mkvtoolnix` installiert werden. Für OCR von Blu-ray-PGS-Bilduntertiteln kann optional `pgsrip` mit RapidOCR in einer isolierten pipx-Umgebung installiert werden:

```bash
sudo apt install mkvtoolnix pipx
pipx install "pgsrip[rapidocr]"
```

## Konfiguration

Die Benutzereinstellungen werden unter `~/.config/luna-video-studio/settings.json` gespeichert.

## Projektdateien

- `src/luna_video_studio/main.py` – Anwendung
- `packaging/` – Debian-Metadaten, Starter und Desktop-Datei
- `CHANGELOG.md` – Versionsänderungen
