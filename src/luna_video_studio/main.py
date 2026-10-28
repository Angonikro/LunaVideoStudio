#!/usr/bin/env python3
"""Luna-Video-Studio: initial GTK4 interface prototype."""
import os
import re
import glob
import subprocess
import threading
import xml.etree.ElementTree as ET
import json
import shutil
import signal
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib

APP_VERSION = "1.3.85"

def normalize_language_code(value):
    """Normalize DVD language labels/codes to ISO-639-2 codes when possible."""
    text = (value or '').strip().lower()
    aliases = {
        'de': 'deu', 'ger': 'deu', 'german': 'deu', 'deutsch': 'deu',
        'en': 'eng', 'english': 'eng', 'fr': 'fra', 'fre': 'fra', 'french': 'fra', 'français': 'fra',
        'es': 'spa', 'spanish': 'spa', 'español': 'spa', 'it': 'ita', 'italian': 'ita', 'italiano': 'ita',
        'nl': 'nld', 'dut': 'nld', 'dutch': 'nld', 'nederlands': 'nld',
        'pt': 'por', 'ru': 'rus', 'ja': 'jpn', 'zh': 'zho', 'ko': 'kor',
        'sv': 'swe', 'da': 'dan', 'no': 'nor', 'fi': 'fin', 'pl': 'pol',
        'cs': 'ces', 'cze': 'ces', 'hu': 'hun', 'el': 'ell', 'gre': 'ell',
        'tr': 'tur', 'ar': 'ara', 'he': 'heb', 'und': '', 'xx': '',
    }
    if text in aliases:
        return aliases[text]
    # Labels often look like "de - German" or "Deutsch · DVD-Untertitel".
    for token in re.split(r'[^a-z]+', text):
        if token in aliases and aliases[token]:
            return aliases[token]
    if re.fullmatch(r'[a-z]{3}', text):
        return text
    return ''



def probe_ffmpeg_dvd_subtitle_streams(device, title):
    """Probe DVD subtitle streams as FFmpeg actually sees them.

    lsdvd SPU IDs do not reliably correspond to dvdvideo stream indexes on all
    discs. Use FFmpeg's own stream indexes and language tags for the burn filter.
    """
    command = [
        'ffprobe', '-v', 'error', '-f', 'dvdvideo', '-title', str(title or 1),
        '-i', str(device), '-show_streams', '-of', 'json'
    ]
    result = subprocess.run(command, capture_output=True, text=True, errors='replace', timeout=60, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        detail = (result.stderr or 'FFprobe konnte die DVD-Untertitel nicht lesen.').strip()
        raise RuntimeError(detail.splitlines()[-1])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError('FFprobe lieferte keine gültige Streamliste für die DVD.') from exc
    streams = []
    for stream in payload.get('streams', []):
        if stream.get('codec_type') != 'subtitle':
            continue
        tags = stream.get('tags') or {}
        language = normalize_language_code(tags.get('language', ''))
        stream_id = str(stream.get('id', '')).strip().lower()
        streams.append({'index': stream.get('index'), 'language': language, 'id': stream_id})
    return streams

def shutil_which(command):
    return shutil.which(command)

def bluray_stream_languages(mountpoint, playlist_id=None):
    """Read languages from the exact MPLS playlist, not the disc main title.

    Returns (audio_languages, subtitle_languages). Stream order follows the
    first clip in the selected playlist and is only a fallback when FFmpeg and
    MediaInfo provide no language tags.
    """
    import ctypes
    from ctypes.util import find_library

    library = find_library('bluray')
    if not library:
        return [], []
    class StreamInfo(ctypes.Structure):
        _fields_ = [('coding_type', ctypes.c_uint8), ('format', ctypes.c_uint8),
                    ('rate', ctypes.c_uint8), ('char_code', ctypes.c_uint8),
                    ('lang', ctypes.c_uint8 * 4), ('pid', ctypes.c_uint16),
                    ('aspect', ctypes.c_uint8), ('subpath_id', ctypes.c_uint8)]
    class ClipInfo(ctypes.Structure):
        _fields_ = [('pkt_count', ctypes.c_uint32), ('still_mode', ctypes.c_uint8),
                    ('still_time', ctypes.c_uint16), ('video_stream_count', ctypes.c_uint8),
                    ('audio_stream_count', ctypes.c_uint8), ('pg_stream_count', ctypes.c_uint8),
                    ('ig_stream_count', ctypes.c_uint8), ('sec_audio_stream_count', ctypes.c_uint8),
                    ('sec_video_stream_count', ctypes.c_uint8),
                    ('video_streams', ctypes.POINTER(StreamInfo)),
                    ('audio_streams', ctypes.POINTER(StreamInfo)),
                    ('pg_streams', ctypes.POINTER(StreamInfo)), ('ig_streams', ctypes.POINTER(StreamInfo)),
                    ('sec_audio_streams', ctypes.POINTER(StreamInfo)), ('sec_video_streams', ctypes.POINTER(StreamInfo)),
                    ('start_time', ctypes.c_uint64), ('in_time', ctypes.c_uint64),
                    ('out_time', ctypes.c_uint64), ('clip_id', ctypes.c_char * 6)]
    class TitleInfo(ctypes.Structure):
        _fields_ = [('idx', ctypes.c_uint32), ('playlist', ctypes.c_uint32),
                    ('duration', ctypes.c_uint64), ('clip_count', ctypes.c_uint32),
                    ('angle_count', ctypes.c_uint8), ('chapter_count', ctypes.c_uint32),
                    ('mark_count', ctypes.c_uint32), ('clips', ctypes.POINTER(ClipInfo)),
                    ('chapters', ctypes.c_void_p), ('marks', ctypes.c_void_p),
                    ('mvc_base_view_r_flag', ctypes.c_uint8)]
    lib = ctypes.CDLL(library)
    lib.bd_open.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.bd_open.restype = ctypes.c_void_p
    lib.bd_get_titles.argtypes = [ctypes.c_void_p, ctypes.c_uint8, ctypes.c_uint32]
    lib.bd_get_titles.restype = ctypes.c_uint32
    lib.bd_get_main_title.argtypes = [ctypes.c_void_p]
    lib.bd_get_main_title.restype = ctypes.c_int
    lib.bd_get_title_info.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint]
    lib.bd_get_title_info.restype = ctypes.POINTER(TitleInfo)
    lib.bd_free_title_info.argtypes = [ctypes.POINTER(TitleInfo)]
    lib.bd_close.argtypes = [ctypes.c_void_p]
    bd = lib.bd_open(os.fsencode(mountpoint), None)
    if not bd:
        return [], []
    try:
        title_count = int(lib.bd_get_titles(bd, 0, 0))
        if title_count <= 0:
            return [], []
        # libbluray's title index is not the MPLS playlist number. Walk the
        # title table and match TitleInfo.playlist to the selected playlist ID.
        ptr = None
        selected_ptr = None
        try:
            if playlist_id is not None:
                try:
                    wanted_playlist = int(playlist_id)
                except (TypeError, ValueError):
                    wanted_playlist = -1
                for title_idx in range(title_count):
                    candidate_ptr = lib.bd_get_title_info(bd, title_idx, 0)
                    if not candidate_ptr:
                        continue
                    if int(candidate_ptr.contents.playlist) == wanted_playlist:
                        selected_ptr = candidate_ptr
                        break
                    lib.bd_free_title_info(candidate_ptr)
            else:
                main_idx = int(lib.bd_get_main_title(bd))
                if main_idx >= 0:
                    selected_ptr = lib.bd_get_title_info(bd, main_idx, 0)
            if not selected_ptr or not selected_ptr.contents.clip_count:
                return [], []
            clip = selected_ptr.contents.clips[0]
            def read_langs_by_pid(array, count):
                # Match language metadata to FFmpeg's stream id/PID instead of
                # assuming libbluray and FFmpeg expose tracks in identical order.
                out = {}
                for i in range(min(int(count), 64)):
                    stream = array[i]
                    raw = bytes(stream.lang).split(b'\0', 1)[0].decode('ascii', 'ignore').lower()
                    if re.fullmatch(r'[a-z]{3}', raw):
                        out[int(stream.pid)] = raw
                return out
            return (read_langs_by_pid(clip.audio_streams, clip.audio_stream_count),
                    read_langs_by_pid(clip.pg_streams, clip.pg_stream_count))
        finally:
            if selected_ptr:
                lib.bd_free_title_info(selected_ptr)
    finally:
        lib.bd_close(bd)

LANGUAGE_NAMES = {'eng':'English', 'deu':'Deutsch', 'ger':'Deutsch', 'fra':'Französisch', 'fre':'Französisch',
                  'ita':'Italienisch', 'spa':'Spanisch', 'nld':'Niederländisch', 'dut':'Niederländisch',
                  'por':'Portugiesisch', 'jpn':'Japanisch', 'zho':'Chinesisch', 'chi':'Chinesisch',
                  'kor':'Koreanisch', 'ara':'Arabisch', 'tur':'Türkisch', 'pol':'Polnisch', 'rus':'Russisch',
                  'und':'Sprache unbekannt'}

def language_name(code):
    code = (code or '').strip().lower()
    return LANGUAGE_NAMES.get(code, code.upper() if re.fullmatch(r'[a-z]{3}', code) else 'Sprache unbekannt')

def format_duration(value):
    try:
        seconds = int(float(value))
        return f'{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}'
    except (TypeError, ValueError):
        return str(value or '—')

CSS = b'''
window { background: #0b1220; color: #e8eef9; }
.header { background: #101b2d; border-bottom: 1px solid #26364e; padding: 10px 16px; }
.brand { font-size: 22px; font-weight: 800; color: #f5f8ff; }
.subtitle { color: #a9bad3; font-size: 13px; }
.panel { background: #111d30; border: 1px solid #263850; border-radius: 14px; padding: 11px; }
.panel-title { font-size: 16px; font-weight: 700; color: #eaf2ff; }
.dim { color: #9fb1ca; }
.action { background: #3979f6; color: white; border-radius: 10px; padding: 10px 18px; font-weight: 700; }
.secondary { background: #1b2b42; color: #dce8fb; border-radius: 10px; padding: 8px 14px; }
statusbar { background: #0e1828; }
progressbar trough { min-height: 9px; border-radius: 6px; background: #25364d; }
progressbar progress { min-height: 9px; border-radius: 6px; background: #4e8cff; }
'''


