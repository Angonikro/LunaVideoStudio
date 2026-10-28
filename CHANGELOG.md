# Changelog

## 1.3.80
- Vollständige DVD-Rips werden anhand der von lsdvd erkannten Titellaufzeit geprüft. Eine deutlich zu kurze Datei (unter 90 % der erwarteten Laufzeit) wird nicht mehr als „Fertig“ gemeldet; die Statusmeldung nennt erkannte und tatsächliche Laufzeit. Der zugrunde liegende Leseabbruch wird damit sichtbar, nicht automatisch repariert.

## 1.3.79
- Fixed full DVD rip audio mapping: DVD stream IDs (e.g. 0x80/0x81) are not FFmpeg global stream indexes. The selected DVD audio track is now mapped by its audio-stream position, preventing the wrong language from being encoded.

## 1.3.78
- Vollständige DVD-Rips nutzen wieder FFmpeg `dvdvideo` mit explizitem DVD-Titel; MPlayer-Rohvideo-Zwischenschritt bleibt für den 1-Minuten-Test.
- README aktualisiert. Blu-ray-Verarbeitung nicht gezielt geändert.

# LunaVideoStudio 1.3.77

- Version 1.3.77: Laufzeit-Label wird auch beim initialen Aufbau und beim Start eines Rips anhand der gewählten Sprache gesetzt. README bleibt unverändert.

## 1.3.74
- Fixed remaining German elapsed-time and total-duration labels when English is selected.
- Translated the abort-request and final progress labels according to the selected language.

## 1.3.73
- Fixed missing German/English language selector: it is now visible in the header.
- Preserved dynamically detected audio and subtitle tracks when changing language.

## 1.3.72
- Added German/English language selector in the header; preference is saved in the user config directory.
- Translated primary interface labels, controls, panels and common status text.

## 1.3.71
- Optionale Audio-Lautheitsnormalisierung mit FFmpeg `loudnorm` (Ziel −16 LUFS, True Peak −1,5 dB); standardmäßig aktiviert und abschaltbar. Für DVD, Blu-ray, Minutentest und normalen Rip vorgesehen.

## 1.3.70
- DVD-Einlesen: Textausgaben externer Werkzeuge werden mit fehlertoleranter Zeichendekodierung gelesen. Eine DVD mit nicht-UTF-8-Metadaten bricht dadurch nicht mehr die gesamte Analyse ab. Bestehende SID-/Spurzuordnung und Blu-ray-Pfad bleiben unverändert.

## 1.3.69
- DVD-Untertitel: Wiederherstellung des bewährten 1.3.54-Fallbacks. Wenn die von lsdvd gelieferte SID nicht mit MPlayers Sprachkennung übereinstimmt, wird die erste SID mit exakt passender Sprache aus MPlayers eigener Liste verwendet. Falls keine passende Sprache gefunden wird, wird sicher abgebrochen. Blu-ray-Pfad unverändert.

## 1.3.68
- Correct DVD subtitle mapping from SPU stream IDs to MPlayer SIDs; avoid unsafe guesses when duplicate-language tracks exist.
- Leave Blu-ray subtitle handling unchanged.

## 1.3.67
- Behält bei DVD-Titeln die XML-Spurzuordnung von lsdvd (<ix>) bei. Die menschenlesbare Ausgabe mit MPEG-SPU-IDs wie 0x22 darf die MPlayer-SID nicht mehr überschreiben.

## 1.3.66
- DVD-Untertitel: Wenn die von lsdvd abgeleitete SID in MPlayer fehlt oder eine andere Sprache meldet, wird die Spur anhand von MPlayers eigener SID-Sprachliste aufgelöst. Automatische Zuordnung nur bei genau einem Treffer; bei mehreren Treffern wird sicher abgebrochen.

## 1.3.65
- Korrigiert die DVD-Untertitel-SID-Zuordnung anhand der DVD-SPU-Stream-ID (0x20–0x3F), statt die lsdvd-Zählnummer ungeprüft als MPlayer-SID zu verwenden.

## 1.3.64
- Abschlussmeldung des normalen Rips an FFmpeg-Endstatus und anschließende FFprobe-Prüfung gekoppelt.
- Bei erfolgreichem FFmpeg-Ende wird die Ausgabe auf lesbaren Videostream und plausible Laufzeit geprüft, bevor „Fertig“ angezeigt wird.
- Fehlerpfad korrigiert: Validierung verwendet den Worker-Modus statt einer nicht definierten Testclip-Variablen.

# Changelog

## 1.3.64
- Abbruch stoppt den sichtbaren Laufzeittimer sofort.
- Medienprozesse starten in einer eigenen Prozessgruppe; Abbruch beendet auch Hilfsprozesse, die sonst Pipes offen halten könnten.
- Abbruch verwendet SIGTERM mit SIGKILL-Fallback nach Zeitlimit, damit Oberfläche und Timer nicht endlos auf einen hängen gebliebenen Prozess warten.