TRANSLATIONS = {
    'Luna-Video-Studio': 'Luna Video Studio',
    'DVD & Blu-ray · MP4 · MKV · AVI': 'DVD & Blu-ray · MP4 · MKV · AVI',
    '1  ·  Quelle auswählen': '1  ·  Select source',
    'Optisches Laufwerk': 'Optical drive',
    'Kein optisches Laufwerk gefunden': 'No optical drive found',
    'Noch keine Quelle ausgewählt': 'No source selected yet',
    'Disc nach erfolgreichem Rippen automatisch auswerfen': 'Eject disc automatically after successful ripping',
    'Laufwerk suchen': 'Search drives',
    'VIDEO_TS / BDMV öffnen': 'Open VIDEO_TS / BDMV',
    'Disk auswerfen': 'Eject disc',
    'Disc einlesen': 'Read disc',
    '2  ·  Ausgabe einstellen': '2  ·  Configure output',
    'Zielformat': 'Output format',
    'Qualitätsprofil': 'Quality profile',
    'Hohe Qualität': 'High quality',
    'Ausgewogen': 'Balanced',
    'Kleine Datei': 'Small file',
    'Originalauflösung': 'Original resolution',
    'Audio automatisch normalisieren (−16 LUFS)': 'Automatically normalize audio (−16 LUFS)',
    'Zielordner': 'Output folder',
    'Zielordner wählen': 'Choose output folder',
    '3  ·  Titel, Tonspuren und Untertitel': '3  ·  Titles, audio tracks and subtitles',
    'Nach dem Einlesen der Disc werden erkannte Titel, Laufzeiten, Tonsprachen und Untertitel hier angezeigt.': 'Detected titles, durations, audio languages and subtitles appear here after reading the disc.',
    'Tonspur': 'Audio track',
    'Keine Tonspur erkannt': 'No audio track detected',
    'Tonspur wird beim Einlesen erkannt.': 'The audio track is detected when the disc is read.',
    'Untertitel': 'Subtitles',
    'Aus – keine Untertitel': 'Off – no subtitles',
    'Standard: Untertitel deaktiviert. Auswahl wird für die spätere Umwandlung vorgemerkt.': 'Subtitles are off by default. Your selection is saved for conversion.',
    'Noch keine Disc eingelesen': 'No disc read yet',
    '4  ·  Fortschritt': '4  ·  Progress',
    'Bereit – Quelle auswählen, um zu beginnen.': 'Ready – select a source to begin.',
    'Schließen': 'Close',
    'Rippen abbrechen': 'Cancel rip',
    'Rippen starten': 'Start rip',
    '1-Minuten-Test': '1-minute test',
    'DVD-/Blu-ray-Analyse und FFmpeg-Video-Encoding. 1-Minuten-Testclip aus der Filmmitte möglich.': 'DVD/Blu-ray analysis and FFmpeg video encoding. A 1-minute test clip from the middle of the film is available.',
    'DVD- oder Blu-ray-Ordner auswählen': 'Select DVD or Blu-ray folder',
    'Zielordner auswählen': 'Select output folder',
    'Laufzeit:': 'Elapsed:',
    'Gesamtdauer:': 'Total duration:',
    'Abgeschlossen': 'Completed',
    'Fehler': 'Error',
    'DVD eingelesen – Umwandlung startet …': 'DVD read – starting conversion …',
    'Ausgewählt:': 'Selected:',
    'Beim Rippen wird nur dieser Titel verwendet.': 'Only this title will be used for ripping.',
    'Quellordner ausgewählt. Klicke auf „Disc einlesen“, um die Analyse zu starten.': 'Source folder selected. Click “Read disc” to start analysis.',
    'Untertitel sind standardmäßig ausgeschaltet.': 'Subtitles are off by default.',
    'Keine Tonspuren für diesen Titel erkannt.': 'No audio tracks detected for this title.',
    'Keine Untertitelspuren für diesen Titel erkannt.': 'No subtitle tracks detected for this title.',
    'Deutsch': 'German',
    'Englisch': 'English',
}
def translated(text, language):
    if language != 'en' or not isinstance(text, str):
        return text
    if text in TRANSLATIONS:
        return TRANSLATIONS[text]
    # Translate recurring status fragments without altering technical names/paths.
    replacements = [
        ('Tonspur(en) für ausgewählten Titel erkannt.', ' audio track(s) detected for selected title.'),
        ('Untertitelspur(en) für ausgewählten Titel erkannt.', ' subtitle track(s) detected for selected title.'),
        ('Untertitel sind standardmäßig ausgeschaltet.', 'Subtitles are off by default.'),
        ('Quelle auswählen, um zu beginnen.', 'Select a source to begin.'),
        ('Rippen abgebrochen', 'Rip cancelled'),
        ('Rippen erfolgreich abgeschlossen', 'Rip completed successfully'),
        ('Encoding fehlgeschlagen', 'Encoding failed'),
        ('Conversion failed!', 'Conversion failed!'),
        ('Fertig', 'Completed'),
        ('Fehler', 'Error'),
        ('wird eingelesen', 'is being read'),
        ('Einlesen fehlgeschlagen', 'Reading failed'),
        ('Disc eingelesen', 'Disc read'),
        ('ausgewählt', 'selected'),
        ('Untertitel', 'Subtitles'),
        ('Tonspur', 'Audio track'),
    ]
    out = text
    for a,b in replacements:
        out = out.replace(a,b)
    return out

class LunaVideoStudio(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='de.goldisoft.lunavideostudio', flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.window = None
        self.language = 'de'
        self.settings_path = Path.home() / '.config' / 'luna-video-studio' / 'settings.json'
        try:
            self.language = json.loads(self.settings_path.read_text()).get('language', 'de')
        except Exception:
            self.language = 'de'
        if self.language not in ('de', 'en'):
            self.language = 'de'
        self._original_widget_text = {}
        self.source_path = None
        self.track_rows = []
        self.analysis_source = None
        self.rip_thread = None
        self.current_process = None
        self.cancel_requested = False
        self.subtitle_streams = []
        self.analysis_thread = None
        self.rip_started_at = None
        self.rip_timer_source = 0

    def do_activate(self):
        if self.window:
            self.window.present()
            return
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(self.get_active_window().get_display() if self.get_active_window() else GdkDisplay.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.window = Gtk.ApplicationWindow(application=self, title='Luna-Video-Studio')
        self.window.set_default_size(940, 660)
        self.window.set_size_request(720, 520)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.window.set_child(root)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        header.add_css_class('header')
        titlebox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        title = Gtk.Label(label='Luna-Video-Studio', xalign=0)
        title.add_css_class('brand')
        subtitle = Gtk.Label(label='DVD & Blu-ray · MP4 · MKV · AVI', xalign=0)
        subtitle.add_css_class('subtitle')
        titlebox.append(title); titlebox.append(subtitle)
        header.append(titlebox)
        spacer = Gtk.Box(); spacer.set_hexpand(True); header.append(spacer)
        # Language selector must be visible in the header, next to the version.
        self.language_model = Gtk.StringList.new(['Deutsch', 'English'])
        self.language_dropdown = Gtk.DropDown.new(self.language_model, None)
        self.language_dropdown.set_selected(1 if self.language == 'en' else 0)
        self.language_dropdown.set_tooltip_text('Sprache / Language')
        self.language_dropdown.connect('notify::selected', self._language_changed)
        header.append(self.language_dropdown)
        version = Gtk.Label(label=f'Goldisoft 2026  ·  {APP_VERSION}')
        version.add_css_class('dim'); header.append(version)
        root.append(header)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        body.set_margin_top(10); body.set_margin_bottom(9); body.set_margin_start(14); body.set_margin_end(14)
        body.set_vexpand(True)
        root.append(body)

        topgrid = Gtk.Grid(column_spacing=10, row_spacing=9)
        topgrid.set_column_homogeneous(True)
        body.append(topgrid)
        source_panel = self.panel('1  ·  Quelle auswählen')
        source_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        source_panel.append(source_box)
        self.drive_model = Gtk.StringList.new(self.detect_drives() or ['Kein optisches Laufwerk gefunden'])
        self.drive_dropdown = Gtk.DropDown.new(self.drive_model, None)
        source_box.append(self.label('Optisches Laufwerk'))
        source_box.append(self.drive_dropdown)
        self.source_label = Gtk.Label(label='Noch keine Quelle ausgewählt', xalign=0, wrap=True)
        self.source_label.add_css_class('dim')
        source_box.append(self.source_label)
        self.auto_eject_check = Gtk.CheckButton(label='Disc nach erfolgreichem Rippen automatisch auswerfen')
        self.auto_eject_check.set_active(False)
        source_box.append(self.auto_eject_check)
        source_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        scan_btn = Gtk.Button(label='Laufwerk suchen'); scan_btn.add_css_class('secondary'); scan_btn.connect('clicked', self.refresh_drives)
        folder_btn = Gtk.Button(label='VIDEO_TS / BDMV öffnen'); folder_btn.add_css_class('secondary'); folder_btn.connect('clicked', self.choose_folder)
        source_buttons.append(scan_btn); source_buttons.append(folder_btn)
        eject_btn = Gtk.Button(label='Disk auswerfen'); eject_btn.add_css_class('secondary'); eject_btn.connect('clicked', self.eject_disc)
        source_buttons.append(eject_btn)
        read_btn = Gtk.Button(label='Disc einlesen'); read_btn.add_css_class('action'); read_btn.connect('clicked', self.read_disc)
        source_buttons.append(read_btn); source_box.append(source_buttons)
        topgrid.attach(source_panel, 0, 0, 1, 1)

        output_panel = self.panel('2  ·  Ausgabe einstellen')
        output_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        output_panel.append(output_box)
        output_box.append(self.label('Zielformat'))
        self.format_dropdown = Gtk.DropDown.new_from_strings(['MP4', 'MKV', 'AVI'])
        output_box.append(self.format_dropdown)
        output_box.append(self.label('Qualitätsprofil'))
        self.quality_dropdown = Gtk.DropDown.new_from_strings(['Hohe Qualität', 'Ausgewogen', 'Kleine Datei', 'Originalauflösung'])
        output_box.append(self.quality_dropdown)
        self.normalize_audio_check = Gtk.CheckButton(label='Audio automatisch normalisieren (−16 LUFS)')
        self.normalize_audio_check.set_active(True)
        output_box.append(self.normalize_audio_check)
        output_box.append(self.label('Zielordner'))
        self.output_entry = Gtk.Entry()
        self.output_entry.set_text(str(Path.home() / 'Videos'))
        output_box.append(self.output_entry)
        choose_out = Gtk.Button(label='Zielordner wählen'); choose_out.add_css_class('secondary'); choose_out.connect('clicked', self.choose_output)
        output_box.append(choose_out)
        topgrid.attach(output_panel, 1, 0, 1, 1)

        tracks_panel = self.panel('3  ·  Titel, Tonspuren und Untertitel')
        body.append(tracks_panel)
        tracks_info = Gtk.Label(label='Nach dem Einlesen der Disc werden erkannte Titel, Laufzeiten, Tonsprachen und Untertitel hier angezeigt.', xalign=0, wrap=True)
        tracks_info.add_css_class('dim'); tracks_panel.append(tracks_info)
        audio_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        audio_row.append(self.label('Tonspur'))
        self.audio_dropdown = Gtk.DropDown.new_from_strings(['Keine Tonspur erkannt'])
        self.audio_dropdown.set_hexpand(True)
        audio_row.append(self.audio_dropdown)
        tracks_panel.append(audio_row)
        self.audio_hint = Gtk.Label(label='Tonspur wird beim Einlesen erkannt.', xalign=0, wrap=True)
        self.audio_hint.add_css_class('dim'); tracks_panel.append(self.audio_hint)
        subtitle_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        subtitle_row.append(self.label('Untertitel'))
        self.subtitle_dropdown = Gtk.DropDown.new_from_strings(['Aus – keine Untertitel'])
        self.subtitle_dropdown.set_hexpand(True)
        subtitle_row.append(self.subtitle_dropdown)
        tracks_panel.append(subtitle_row)
        self.subtitle_hint = Gtk.Label(label='Standard: Untertitel deaktiviert. Auswahl wird für die spätere Umwandlung vorgemerkt.', xalign=0, wrap=True)
        self.subtitle_hint.add_css_class('dim'); tracks_panel.append(self.subtitle_hint)
        self.track_placeholder = Gtk.Label(label='Noch keine Disc eingelesen', xalign=0)
        self.track_placeholder.set_margin_top(8); self.track_placeholder.set_margin_bottom(8)
        tracks_panel.append(self.track_placeholder)
        self.track_list = Gtk.ListBox()
        self.track_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.track_list.connect('row-selected', self._track_selected)
        self.track_list.set_visible(False)
        self.track_scroll = Gtk.ScrolledWindow()
        self.track_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.track_scroll.set_min_content_height(110)
        self.track_scroll.set_max_content_height(210)
        self.track_scroll.set_child(self.track_list)
        self.track_scroll.set_visible(False)
        tracks_panel.append(self.track_scroll)

        progress_panel = self.panel('4  ·  Fortschritt')
        body.append(progress_panel)
        self.status_label = Gtk.Label(label='Bereit – Quelle auswählen, um zu beginnen.', xalign=0)
        self.status_label.add_css_class('dim'); progress_panel.append(self.status_label)
        self.progress = Gtk.ProgressBar(); self.progress.set_fraction(0); self.progress.set_show_text(True); self.progress.set_text('0 %')
        progress_panel.append(self.progress)
        self.elapsed_label = Gtk.Label(label=translated('Laufzeit:', self.language) + ' 00:00:00', xalign=0)
        self.elapsed_label.add_css_class('dim')
        progress_panel.append(self.elapsed_label)

        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bottom.set_halign(Gtk.Align.END)
        body.append(bottom)
        self.close_btn = Gtk.Button(label='Schließen'); self.close_btn.add_css_class('secondary'); self.close_btn.connect('clicked', lambda *_: self.window.close())
        self.abort_btn = Gtk.Button(label='Rippen abbrechen'); self.abort_btn.add_css_class('secondary'); self.abort_btn.set_sensitive(False); self.abort_btn.connect('clicked', self.cancel_rip)
        self.start_btn = Gtk.Button(label='Rippen starten'); self.start_btn.add_css_class('action'); self.start_btn.connect('clicked', self.start_rip)
        self.test_btn = Gtk.Button(label='1-Minuten-Test'); self.test_btn.add_css_class('secondary'); self.test_btn.connect('clicked', self.start_test_rip)
        bottom.append(self.close_btn); bottom.append(self.abort_btn); bottom.append(self.test_btn); bottom.append(self.start_btn)

        footer = Gtk.Label(label='DVD-/Blu-ray-Analyse und FFmpeg-Video-Encoding. 1-Minuten-Testclip aus der Filmmitte möglich.', xalign=0, wrap=True)
        footer.set_margin_start(20); footer.set_margin_end(20); footer.set_margin_bottom(12); footer.add_css_class('dim')
        root.append(footer)
        self.window.present()
        self._apply_language()

    def _language_changed(self, dropdown, _pspec):
        self.language = 'en' if dropdown.get_selected() == 1 else 'de'
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(json.dumps({'language': self.language}, ensure_ascii=False, indent=2))
        except Exception:
            pass
        self._rebuild_for_language()

    def _rebuild_for_language(self):
        """Recreate the complete GTK window while retaining the current workflow state."""
        old = self.window
        if old is None:
            self.do_activate()
            return

        def dropdown_state(widget):
            model = widget.get_model()
            values = []
            if model is not None:
                for i in range(model.get_n_items()):
                    item = model.get_item(i)
                    values.append(item.get_string() if hasattr(item, 'get_string') else str(item))
            return values, widget.get_selected()

        snapshot = {
            'output_folder': self.output_entry.get_text(),
            'auto_eject': self.auto_eject_check.get_active(),
            'normalize': self.normalize_audio_check.get_active(),
            'format': dropdown_state(self.format_dropdown),
            'quality': dropdown_state(self.quality_dropdown),
            'drive': dropdown_state(self.drive_dropdown),
            'audio': dropdown_state(self.audio_dropdown),
            'subtitles': dropdown_state(self.subtitle_dropdown),
            'source_label': self.source_label.get_text(),
            'status': self.status_label.get_text(),
            'elapsed': self.elapsed_label.get_text(),
            'progress_fraction': self.progress.get_fraction(),
            'progress_text': self.progress.get_text(),
            'track_placeholder': self.track_placeholder.get_text(),
            'track_list_visible': self.track_list.get_visible(),
            'track_scroll_visible': self.track_scroll.get_visible(),
            'abort_sensitive': self.abort_btn.get_sensitive(),
            'start_sensitive': self.start_btn.get_sensitive(),
            'test_sensitive': self.test_btn.get_sensitive(),
        }
        # Destroy only the view. The application, worker threads, subprocesses,
        # source path, track metadata and cancellation state remain untouched.
        self.window = None
        old.destroy()
        self._original_widget_text = {}
        self.do_activate()

        self.output_entry.set_text(snapshot['output_folder'])
        self.auto_eject_check.set_active(snapshot['auto_eject'])
        self.normalize_audio_check.set_active(snapshot['normalize'])
        for name in ('format', 'quality', 'drive', 'audio', 'subtitles'):
            dropdown = getattr(self, {'format':'format_dropdown','quality':'quality_dropdown','drive':'drive_dropdown','audio':'audio_dropdown','subtitles':'subtitle_dropdown'}[name])
            values, selected = snapshot[name]
            if values:
                dropdown.set_model(Gtk.StringList.new(values))
                dropdown.set_selected(min(selected, len(values)-1))
        self.source_label.set_text(snapshot['source_label'])
        self.status_label.set_text(snapshot['status'])
        self.elapsed_label.set_text(snapshot['elapsed'])
        self.progress.set_fraction(snapshot['progress_fraction'])
        self.progress.set_text(snapshot['progress_text'])
        self.track_placeholder.set_text(snapshot['track_placeholder'])
        self.track_list.set_visible(snapshot['track_list_visible'])
        self.track_scroll.set_visible(snapshot['track_scroll_visible'])
        self.abort_btn.set_sensitive(snapshot['abort_sensitive'])
        self.start_btn.set_sensitive(snapshot['start_sensitive'])
        self.test_btn.set_sensitive(snapshot['test_sensitive'])
        self._apply_language()

    def _apply_language(self):
        if not self.window:
            return
        def walk(widget):
            if widget not in self._original_widget_text:
                text = None
                if isinstance(widget, Gtk.Label):
                    text = widget.get_text()
                elif isinstance(widget, Gtk.Button):
                    text = widget.get_label()
                elif isinstance(widget, Gtk.CheckButton):
                    text = widget.get_label()
                if text is not None:
                    self._original_widget_text[widget] = text
            original = self._original_widget_text.get(widget)
            if original is not None:
                new_text = translated(original, self.language)
                if isinstance(widget, Gtk.Label):
                    widget.set_text(new_text)
                elif isinstance(widget, Gtk.Button):
                    widget.set_label(new_text)
                elif isinstance(widget, Gtk.CheckButton):
                    widget.set_label(new_text)
            if isinstance(widget, Gtk.DropDown) and widget is self.language_dropdown:
                pass
            child = widget.get_first_child() if hasattr(widget, 'get_first_child') else None
            while child:
                walk(child)
                child = child.get_next_sibling()
        walk(self.window)
        # Translate fixed dropdown models too; dynamically discovered tracks keep
        # their original language labels supplied by the disc metadata.
        for dropdown, german, english in [
            (getattr(self, 'format_dropdown', None), ['MP4', 'MKV', 'AVI'], ['MP4', 'MKV', 'AVI']),
            (getattr(self, 'quality_dropdown', None), ['Hohe Qualität', 'Ausgewogen', 'Kleine Datei', 'Originalauflösung'], ['High quality', 'Balanced', 'Small file', 'Original resolution']),
        ]:
            if dropdown is not None:
                selected = dropdown.get_selected()
                labels = german if self.language == 'de' else english
                dropdown.set_model(Gtk.StringList.new(labels))
                dropdown.set_selected(min(selected, len(labels)-1))

    def panel(self, heading):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.add_css_class('panel')
        label = Gtk.Label(label=heading, xalign=0); label.add_css_class('panel-title'); box.append(label)
        return box

    def label(self, text):
        label = Gtk.Label(label=text, xalign=0); label.add_css_class('dim'); return label

    def detect_drives(self):
        """Detect Linux optical drives the same way as LunaRipper and describe their media capabilities."""
        found = []
        devices = sorted(set(glob.glob('/dev/sr[0-9]*')))
        for device in devices:
            if not Path(device).exists() or not Path(device).name[2:].isdigit():
                continue
            props = {}
            try:
                result = subprocess.run(
                    ['udevadm', 'info', '--query=property', f'--name={device}'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='replace', timeout=4, check=False
                )
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if '=' in line:
                            key, value = line.split('=', 1)
                            props[key] = value
            except (OSError, subprocess.TimeoutExpired):
                pass
            kinds = []
            if props.get('ID_CDROM') == '1': kinds.append('CD')
            if props.get('ID_CDROM_DVD') == '1': kinds.append('DVD')
            if props.get('ID_CDROM_BD') == '1': kinds.append('Blu-ray')
            detail = '/'.join(kinds) if kinds else 'optisches Laufwerk'
            model = props.get('ID_MODEL') or props.get('ID_VENDOR')
            if model:
                detail += f' · {model.replace("_", " ").strip()}'
            found.append(f'{device} — {detail}')
        return found

    def refresh_drives(self, *_):
        """Refresh the optical-drive list without restarting the application."""
        selected_before = self.drive_dropdown.get_selected_item()
        previous = selected_before.get_string() if selected_before else ''
        drives = self.detect_drives()
        self.drive_model.splice(0, self.drive_model.get_n_items(), drives or ['Kein optisches Laufwerk gefunden'])
        selected = next((i for i, item in enumerate(drives) if item == previous), 0)
        self.drive_dropdown.set_selected(selected)
        if drives:
            self.status_label.set_text(f'{len(drives)} optisches Laufwerk/Laufwerke gefunden.')
        else:
            self.status_label.set_text('Kein optisches Laufwerk gefunden. Bitte Laufwerk anschließen und erneut suchen.')

    def selected_device(self):
        item = self.drive_dropdown.get_selected_item()
        drive = item.get_string() if item else ''
        if not drive or drive.startswith('Kein optisches'):
            return None
        return drive.split(' — ', 1)[0]

    def eject_disc(self, *_):
        """Eject the optical drive off the GTK main thread so the UI stays responsive."""
        device = self.source_path or self.selected_device()
        if not device or not device.startswith('/dev/'):
            self.status_label.set_text('Bitte zuerst ein optisches Laufwerk auswählen.')
            return
        eject = shutil_which('eject')
        if not eject:
            self.status_label.set_text('Das Programm „eject“ fehlt. Bitte das Paket eject installieren.')
            return
        if getattr(self, '_eject_in_progress', False):
            self.status_label.set_text('Auswerfen läuft bereits …')
            return
        self._eject_in_progress = True
        self.status_label.set_text(f'Laufwerk {device} wird im Hintergrund ausgeworfen …')
        def run_eject():
            try:
                result = subprocess.run([eject, device], capture_output=True, text=True, errors='replace', timeout=20, check=False)
                if result.returncode == 0:
                    message = f'Laufwerk {device} wurde zum Auswerfen angewiesen.'
                else:
                    detail = (result.stderr or result.stdout or 'Unbekannter Laufwerksfehler').strip().splitlines()
                    message = f'Disk konnte nicht ausgeworfen werden: {detail[-1] if detail else "Unbekannter Laufwerksfehler"}'
            except (OSError, subprocess.TimeoutExpired) as exc:
                message = f'Auswerfen fehlgeschlagen: {exc}'
            GLib.idle_add(self._eject_finished, message)
        threading.Thread(target=run_eject, name='lvs-eject', daemon=True).start()

    def _eject_finished(self, message):
        self._eject_in_progress = False
        self.status_label.set_text(message)
        return GLib.SOURCE_REMOVE

    def check_drive(self, *_):
        device = self.selected_device()
        if not device:
            self.status_label.set_text('Kein optisches Laufwerk gefunden. Bitte Laufwerk suchen.')
            return
        self.source_path = device
        self.source_label.set_text(f'Gewähltes Laufwerk: {device}')

    def read_disc(self, *_):
        device = self.source_path or self.selected_device()
        if not device:
            self.status_label.set_text('Bitte zuerst ein optisches Laufwerk auswählen oder einen VIDEO_TS-/BDMV-Ordner öffnen.')
            return
        self.source_path = device
        self.current_analysis_source = device
        self.start_btn.set_sensitive(False)
        self.status_label.set_text('Disc wird eingelesen …')
        self.track_placeholder.set_text('Analyse läuft …')
        self.progress.set_fraction(0.05)
        self.progress.set_text('Analysiere Disc …')
        self.analysis_thread = threading.Thread(target=self._analysis_worker_safe, args=(device,), daemon=True)
        self.analysis_thread.start()

    def _analysis_worker_safe(self, source):
        """Keep unexpected probe errors visible in the UI instead of silently dying in the worker."""
        try:
            self._analysis_worker(source)
        except Exception as exc:
            GLib.idle_add(self._analysis_finished, [], f'Einlesen fehlgeschlagen ({type(exc).__name__}): {exc}')

    def _analysis_worker(self, source):
        tracks = []
        messages = []
        is_folder = os.path.isdir(source)
        # Keep the proven DVD path from 0.1.12. Only skip lsdvd for a mounted
        # Blu-ray BDMV structure, because lsdvd is a DVD-only tool.
        device_mountpoints = []
        if source.startswith('/dev/'):
            try:
                with open('/proc/mounts', 'r', encoding='utf-8') as mounts_file:
                    for line in mounts_file:
                        fields = line.split()
                        if len(fields) >= 2 and fields[0] == source:
                            device_mountpoints.append(fields[1].replace('\\040', ' '))
            except OSError:
                pass
        folder_is_bluray = is_folder and (
            os.path.isdir(os.path.join(source, 'BDMV')) or
            os.path.basename(source).upper() == 'BDMV'
        )
        device_is_bluray = any(os.path.isdir(os.path.join(mp, 'BDMV')) for mp in device_mountpoints)
        is_bluray_source = folder_is_bluray or device_is_bluray
        if shutil_which('lsdvd') and (is_folder or source.startswith('/dev/')) and not is_bluray_source:
            try:
                result = subprocess.run(['lsdvd', '-Ox', source], capture_output=True, text=True, errors='replace', timeout=60, check=False)
                parsed = False
                if result.returncode == 0 and result.stdout.strip():
                    try:
                        root = ET.fromstring(result.stdout)
                        for i, title in enumerate(root.findall('.//title'), 1):
                            number = title.findtext('ix') or str(i)
                            length = title.findtext('length') or '—'
                            chapters = len(title.findall('.//chapter'))
                            seconds = float(length) if length != '—' else 0
                            # lsdvd XML exposes DVD subpicture streams per title.
                            # Keep the language code and stream ID so the UI can offer
                            # explicit subtitle selection, including the disabled option.
                            audio_choices = []
                            for audio in title.findall('./audio'):
                                language = (audio.findtext('langcode') or audio.findtext('language') or '').strip()
                                lang_match = re.match(r'([a-zA-Z]{2,3})\s*-\s*(.+)', language)
                                if lang_match: language = lang_match.group(2).strip()
                                language = language or 'Sprache unbekannt'
                                codec = (audio.findtext('format') or audio.findtext('content') or 'DVD-Audio').strip()
                                stream_id = (audio.findtext('streamid') or audio.findtext('stream_id') or '').strip()
                                label = f'{language} · {codec}' + (f' (Spur {stream_id})' if stream_id else '')
                                audio_choices.append({'label': label, 'index': stream_id or str(len(audio_choices)), 'language': language, 'codec': codec})
                            subtitle_choices = []
                            for sub in title.findall('./subpicture'):
                                stream_id = (sub.findtext('streamid') or sub.findtext('stream_id') or '').strip()
                                language = (sub.findtext('langcode') or sub.findtext('language') or '').strip()
                                if not language or language.lower() in ('xx', 'und', 'unknown'):
                                    language = 'Sprache unbekannt'
                                codec = (sub.findtext('format') or 'DVD-Untertitel').strip()
                                # Keep the DVD SPU stream ID for display and diagnostics.
                                # FFmpeg's actual stream index is resolved separately via ffprobe.
                                ordinal_text = (sub.findtext('ix') or '').strip()
                                display_id = stream_id or ordinal_text or str(len(subtitle_choices))
                                label = f'{language} · {codec} (Spur {display_id})'
                                subtitle_choices.append({'label': label, 'index': display_id, 'has_spu_id': bool(stream_id and re.fullmatch(r'0x(?:2[0-9a-fA-F]|3[0-9a-fA-F])', stream_id)), 'language': language, 'codec': codec})
                            audio_count = len(title.findall('./audio'))
                            if seconds > 1:
                                detail = f'{chapters} Kapitel · DVD'
                                if audio_count or subtitle_choices:
                                    detail += f' · {audio_count} Tonspuren · {len(subtitle_choices)} Untertitel'
                                tracks.append({'title': f'DVD-Titel {number}', 'duration': format_duration(length), 'duration_seconds': seconds, 'input_path': source, 'dvd_title': int(number), 'details': detail, 'subtitles': subtitle_choices, 'audio': audio_choices})
                        parsed = bool(tracks)
                    except ET.ParseError:
                        parsed = False
                # Always inspect the human-readable output too: some lsdvd builds
                # return valid XML for title timing but omit subpicture details there.
                # The text output contains the per-title Subtitle lines and stream IDs.
                # Use the same verbose mode that exposes Subtitle/Stream id rows on the user's lsdvd build.
                text_result = subprocess.run(['lsdvd', '-x', source], capture_output=True, text=True, errors='replace', timeout=60, check=False)
                text_output = text_result.stdout or ''
                if not re.search(r'^\s*Subtitle:\s*\d+', text_output, re.MULTILINE):
                    # Some lsdvd builds only print subtitle rows without -x.
                    fallback_result = subprocess.run(['lsdvd', source], capture_output=True, text=True, errors='replace', timeout=60, check=False)
                    if fallback_result.stdout:
                        text_output = fallback_result.stdout
                title_re = re.compile(r'^Title:\s*(\d+),\s*Length:\s*([0-9:.]+)\s*Chapters:\s*(\d+)', re.MULTILINE)
                audio_re = re.compile(r'^\s*Audio:\s*(\d+),\s*Language:\s*([^,]+)(?:,.*?Stream id:\s*(0x[0-9a-fA-F]+))?', re.MULTILINE)
                subtitle_re = re.compile(r'^\s*Subtitle:\s*(\d+),\s*Language:\s*([^,]+)(?:,.*?Stream id:\s*(0x[0-9a-fA-F]+))?', re.MULTILINE)
                blocks = re.split(r'(?=^Title:\s*\d+\s*,)', text_output, flags=re.MULTILINE)
                text_titles = {}
                for block in blocks:
                    tm = title_re.search(block)
                    if not tm:
                        continue
                    number, length, chapters = tm.groups()
                    audios = []
                    for am in audio_re.finditer(block):
                        audio_number, lang_text, stream_id = am.groups()
                        lang_text = lang_text.strip()
                        lang_match = re.match(r'([a-zA-Z]{2,3})\s*-\s*(.+)', lang_text)
                        language = lang_match.group(2).strip() if lang_match else lang_text
                        stream_id = stream_id or f'Spur {audio_number}'
                        audios.append({'label': f'{language} · DVD-Audio (Spur {stream_id})', 'index': stream_id, 'language': language, 'codec': 'DVD-Audio'})
                    subs = []
                    for sm in subtitle_re.finditer(block):
                        sub_number, lang_text, stream_id = sm.groups()
                        lang_text = lang_text.strip()
                        language = lang_text
                        lang_match = re.match(r'([a-zA-Z]{2,3})\s*-\s*(.+)', lang_text)
                        if lang_match:
                            language = lang_match.group(2).strip()
                        language = language or 'Sprache unbekannt'
                        stream_id = stream_id or f'Spur {sub_number}'
                        label = f'{language} · DVD-Untertitel (Spur {stream_id})'
                        has_spu_id = bool(stream_id and re.fullmatch(r'0x(?:2[0-9a-fA-F]|3[0-9a-fA-F])', stream_id))
                        subs.append({'label': label, 'index': stream_id, 'has_spu_id': has_spu_id, 'language': language, 'codec': 'DVD-Untertitel'})
                    text_titles[number] = (length, chapters, subs, audios)
                if not parsed:
                    for number, (length, chapters, subs, audios) in text_titles.items():
                        parts = length.split(':')
                        try:
                            seconds = sum(float(part) * (60 ** power) for power, part in enumerate(reversed(parts)))
                        except ValueError:
                            seconds = 0
                        if seconds > 1:
                            tracks.append({'title': f'DVD-Titel {number}', 'duration': length, 'duration_seconds': seconds, 'input_path': source, 'dvd_title': int(number), 'details': f'{chapters} Kapitel · DVD · {len(subs)} Untertitel', 'subtitles': subs, 'audio': audios})
                else:
                    # Prefer the known per-title text metadata whenever it provides
                    # subtitle information; XML title order is not always reliable.
                    by_number = {re.search(r'(\d+)$', t['title']).group(1): t for t in tracks if re.search(r'(\d+)$', t['title'])}
                    for number, (length, chapters, subs, audios) in text_titles.items():
                        target = by_number.get(number)
                        if target and (subs or audios):
                            # Prefer XML subtitle entries when they include reliable
                            # per-title DVD SPU stream IDs; otherwise use text metadata.
                            xml_subs = target.get('subtitles') or []
                            xml_has_spu_ids = bool(xml_subs) and all(
                                item.get('has_spu_id', False) for item in xml_subs
                            )
                            if subs and not xml_has_spu_ids:
                                target['subtitles'] = subs
                            if audios:
                                target['audio'] = audios
                            actual_subs = target.get('subtitles') or []
                            target['details'] = re.sub(r' · \d+ Untertitel', '', target['details'])
                            target['details'] += f' · {len(actual_subs)} Untertitel'
                if not tracks and result.stderr.strip():
                    messages.append(result.stderr.strip().splitlines()[-1])
            except (OSError, subprocess.TimeoutExpired, ET.ParseError) as exc:
                messages.append(f'DVD-Analyse: {exc}')
        # Blu-ray: enumerate playlists instead of asking FFmpeg for only its default/main title.
        # FFmpeg's libbluray demuxer accepts -playlist before -i. Playlist IDs come
        # from BDMV/PLAYLIST/*.mpls; each candidate is probed independently.
        ffprobe = shutil_which('ffprobe')
        if ffprobe:
            mountpoints = []
            if is_folder:
                base = source
                if os.path.basename(base).upper() == 'BDMV':
                    base = os.path.dirname(base)
                mountpoints = [base, source]
            elif source.startswith('/dev/'):
                mountpoints = list(device_mountpoints)
            found_bluray = False
            seen_mounts = set()
            for mountpoint in mountpoints:
                if mountpoint in seen_mounts:
                    continue
                seen_mounts.add(mountpoint)
                playlist_dir = os.path.join(mountpoint, 'BDMV', 'PLAYLIST')
                try:
                    playlist_ids = sorted({Path(name).stem for name in os.listdir(playlist_dir)
                                           if name.lower().endswith('.mpls') and Path(name).stem.isdigit()})
                except OSError:
                    playlist_ids = []
                # If playlist filenames cannot be enumerated, retain the old default probe.
                candidates = playlist_ids or [None]
                for playlist_id in candidates:
                    candidate = f'bluray:{mountpoint}'
                    probe_cmd = [ffprobe, '-v', 'error', '-show_format', '-show_streams', '-of', 'json']
                    if playlist_id is not None:
                        probe_cmd += ['-playlist', playlist_id]
                    probe_cmd += [candidate]
                    try:
                        result = subprocess.run(probe_cmd, capture_output=True, text=True, errors='replace', timeout=90, check=False)
                        if result.returncode != 0 or not result.stdout.strip():
                            error_text = (result.stderr or '').strip()
                            if error_text and any(term in error_text.lower() for term in ("can't decrypt", 'aacs', 'no valid aacs')):
                                messages.append('Blu-ray kann nicht entschlüsselt werden. Bitte die AACS-Konfiguration und den Zugriff auf die Disc prüfen.')
                            continue
                        data = json.loads(result.stdout)
                        duration = float(data.get('format', {}).get('duration', 0) or 0)
                        if duration <= 1:
                            continue
                        streams = data.get('streams', [])
                        audio_streams = [stream for stream in streams if stream.get('codec_type') == 'audio']
                        subtitle_streams = [stream for stream in streams if stream.get('codec_type') == 'subtitle']
                        # Restore 1.3.54 language recovery: FFmpeg often omits Blu-ray language tags.
                        # MediaInfo is accepted only when its track counts exactly match this playlist.
                        mediainfo_tracks = {'audio': [], 'text': []}
                        mediainfo = shutil_which('mediainfo')
                        if mediainfo:
                            for media_path in (os.path.join(mountpoint, 'BDMV', 'index.bdmv'), mountpoint):
                                try:
                                    mi = subprocess.run([mediainfo, '--Output=JSON', media_path], capture_output=True, text=True, errors='replace', timeout=60, check=False)
                                    if mi.returncode == 0 and mi.stdout.strip():
                                        mi_data = json.loads(mi.stdout)
                                        media_obj = mi_data.get('media', {}) if isinstance(mi_data, dict) else {}
                                        media = media_obj.get('track', []) if isinstance(media_obj, dict) else media_obj
                                        if isinstance(media, dict): media = [media]
                                        if not isinstance(media, list): media = []
                                        media = [x for x in media if isinstance(x, dict)]
                                        aud = [x for x in media if x.get('@type') == 'Audio']
                                        txt = [x for x in media if x.get('@type') == 'Text']
                                        if len(aud) == len(audio_streams) and len(txt) == len(subtitle_streams) and (aud or txt):
                                            mediainfo_tracks = {'audio': aud, 'text': txt}
                                            break
                                except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
                                    continue
                        bd_audio_langs, bd_subtitle_langs = bluray_stream_languages(mountpoint, playlist_id)
                        def language_for_bluray_stream(stream, pid_languages):
                            # FFprobe reports Blu-ray transport stream PIDs as hex IDs
                            # (for example 0x1200). Use the PID as the join key.
                            stream_id = str(stream.get('id', '')).strip().lower()
                            try:
                                pid = int(stream_id, 0)
                            except (TypeError, ValueError):
                                pid = None
                            return pid_languages.get(pid, '') if pid is not None else ''
                        title_label = f'Blu-ray-Playlist {playlist_id}' if playlist_id else 'Blu-ray-Haupttitel'
                        details = f'Blu-ray · {len(audio_streams)} Tonspuren · {len(subtitle_streams)} Untertitel'
                        if playlist_id:
                            details += f' · Playlist {playlist_id}'
                        details += f' · {mountpoint}'
                        audio_choices = []
                        for track_no, stream in enumerate(audio_streams):
                            tags = stream.get('tags', {}) or {}
                            mi_track = mediainfo_tracks['audio'][track_no] if track_no < len(mediainfo_tracks['audio']) else {}
                            bd_language = language_for_bluray_stream(stream, bd_audio_langs)
                            language = tags.get('language') or tags.get('LANGUAGE') or language_name(bd_language) if (tags.get('language') or tags.get('LANGUAGE') or bd_language) else (mi_track.get('Language') or mi_track.get('Language/String3') or 'Sprache unbekannt')
                            title_tag = tags.get('title') or tags.get('handler_name') or mi_track.get('Title')
                            codec = stream.get('codec_name') or mi_track.get('Format') or 'Audio'
                            index = stream.get('index', '?')
                            label = f'{language} · {title_tag} · {codec} (Stream {index})' if title_tag else f'{language} · {codec} (Stream {index})'
                            audio_choices.append({'label': label, 'index': index, 'language': language, 'codec': codec})
                        subtitle_choices = []
                        for track_no, stream in enumerate(subtitle_streams):
                            tags = stream.get('tags', {}) or {}
                            mi_track = mediainfo_tracks['text'][track_no] if track_no < len(mediainfo_tracks['text']) else {}
                            bd_language = language_for_bluray_stream(stream, bd_subtitle_langs)
                            language = tags.get('language') or tags.get('LANGUAGE') or language_name(bd_language) if (tags.get('language') or tags.get('LANGUAGE') or bd_language) else (mi_track.get('Language') or mi_track.get('Language/String3') or 'Sprache unbekannt')
                            title_tag = tags.get('title') or tags.get('handler_name') or mi_track.get('Title')
                            codec = stream.get('codec_name') or mi_track.get('Format') or 'Untertitel'
                            index = stream.get('index', '?')
                            label = f'{language} · {title_tag} · {codec} (Stream {index})' if title_tag else f'{language} · {codec} (Stream {index})'
                            subtitle_choices.append({'label': label, 'index': index, 'relative_index': track_no, 'language': language, 'codec': codec})
                        tracks.append({'title': title_label, 'duration': format_duration(duration),
                                       'duration_seconds': duration, 'input_path': candidate,
                                       'bluray_playlist': playlist_id, 'details': details,
                                       'subtitles': subtitle_choices, 'audio': audio_choices})
                        found_bluray = True
                    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError) as exc:
                        messages.append(f'Blu-ray-Analyse: {exc}')
            if not found_bluray and not tracks and not mountpoints:
                messages.append('Für Blu-ray wurde kein eingehängter Disc-Pfad gefunden. Bitte Disc einlegen und Dateimanager prüfen.')
        else:
            messages.append('ffprobe fehlt; FFmpeg wird für die Medienanalyse benötigt.')
        if not tracks:
            detail = messages[-1] if messages else 'Keine lesbaren DVD-Titel oder Blu-ray-Playlist gefunden.'
            GLib.idle_add(self._analysis_finished, [], f'Einlesen nicht erfolgreich: {detail}')
        else:
            GLib.idle_add(self._analysis_finished, tracks, f'{len(tracks)} Titel gefunden. Video-Umwandlung wird im nächsten Schritt ergänzt.')

    def _analysis_finished(self, tracks, message):
        while row := self.track_list.get_row_at_index(0):
            self.track_list.remove(row)
        self.track_rows = tracks
        self.analysis_source = getattr(self, 'current_analysis_source', None)
        self.subtitle_streams = []
        self.audio_streams = []
        if tracks:
            # Select the longest title as a sensible initial suggestion, but let the user choose.
            suggested = max(range(len(tracks)), key=lambda i: float(tracks[i].get('duration_seconds') or 0))
            self.track_placeholder.set_visible(False)
            for item in tracks:
                row = Gtk.ListBoxRow()
                line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                line.set_margin_top(5); line.set_margin_bottom(5); line.set_margin_start(6); line.set_margin_end(6)
                name = Gtk.Label(label=item['title'], xalign=0); name.set_hexpand(True)
                duration = Gtk.Label(label=item['duration'], xalign=1)
                details = Gtk.Label(label=item['details'], xalign=1); details.add_css_class('dim')
                line.append(name); line.append(duration); line.append(details); row.set_child(line); self.track_list.append(row)
            self.track_list.set_visible(True)
            self.track_scroll.set_visible(True)
            self.track_list.select_row(self.track_list.get_row_at_index(suggested))
            self._populate_stream_choices(tracks[suggested])
        else:
            self.audio_streams = []
            self.audio_dropdown.set_model(Gtk.StringList.new(['Keine Tonspur erkannt']))
            self.audio_dropdown.set_selected(0)
            self.audio_hint.set_text('Tonspur wird beim Einlesen erkannt.')
            self.subtitle_dropdown.set_model(Gtk.StringList.new(['Aus – keine Untertitel']))
            self.subtitle_dropdown.set_selected(0)
            self.subtitle_hint.set_text('Standard: Untertitel deaktiviert.')
            self.track_placeholder.set_visible(True)
            self.track_placeholder.set_text(message)
            self.track_list.set_visible(False)
            self.track_scroll.set_visible(False)
        self.status_label.set_text(message)
        # Suggest a film-named output folder after successful disc analysis.
        # Only change the default Videos target; preserve a path the user chose.
        if tracks:
            disc_name = self._detect_disc_name(self.analysis_source, tracks)
            current_output = os.path.normpath(os.path.expanduser(self.output_entry.get_text().strip() or str(Path.home() / 'Videos')))
            default_output = os.path.normpath(str(Path.home() / 'Videos'))
            if disc_name and current_output in (default_output, os.path.normpath(str(Path.home() / 'Videos' / disc_name))):
                self.output_entry.set_text(str(Path.home() / 'Videos' / disc_name))
        self.progress.set_fraction(1.0 if tracks else 0.0)
        self.progress.set_text('Analyse abgeschlossen' if tracks else 'Analyse fehlgeschlagen')
        self.start_btn.set_sensitive(True)
        return GLib.SOURCE_REMOVE

    def _detect_disc_name(self, source, tracks):
        """Best-effort disc/volume name for the output directory suggestion."""
        candidates = []
        if source and os.path.isdir(source):
            path = Path(source)
            if path.name.upper() in ('VIDEO_TS', 'BDMV'):
                candidates.append(path.parent.name)
            else:
                candidates.append(path.name)
        elif source and source.startswith('/dev/') and shutil_which('blkid'):
            try:
                result = subprocess.run(
                    ['blkid', '-o', 'value', '-s', 'LABEL', source],
                    capture_output=True, text=True, errors='replace', timeout=5, check=False
                )
                if result.returncode == 0 and result.stdout.strip():
                    candidates.append(result.stdout.strip())
            except (OSError, subprocess.TimeoutExpired):
                pass
        # lsdvd sometimes exposes the DVD volume title in its human-readable output.
        if source and source.startswith('/dev/') and shutil_which('lsdvd'):
            try:
                result = subprocess.run(['lsdvd', source], capture_output=True, text=True, errors='replace', timeout=10, check=False)
                match = re.search(r'^Disc Title:\s*(.+?)\s*$', result.stdout or '', re.MULTILINE | re.IGNORECASE)
                if match:
                    candidates.append(match.group(1))
            except (OSError, subprocess.TimeoutExpired):
                pass
        for candidate in candidates:
            cleaned = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', candidate).strip(' ._')
            cleaned = re.sub(r'\s+', ' ', cleaned)
            if cleaned and cleaned.lower() not in {'video_ts', 'bdmv', 'dvd', 'bluray', 'blu-ray', 'unknown'}:
                return cleaned[:100]
        # Avoid using generic track labels such as "Title 1" as a film name.
        if tracks:
            title = str(max(tracks, key=lambda t: float(t.get('duration_seconds') or 0)).get('title', '')).strip()
            if title and not re.fullmatch(r'(?:title|titel)\s*\d+', title, re.IGNORECASE):
                cleaned = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', title).strip(' ._')
                if cleaned:
                    return cleaned[:100]
        return None

    def _populate_stream_choices(self, track):
        self.audio_streams = track.get('audio', [])
        audio_choices = [item['label'] for item in self.audio_streams] or ['Keine Tonspur erkannt']
        self.audio_dropdown.set_model(Gtk.StringList.new(audio_choices))
        self.audio_dropdown.set_selected(0)
        self.audio_hint.set_text(f'{len(self.audio_streams)} Tonspur(en) für ausgewählten Titel erkannt.' if self.audio_streams else 'Keine Tonspuren für diesen Titel erkannt.')
        self.subtitle_streams = track.get('subtitles', [])
        choices = ['Aus – keine Untertitel'] + [item['label'] for item in self.subtitle_streams]
        self.subtitle_dropdown.set_model(Gtk.StringList.new(choices))
        self.subtitle_dropdown.set_selected(0)
        self.subtitle_hint.set_text(f'{len(self.subtitle_streams)} Untertitelspur(en) für ausgewählten Titel erkannt. Untertitel sind standardmäßig ausgeschaltet.' if self.subtitle_streams else 'Keine Untertitelspuren für diesen Titel erkannt.')

    def _track_selected(self, listbox, row):
        if row is None:
            return
        index = row.get_index()
        if 0 <= index < len(self.track_rows):
            self._populate_stream_choices(self.track_rows[index])
            self.status_label.set_text(f"Ausgewählt: {self.track_rows[index]['title']} · {self.track_rows[index]['duration']}. Beim Rippen wird nur dieser Titel verwendet.")

    def choose_folder(self, *_):
        dialog = Gtk.FileDialog.new()
        dialog.set_title('DVD- oder Blu-ray-Ordner auswählen')
        dialog.select_folder(self.window, None, self.folder_selected)

    def folder_selected(self, dialog, result):
        try:
            f = dialog.select_folder_finish(result)
            self.source_path = f.get_path()
            self.source_label.set_text(self.source_path)
            self.status_label.set_text('Quellordner ausgewählt. Klicke auf „Disc einlesen“, um die Analyse zu starten.')
        except Exception:
            pass

    def choose_output(self, *_):
        dialog = Gtk.FileDialog.new(); dialog.set_title('Zielordner auswählen')
        dialog.select_folder(self.window, None, self.output_selected)

    def output_selected(self, dialog, result):
        try:
            f = dialog.select_folder_finish(result)
            self.output_entry.set_text(f.get_path())
        except Exception:
            pass

    def cancel_rip(self, *_):
        # Stop the visible timer immediately. The worker owns process cleanup;
        # the GUI must not keep counting while cancellation is underway.
        self.cancel_requested = True
        if self.rip_timer_source:
            GLib.source_remove(self.rip_timer_source)
            self.rip_timer_source = 0
        self.rip_started_at = None
        self.elapsed_label.set_text(translated('Abbruch angefordert …', self.language))
        self.status_label.set_text('Abbruch läuft – Video- und Hilfsprozesse werden beendet …')
        proc = self.current_process
        if proc is not None and proc.poll() is None:
            def stop_process_tree(target):
                try:
                    # Every spawned media process starts its own session, so this
                    # also stops children that might otherwise keep pipes open.
                    os.killpg(target.pid, signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    try:
                        target.terminate()
                    except OSError:
                        pass
                try:
                    target.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(target.pid, signal.SIGKILL)
                    except (OSError, ProcessLookupError):
                        try:
                            target.kill()
                        except OSError:
                            pass
                except (OSError, ProcessLookupError):
                    pass
            threading.Thread(target=stop_process_tree, args=(proc,), daemon=True).start()

    def start_rip(self, *_):
        # Full DVD rips use FFmpeg's dvdvideo demuxer and the selected full title.
        self._launch_encoding(test_clip=False, test_pipeline=False)

    def start_test_rip(self, *_):
        # Use the same FFmpeg DVD/Blu-ray demuxing, stream mapping, and subtitle
        # handling as the full rip.
        self._launch_encoding(test_clip=True, test_pipeline=False)

    def _launch_encoding(self, test_clip=False, test_pipeline=False):
        if not self.track_rows:
            self.status_label.set_text('Bitte zuerst eine DVD oder Blu-ray einlesen.')
            return
        if not shutil_which('ffmpeg'):
            self.status_label.set_text('FFmpeg fehlt. Bitte das Paket ffmpeg installieren.')
            return
        selected_row = self.track_list.get_selected_row()
        selected_index = selected_row.get_index() if selected_row is not None else 0
        selected_index = max(0, min(selected_index, len(self.track_rows) - 1))
        track = self.track_rows[selected_index]
        source = track.get('input_path') or self.analysis_source or self.source_path
        if not source:
            self.status_label.set_text('Keine gültige Quelle für die Umwandlung gefunden.')
            return
        is_bluray_source = source.startswith('bluray:') or track.get('details', '').startswith('Blu-ray')
        # Both full DVD rips and one-minute previews use FFmpeg's dvdvideo demuxer.
        outdir = os.path.expanduser(self.output_entry.get_text().strip() or str(Path.home() / 'Videos'))
        try:
            os.makedirs(outdir, exist_ok=True)
        except OSError as exc:
            self.status_label.set_text(f'Zielordner kann nicht angelegt werden: {exc}')
            return
        fmt_items = ['mp4', 'mkv', 'avi']
        fmt = fmt_items[self.format_dropdown.get_selected()] if self.format_dropdown.get_selected() < len(fmt_items) else 'mp4'
        quality = self.quality_dropdown.get_selected()
        normalize_audio = bool(self.normalize_audio_check.get_active())
        if quality == 0:
            video_args = ['-c:v', 'libx264', '-preset', 'slow', '-crf', '19']
        elif quality == 1:
            video_args = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '23']
        elif quality == 2:
            video_args = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '28']
        else:
            video_args = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18']
        audio_items = track.get('audio', [])
        audio_pos = self.audio_dropdown.get_selected()
        audio_item = audio_items[audio_pos] if audio_pos < len(audio_items) else None
        subtitle_items = track.get('subtitles', [])
        sub_pos = self.subtitle_dropdown.get_selected()
        # Dropdown index 0 is the explicit 'no subtitles' choice; real subtitle
        # tracks begin at dropdown index 1.
        subtitle_item = subtitle_items[sub_pos - 1] if 0 < sub_pos <= len(subtitle_items) else None
        dvd_subtitle_global_index = None
        # Resolve the selected DVD subtitle using FFmpeg's own stream metadata.
        # The lsdvd stream ID (0x20, 0x21, ...) is not consistently preserved as
        # the FFmpeg dvdvideo stream ID, which can burn a different language.
        if (track.get('dvd_title') and not is_bluray_source and subtitle_item
                and fmt == 'mp4'):
            try:
                ff_subs = probe_ffmpeg_dvd_subtitle_streams(source, track['dvd_title'])
                wanted_language = normalize_language_code(subtitle_item.get('language', ''))
                matches = [item for item in ff_subs if wanted_language and item.get('language') == wanted_language]
                if len(matches) == 1:
                    dvd_subtitle_global_index = matches[0].get('index')
                elif len(matches) > 1:
                    # Preserve the selected occurrence among tracks of the same
                    # language rather than silently choosing the first one.
                    same_lang_before = sum(1 for item in subtitle_items[:sub_pos - 1]
                                           if normalize_language_code(item.get('language', '')) == wanted_language)
                    if same_lang_before < len(matches):
                        dvd_subtitle_global_index = matches[same_lang_before].get('index')
                if dvd_subtitle_global_index is None:
                    self.status_label.set_text(
                        f'FFmpeg konnte die gewählte Untertitelsprache ({subtitle_item.get("language", "unbekannt")}) nicht eindeutig zuordnen. Bitte DVD erneut einlesen; es werden keine falschen Untertitel eingebrannt.'
                    )
                    return
            except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
                self.status_label.set_text(f'DVD-Untertitel konnten nicht sicher zugeordnet werden: {exc}')
                return
        # Blu-ray input is an FFmpeg bluray: URL. For a full DVD rip, explicitly
        # select FFmpeg's dvdvideo demuxer before passing its title option. Without
        # '-f dvdvideo', FFmpeg treats '-title' as an unknown generic option and
        # fails with "Option not found"; DVD processing stays on FFmpeg.
        # The test clip follows the terminal command pattern confirmed on the
        # user's Raspberry Pi, but honors the selected audio language. Use the
        # audio-relative stream index (0:a:N), not ffprobe's global stream ID,
        # because those indexes can differ between probing and FFmpeg demuxing.
        cmd = ['ffmpeg', '-hide_banner', '-nostats', '-stats_period', '0.5', '-progress', 'pipe:1', '-y']
        duration = float(track.get('duration_seconds') or 0)
        if test_clip:
            if duration <= 60:
                self.status_label.set_text('Der erkannte Titel ist höchstens 60 Sekunden lang; Testclip nicht möglich.')
                return
            seek_seconds = max(0, int(duration / 2 - 30))
            cmd += ['-ss', str(seek_seconds)]
        if source.startswith('bluray:'):
            input_arg = source
        elif track.get('details', '').startswith('Blu-ray'):
            input_arg = source if source.startswith('bluray:') else 'bluray:' + source
        else:
            input_arg = source
        if track.get('dvd_title') and not is_bluray_source:
            cmd += ['-f', 'dvdvideo', '-title', str(track['dvd_title'])]
        # For Blu-ray, the selected title is a specific MPLS playlist. Apply
        # that playlist to the FFmpeg input as well as during probing; otherwise
        # FFmpeg silently opens its default/main playlist and subtitle indexes
        # can refer to different tracks than the ones selected in the UI.
        if is_bluray_source and track.get('bluray_playlist'):
            cmd += ['-playlist', str(track['bluray_playlist'])]
        cmd += ['-i', input_arg]
        if test_clip:
            cmd += ['-t', '60']
        bluray_selected_subtitle = bool(is_bluray_source and subtitle_item)
        # Blu-ray PGS subtitles are bitmap streams. For MP4, burn the selected
        # PGS stream into the video frames with FFmpeg's overlay filter. This
        # keeps the requested MP4 container and does not depend on OCR tools.
        # For MKV, keep the PGS subtitle as a selectable separate stream.
        burn_bluray_subtitle = bool(bluray_selected_subtitle and (fmt in ('mp4', 'avi') or test_pipeline))
        # DVD subpicture tracks are bitmap subtitles too. When FFmpeg's dvdvideo
        # demuxer exposes them, burn the selected subtitle stream directly into
        # the video frames instead of trying to mux DVD-SPU into MP4 as mov_text.
        dvd_selected_subtitle = bool(track.get('dvd_title') and not is_bluray_source and subtitle_item)
        burn_dvd_subtitle = bool(dvd_selected_subtitle and fmt == 'mp4')
        dvd_subtitle_relative_index = max(0, sub_pos - 1)
        if test_pipeline:
            audio_map = f'0:a:{audio_pos}?' if audio_item else '0:a:0?'
            if burn_bluray_subtitle:
                sub_stream_index = int(subtitle_item.get('index', 0))
                cmd += ['-filter_complex', f'[0:v:0][0:{sub_stream_index}]overlay[vout]', '-map', '[vout]', '-map', audio_map, '-sn']
            else:
                cmd += ['-map', '0:v:0', '-map', audio_map]
                if bluray_selected_subtitle:
                    sub_stream_index = int(subtitle_item.get('index', 0))
                    cmd += ['-map', f'0:{sub_stream_index}', '-c:s', 'copy']
                else:
                    cmd += ['-sn']
            cmd += video_args + ['-c:a', ('libmp3lame' if fmt == 'avi' else ('aac' if fmt == 'mp4' or normalize_audio else 'copy'))]
            if normalize_audio:
                cmd += ['-af', 'loudnorm=I=-16:TP=-1.5:LRA=11']
            if subtitle_item and fmt == 'mp4' and not bluray_selected_subtitle and not burn_dvd_subtitle:
                cmd += ['-c:s', 'mov_text']
            elif subtitle_item and not burn_bluray_subtitle and not burn_dvd_subtitle:
                cmd += ['-c:s', 'copy']
            if fmt == 'mp4':
                cmd += ['-movflags', '+faststart']
        else:
            if burn_bluray_subtitle or burn_dvd_subtitle:
                if burn_bluray_subtitle:
                    sub_stream_spec = f"0:{int(subtitle_item.get('index', 0))}"
                else:
                    # Use the global FFmpeg stream index resolved by language
                    # above, not lsdvd's SPU ID or its list position.
                    sub_stream_spec = f'0:{int(dvd_subtitle_global_index)}'
                cmd += ['-filter_complex', f'[0:v:0][{sub_stream_spec}]overlay[vout]', '-map', '[vout]']
                if audio_item:
                    if track.get('dvd_title') and not is_bluray_source:
                        # lsdvd exposes DVD audio stream IDs such as 0x80/0x81,
                        # which are NOT FFmpeg global stream indexes. The dvdvideo
                        # demuxer orders audio streams as 0:a:0, 0:a:1, ... .
                        # Map by the selected audio's position in the detected list
                        # so selecting German does not accidentally fall back to English.
                        cmd += ['-map', f'0:a:{audio_pos}']
                    else:
                        try:
                            cmd += ['-map', f"0:{int(audio_item['index'])}"]
                        except (ValueError, TypeError):
                            cmd += ['-map', '0:a:0?']
                else:
                    cmd += ['-map', '0:a:0?']
                cmd += ['-sn']
            else:
                cmd += ['-map', '0:v:0']
                if subtitle_item and bluray_selected_subtitle:
                    sub_stream_index = int(subtitle_item.get('index', 0))
                    cmd += ['-map', f'0:{sub_stream_index}']
                if audio_item:
                    if track.get('dvd_title') and not is_bluray_source:
                        # DVD stream IDs (0x80, 0x81, ...) are not FFmpeg global
                        # stream indexes. Use the selected audio stream's ordinal
                        # within FFmpeg's dvdvideo audio list instead.
                        cmd += ['-map', f'0:a:{audio_pos}']
                    else:
                        try:
                            cmd += ['-map', f"0:{int(audio_item['index'])}"]
                        except (ValueError, TypeError):
                            cmd += ['-map', '0:a:0?']
                else:
                    cmd += ['-map', '0:a:0?']
            if not burn_bluray_subtitle and not burn_dvd_subtitle and subtitle_item and not bluray_selected_subtitle:
                try:
                    cmd += ['-map', f"0:{int(subtitle_item['index'])}"]
                except (ValueError, TypeError):
                    pass
            cmd += video_args + ['-c:a', ('libmp3lame' if fmt == 'avi' else ('aac' if fmt == 'mp4' or normalize_audio else 'copy'))]
            if normalize_audio:
                cmd += ['-af', 'loudnorm=I=-16:TP=-1.5:LRA=11']
            if subtitle_item and fmt == 'mp4' and not bluray_selected_subtitle and not burn_dvd_subtitle:
                cmd += ['-c:s', 'mov_text']
            elif subtitle_item and not burn_bluray_subtitle and not burn_dvd_subtitle:
                cmd += ['-c:s', 'copy']
        safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', track.get('title', 'Video')).strip('_') or 'Video'
        suffix = '_TEST_1_MINUTE' if test_clip else ''
        output_fmt = fmt
        output = os.path.join(outdir, f'{safe_name}{suffix}.{output_fmt}')
        cmd.append(output)
        self.cancel_requested = False
        self.current_process = None
        self.start_btn.set_sensitive(False); self.test_btn.set_sensitive(False); self.abort_btn.set_sensitive(True)
        self.rip_started_at = __import__('time').monotonic()
        self.elapsed_label.set_text(translated('Laufzeit:', self.language) + ' 00:00:00')
        if self.rip_timer_source:
            GLib.source_remove(self.rip_timer_source)
        self.rip_timer_source = GLib.timeout_add_seconds(1, self._update_elapsed_timer)
        self.progress.set_fraction(0); self.progress.set_text('0 %')
        if burn_bluray_subtitle:
            self.status_label.set_text(f'Blu-ray-PGS wird direkt ins {fmt.upper()}-Bild eingebrannt …')
        elif burn_dvd_subtitle:
            self.status_label.set_text('DVD-Untertitel werden mit FFmpeg direkt ins MP4-Bild eingebrannt …')
        else:
            if test_clip:
                status_text = '1-Minuten-Testclip läuft. FFmpeg verarbeitet den Filmausschnitt …'
            else:
                status_text = 'Rippen läuft. FFmpeg verarbeitet den Film …'
            self.status_label.set_text(status_text)
        # Auto-eject is opt-in after successful full rip OR successful 1-minute test.
        eject_candidate = self.source_path if self.source_path and self.source_path.startswith('/dev/') else self.selected_device()
        eject_device = eject_candidate if self.auto_eject_check.get_active() and eject_candidate and eject_candidate.startswith('/dev/') else None
        worker_mode = {'is_dvd_full_rip': bool(track.get('dvd_title') and not is_bluray_source and not test_clip), 'limit_to_minute': bool(test_clip), 'auto_eject_device': eject_device, 'duration_seconds': duration, 'normalize_audio': normalize_audio}
        self.rip_thread = threading.Thread(target=self._encoding_worker, args=(cmd, output, worker_mode), daemon=True)
        self.rip_thread.start()

    def _encoding_worker(self, cmd, output, worker_mode=None):
        worker_mode = worker_mode or {}
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='replace', bufsize=1, universal_newlines=True, start_new_session=True)
            self.current_process = process
            stderr_chunks = []
            # FFmpeg emits progress records on stdout when -progress pipe:1 is set.
            # Drain stderr concurrently so a full pipe cannot stall the encoder.
            def drain_stderr():
                try:
                    for err_line in process.stderr:
                        stderr_chunks.append(err_line)
                except (OSError, ValueError):
                    pass
            stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
            stderr_thread.start()
            current_out_time = 0.0
            total_duration = float(worker_mode.get('duration_seconds') or 0)
            progress_values = {}
            for progress_line in process.stdout:
                line = progress_line.strip()
                if '=' not in line:
                    continue
                key, value = line.split('=', 1)
                progress_values[key] = value
                # FFmpeg versions vary in how reliably they populate out_time_ms;
                # prefer out_time (HH:MM:SS.microseconds) and fall back to out_time_us/ms.
                if key == 'out_time':
                    try:
                        hh, mm, ss = value.split(':')
                        current_out_time = max(0.0, int(hh) * 3600 + int(mm) * 60 + float(ss))
                    except (ValueError, TypeError):
                        pass
                elif key in ('out_time_us', 'out_time_ms') and not progress_values.get('out_time'):
                    try:
                        current_out_time = max(0.0, int(value) / 1_000_000.0)
                    except (ValueError, TypeError):
                        pass
                if key == 'progress':
                    if value.strip().lower() == 'end':
                        # FFmpeg explicitly says it has finished writing the output.
                        # Reflect that immediately; the worker still waits for process exit
                        # and validates the output below before declaring success.
                        GLib.idle_add(self._encoding_progress, 1.0, current_out_time, total_duration)
                    elif total_duration > 0:
                        fraction = min(0.99, current_out_time / total_duration)
                        GLib.idle_add(self._encoding_progress, fraction, current_out_time, total_duration)
                    progress_values.clear()
            process.wait()
            stderr_thread.join(timeout=2)
            stderr = ''.join(stderr_chunks)
            returncode = process.returncode
            if self.cancel_requested:
                message = 'Rippen wurde abgebrochen. Eine unvollständige Ausgabedatei kann vorhanden sein.'
                fraction = 0.0
            elif returncode == 0:
                # Do not report success solely from FFmpeg's return code: confirm that
                # the resulting container can be read and has a video stream and duration.
                try:
                    if not os.path.isfile(output) or os.path.getsize(output) < 1024:
                        raise RuntimeError('Die Ausgabedatei fehlt oder ist zu klein.')
                    if shutil_which('ffprobe'):
                        check = subprocess.run(
                            ['ffprobe', '-v', 'error', '-show_entries',
                             'format=duration:stream=codec_type', '-of', 'json', output],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='replace',
                            timeout=30, check=False)
                        if check.returncode != 0:
                            raise RuntimeError('FFprobe kann die fertige Datei nicht lesen.')
                        data = json.loads(check.stdout or '{}')
                        types = [item.get('codec_type') for item in data.get('streams', [])]
                        duration_value = float((data.get('format') or {}).get('duration') or 0)
                        if 'video' not in types or duration_value < 5:
                            raise RuntimeError('Video-Stream oder plausible Laufzeit fehlt.')
                        expected_duration = float(worker_mode.get('duration_seconds') or 0)
                        if worker_mode.get('is_dvd_full_rip') and expected_duration > 0 and duration_value < expected_duration * 0.90:
                            raise RuntimeError(
                                f'Unvollständiger DVD-Rip: erkannt {expected_duration / 60:.1f} Min., '
                                f'Datei enthält nur {duration_value / 60:.1f} Min. '
                                '(mindestens 90 % der erkannten Titellaufzeit erforderlich). '
                                'Die Datei wird nicht als „Fertig“ gewertet.'
                            )
                except (OSError, RuntimeError, ValueError, TypeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                    message = f'Encoding beendet, aber Dateiprüfung fehlgeschlagen: {exc}'
                    fraction = 0.0
                    GLib.idle_add(self._set_rip_stage_status, message)
                    raise RuntimeError(message)
                message = f'Fertig: {output}'
                eject_device = worker_mode.get('auto_eject_device')
                if eject_device and eject_device.startswith('/dev/') and shutil_which('eject'):
                    try:
                        eject_result = subprocess.run([shutil_which('eject'), eject_device], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='replace', timeout=15, check=False)
                        if eject_result.returncode == 0:
                            message += f' · Disc in {eject_device} ausgeworfen.'
                        else:
                            detail = (eject_result.stderr or eject_result.stdout or 'Auswerfen nicht möglich').strip().splitlines()[-1]
                            message += f' · Rippen erfolgreich, aber Auswerfen fehlgeschlagen: {detail}'
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        message += f' · Rippen erfolgreich, aber Auswerfen fehlgeschlagen: {exc}'
                fraction = 1.0
            else:
                # Some FFmpeg builds can return a non-zero status after the MP4
                # muxer has already finalized a complete, playable output (for
                # example, a late conversion/filter warning). Never call that a
                # success merely because a file exists: validate it with ffprobe
                # and require a video stream plus a plausible positive duration.
                validated = False
                validation_detail = ''
                try:
                    if os.path.isfile(output) and os.path.getsize(output) >= 1024 and shutil_which('ffprobe'):
                        probe = subprocess.run(
                            ['ffprobe', '-v', 'error', '-show_entries',
                             'format=duration:stream=codec_type', '-of', 'json', output],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, errors='replace', timeout=30, check=False)
                        if probe.returncode == 0 and probe.stdout.strip():
                            probe_data = json.loads(probe.stdout)
                            stream_types = [item.get('codec_type') for item in probe_data.get('streams', [])]
                            duration_value = float((probe_data.get('format') or {}).get('duration') or 0)
                            expected_duration = float(worker_mode.get('duration_seconds') or 0)
                            # Test clips are intentionally short. A full DVD rip must
                            # closely match lsdvd's detected title duration; otherwise
                            # a truncated file must never be reported as successful.
                            duration_ok = duration_value >= 5
                            if worker_mode.get('is_dvd_full_rip') and expected_duration > 0:
                                duration_ok = duration_ok and duration_value >= expected_duration * 0.90
                                if not duration_ok:
                                    validation_detail = (
                                        f'Unvollständiger DVD-Rip: erkannt {expected_duration / 60:.1f} Min., '
                                        f'Datei enthält {duration_value / 60:.1f} Min. (erforderlich: mindestens 90 %).'
                                    )
                            validated = 'video' in stream_types and duration_ok
                            if not validated and not validation_detail:
                                validation_detail = 'Die Ausgabedatei enthält keinen gültigen Videostream oder keine plausible Laufzeit.'
                        else:
                            validation_detail = (probe.stderr or 'FFprobe konnte die Datei nicht prüfen.').strip().splitlines()[-1]
                    else:
                        validation_detail = 'Keine ausreichend große Ausgabedatei oder ffprobe fehlt.'
                except (OSError, ValueError, TypeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                    validation_detail = f'Prüfung der Ausgabedatei fehlgeschlagen: {exc}'
                if validated:
                    tail = (stderr or 'FFmpeg meldete einen Fehler nach dem Schreiben der Ausgabedatei.').strip().splitlines()
                    detail = tail[-1] if tail else 'FFmpeg meldete einen Fehler nach dem Schreiben der Ausgabedatei.'
                    message = f'Fertig: {output} (Datei durch FFprobe geprüft; FFmpeg meldete nachträglich: {detail})'
                    fraction = 1.0
                else:
                    tail = (stderr or 'Das Video-Werkzeug hat keine Fehlerdetails geliefert.').strip().splitlines()
                    message = 'Encoding fehlgeschlagen: ' + (tail[-1] if tail else 'Unbekannter Fehler')
                    if validation_detail:
                        message += f' · Dateiprüfung: {validation_detail}'
                    fraction = 0.0
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            message = str(exc) if isinstance(exc, RuntimeError) else f'Videoverarbeitung fehlgeschlagen: {exc}'
            fraction = 0.0
        GLib.idle_add(self._encoding_finished, message, fraction)

    def _set_rip_stage_status(self, message):
        self.status_label.set_text(message)
        return GLib.SOURCE_REMOVE

    def _encoding_progress(self, fraction, elapsed, total):
        # Called on the GTK main loop; keep the progress bar moving during encoding.
        self.progress.set_fraction(max(0.0, min(0.99, fraction)))
        pct = int(max(0.0, min(0.99, fraction)) * 100)
        self.progress.set_text(f'{pct} %  ·  {format_duration(elapsed)} / {format_duration(total)}')
        return GLib.SOURCE_REMOVE

    def _update_elapsed_timer(self):
        if self.rip_started_at is None:
            self.rip_timer_source = 0
            return GLib.SOURCE_REMOVE
        elapsed = max(0, int(__import__('time').monotonic() - self.rip_started_at))
        self.elapsed_label.set_text(translated('Laufzeit:', self.language) + f' {format_duration(elapsed)}')
        return GLib.SOURCE_CONTINUE

    def _encoding_finished(self, message, fraction):
        elapsed_text = '00:00:00'
        if self.rip_started_at is not None:
            elapsed_seconds = max(0, int(__import__('time').monotonic() - self.rip_started_at))
            elapsed_text = format_duration(elapsed_seconds)
        if self.rip_timer_source:
            GLib.source_remove(self.rip_timer_source)
            self.rip_timer_source = 0
        self.rip_started_at = None
        self.elapsed_label.set_text(translated('Gesamtdauer:', self.language) + f' {elapsed_text}')
        self.status_label.set_text(message)
        self.progress.set_fraction(fraction)
        self.progress.set_text(translated('Abgeschlossen' if fraction else 'Fehler', self.language))
        self.current_process = None
        self.start_btn.set_sensitive(True); self.test_btn.set_sensitive(True); self.abort_btn.set_sensitive(False)
        return GLib.SOURCE_REMOVE

# GTK display helper avoids requiring an already-created window.
from gi.repository import Gdk
GdkDisplay = Gdk.Display

if __name__ == '__main__':
    app = LunaVideoStudio()
    app.run(None)