## Version 1.3.62
- Manuelles Auswerfen läuft in einem Hintergrund-Thread; die GTK-Oberfläche bleibt während des Systemaufrufs bedienbar.
- Ergebnis und Fehler des Auswerfens werden sicher über die GTK-Hauptschleife angezeigt.
- Automatisches Auswerfen nach dem Rippen bleibt im bereits separaten Rip-Worker.


## Version 1.3.61
- Fehlerbehandlung nach FFmpeg verbessert: Bei einem Fehler-Rückgabecode wird die Ausgabe mit FFprobe geprüft. Nur eine Datei mit lesbarem Videostream und plausibler Laufzeit kann als fertig gemeldet werden; echte oder unprüfbare Ausgaben bleiben Fehler.
- Blu-ray-Playlist-/Untertitelauswahl und DVD-Spurwahl nicht verändert.

## Version 1.3.61
- DVD-Minuten-Test und DVD-Komplettrip verwenden ausdrücklich dieselbe MPlayer-basierte DVD-Lese- und Untertitelauswahl-Pipeline; nur der Test ist auf 60 Sekunden begrenzt.
- DVD-Untertitel werden nicht mehr stillschweigend durch eine andere Spur derselben Sprache ersetzt. Die ausgewählte SID muss von MPlayer mit der erwarteten Sprache bestätigt werden; andernfalls wird sicher abgebrochen.
- Blu-ray-Playlist-/Streamauswahl aus 1.3.59 beibehalten; Minuten-Test und Komplettrip verwenden dieselbe gewählte Playlist und denselben ausgewählten Untertitelstream.
- Programmversion, README und Debian-Paketversion auf 1.3.61 vereinheitlicht.

## Version 1.3.59
- Blu-ray-Sprachmetadaten werden über die tatsächliche Transport-Stream-PID mit FFprobe-Spuren verknüpft, statt sich auf die Listenposition zu verlassen.
- Beim Einbrennen und Zuordnen von Blu-ray-PGS-Untertiteln wird der globale FFmpeg-Streamindex verwendet.
- Weiterhin gilt: Ein echter Blu-ray-Minuten-Test muss auf dem Zielsystem bestätigen, dass die gewählte Sprache korrekt eingebrannt wird.

## 1.3.58
- Fix Blu-ray language lookup to match the selected MPLS playlist instead of the disc main title.
- Keep FFmpeg/MediaInfo language metadata preferred when available.

## 1.3.56
- Blu-ray: show playlist candidates and restore language metadata fallback from MediaInfo/libbluray when available.
- DVD path retained from 1.3.54.

# Changelog

## 1.3.54
- DVD-Minuten-Test prüft die Untertitel-Sprachkennung anhand von MPlayers eigener SID-/Sprach-Erkennung.
- Wenn die ausgewählte Sprache nicht eindeutig bestätigt werden kann, wird der Test mit einer verständlichen Fehlermeldung abgebrochen, statt stillschweigend falsche Untertitel einzubrennen.
- App- und Paketversion auf 1.3.54 angeglichen.

## 1.3.53
- Korrigiert die DVD-Untertitelauswahl im MPlayer-Minuten-Test: Die ausgewählte lsdvd-Spurnummer wird explizit als MPlayer-`-sid` verwendet; die separate DVD-SPU-Stream-ID wird nicht mehr als Auswahlindex fehlinterpretiert.
- App- und Paketversion auf 1.3.53 angeglichen.

## 1.3.51
- Laufzeit-Timer ergänzt: zeigt die verstrichene Zeit während des Rippens und die Gesamtdauer nach Abschluss, Abbruch oder Fehler.

# Changelog

## 1.3.50
- README ergänzt: fehlende Systemabhängigkeiten `mkvtoolnix` und `pipx`.
- Dokumentiert die optionale Installation von `pgsrip[rapidocr]` für Blu-ray-PGS-Untertitel-OCR.
- Veraltete Download-Dateinamen in der README korrigiert.

# Changelog

## 1.3.49
- DVD-Zwischendateien werden im Benutzer-Cache unter `~/.cache/luna-video-studio/dvdtest/` gespeichert statt unter `/tmp`.

## 1.3.48
- Animate the progress bar while MPlayer reads DVD data into temporary streams.
- Show FFmpeg's real time-based progress during the subsequent DVD encoding stage.
- Keep the existing DVD extraction/encoding pipeline and one-minute test behavior unchanged.

# Changelog

## 1.3.47
- Repariertes GitHub-ZIP-Paket; Inhalt basiert auf dem geprüften Quellarchiv 1.3.46.


## 1.3.46
- After disc analysis, suggest `~/Videos/<disc name>` as the output folder when a disc/volume label or folder name can be detected. A user-selected custom destination is preserved.
- Existing ripping pipeline and progress handling left unchanged in this release.


## 1.3.45
- Stellt den Rip-Verarbeitungspfad aus 1.3.43 wieder her, der in 1.3.44 geändert worden war.
- Korrigiert ausschließlich den Status: „DVD-Testclip“ erscheint nur beim echten 1-Minuten-DVD-Test. Beim vollständigen DVD-Rip wird der vollständige Rip angezeigt.
- Fortschrittsanzeige und separater 1-Minuten-Test bleiben aus 1.3.43 unverändert erhalten.

## 1.3.43
- Fortschrittsanzeige robuster gemacht: FFmpeg-Fortschritt wird regelmäßig abgefragt und sowohl aus `out_time` als auch aus den Zeitfeldern älterer FFmpeg-Versionen gelesen.
- Fortschritt wird während der Verarbeitung aktualisiert und nicht erst nach dem Ende auf 100 % gesetzt.
- Fortschrittsintervall auf 0,5 Sekunden gesetzt.

## 1.3.43
- Versionsanzeige in der App an die Paketversion angeglichen.
- README-Download- und Installationsbeispiele auf 1.3.43 aktualisiert.

## 1.3.40
- „Rippen starten“ nutzt denselben Verarbeitungsweg wie „1-Minuten-Test“, ohne 60-Sekunden-Limit oder Startposition in der Filmmitte.
- Der separate Button „1-Minuten-Test“ bleibt erhalten.

## 1.3.36
- Die Titelliste ist auswählbar. Vorbelegung ist der längste erkannte Titel; der Benutzer kann vor dem Rippen einen anderen Titel anklicken.
- Ton- und Untertitel-Auswahl werden passend zum ausgewählten Titel aktualisiert.
- Vollständiges Rippen und Fortschrittsberechnung verwenden denselben ausgewählten Titel statt immer den ersten Listeneintrag.

## 1.3.34
- Korrigiert die FFmpeg-Optionierung für vollständige DVD-Rips durch explizite Auswahl des `dvdvideo`-Demuxers.
- Der vorhandene DVD-1-Minuten-Testpfad bleibt unverändert.


## 1.3.33
- Automatisches Auswerfen gilt bei aktivierter Option auch nach erfolgreichem 1-Minuten-Test.
- Neue Schaltfläche „Rippen abbrechen“ beendet den aktiven FFmpeg-/MPlayer-Prozess. Abgebrochene Vorgänge werden nicht als erfolgreich gewertet und lösen keinen automatischen Disc-Auswurf aus.

# Changelog – LunaVideoStudio

## 1.3.31
- Neue optionale Checkbox direkt im Bereich „Quelle auswählen“: „Disc nach erfolgreichem Rippen automatisch auswerfen“.
- Automatisches Auswerfen ist standardmäßig deaktiviert.
- Die Disc wird nur nach erfolgreich abgeschlossenem vollständigem Rippen ausgeworfen; bei Fehlern bleibt sie im Laufwerk.
- Der 1-Minuten-Testclip löst kein automatisches Auswerfen aus.
- Bestehende DVD-/Blu-ray-Verarbeitung und die Auswahl des Ausgabeformats wurden nicht gezielt verändert.
- GitHub-Quellarchiv und Debian-Paket auf Version 1.3.31 aktualisiert.

## 0.1.30
- Blu-ray-PGS-Untertitel werden bei MP4-Ausgabe per FFmpeg direkt ins Videobild eingebrannt.
- MP4 bleibt MP4; keine automatische Umstellung auf MKV bei ausgewählten Blu-ray-Untertiteln.
- 1-Minuten-Testclip verwendet dieselbe Einbrenn-Methode für ausgewählte Blu-ray-PGS-Untertitel.

## 0.1.24
- Frühere Ausgangsbasis für die DVD-/Blu-ray-Verarbeitung.

## 1.3.33
- Ausgabeformat wird auch beim 1-Minuten-Test entsprechend der Auswahl MP4, MKV oder AVI gesetzt.
- AVI verwendet MP3-Audio für eine kompatiblere AVI-Ausgabe.
- Blu-ray-PGS-Untertitel werden bei MP4 und AVI in das Bild eingebrannt; bei MKV bleiben sie als auswählbare PGS-Spur erhalten.
- Automatisches Auswerfen ermittelt das optische Laufwerk bei Bedarf erneut aus der Laufwerksauswahl, damit ein gewählter Quellordner den Laufwerksauswurf nicht verhindert.

## 1.3.35
- Fortschrittsbalken zeigt während des Encodings verarbeitete Zeit und Prozent an.
- FFmpeg-Fortschrittsausgabe wird live verarbeitet; stderr wird parallel geleert, um Pipe-Blockaden zu vermeiden.
