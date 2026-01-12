#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from zoneinfo import ZoneInfo

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QPlainTextEdit, QMessageBox, QMenu
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

TIME_RE = re.compile(r"^\s*(?:[01]\d|2[0-3]):[0-5]\d\s*$")
DATE_RE = re.compile(r"^\s*(\d{1,2})/(\d{1,2})\s*$")

# Γραμμές sport που μπορεί να εμφανιστούν μόνες τους μετά το comp/meta
SPORT_LINE_SET = {
    "Ποδόσφαιρο", "Μπάσκετ", "Τένις", "Βόλεϊ", "Χάντμπολ",
    "Αμερικανικό Ποδόσφαιρο", "American Football", "Εκπομπή"
}

# Χαρτογράφηση "sport" από keywords που βρίσκονται σε match/comp/channel
SPORT_KEYWORDS = [
    ("Τένις", [
        "ATP", "WTA", "United Cup", "Grand Slam", "Challenger", "ITF", "Davis Cup", "Billie Jean King"
    ]),
    ("Βόλεϊ", [
        "Volley", "CEV", "Volleyball", "Challenge Cup", "Champions League", "CEV Cup", "Volley League"
    ]),
    ("Μπάσκετ", [
        "NBA", "Euroleague", "EuroLeague", "Eurocup", "EuroCup",
        "ACB", "GBL", "Basket", "FIBA", "BCL", "Stoiximan GBL", "Lega Basket"
    ]),
    ("Ποδόσφαιρο", [
        "Super League", "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue",
        "FA Cup", "Coppa Italia", "Conference League", "Europa", "Champions League",
        "Eredivisie", "Liga Portugal", "Cup", "Κύπελλο", "Λιγκ Καπ", "League Cup",
        "Saudi", "Roshn", "Cyprus League"
    ]),
    ("Αμερικανικό Ποδόσφαιρο", [
        "NFL", "American Football", "Steelers", "Texans", "Playoffs"
    ]),
    ("Χάντμπολ", [
        "Χάντμπολ", "Handball", "Ευρωπαϊκό Πρωτάθλημα Ανδρών"
    ]),
    ("Εκπομπή", [
        "Εκπομπή", "Show", "Pre Game", "Post Game", "Sportshow", "Playmakers",
        "Monday Football Club", "Matchday Live", "Minute by Minute", "OnlyFacts",
        "BIG 4", "Box2Box", "Game Night", "Give And Go", "MIND Game", "Pelota",
        "Pick n", "On Fire"
    ]),
]

@dataclass
class Event:
    date_key: str          # YYYY-MM-DD
    time: str              # HH:MM
    channel: str
    match: str
    comp: str
    sport: str

def athens_now() -> datetime:
    return datetime.now(ZoneInfo("Europe/Athens"))

def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())

def infer_sport(channel: str, match: str, comp: str) -> str:
    hay = f"{channel} {match} {comp}"
    for sport, keys in SPORT_KEYWORDS:
        for k in keys:
            if k.lower() in hay.lower():
                return sport
    return ""  # όπως ζήτησες: αν δεν βρίσκει, αφήνει κενό (μπορούμε να το κάνουμε "Άλλο" αν θες αργότερα)

def parse_input(text: str) -> Tuple[Dict[str, List[Event]], List[str]]:
    """
    Επιστρέφει:
      - schedule: dict[YYYY-MM-DD] -> list[Event]
      - warnings: λίστα με προειδοποιήσεις (αν βρήκε κάτι περίεργο)
    """
    lines_raw = text.splitlines()
    # κρατάμε και κενές γραμμές για σωστό peek, αλλά δουλεύουμε με index
    lines = [ln.rstrip("\n") for ln in lines_raw]

    warnings: List[str] = []
    schedule: Dict[str, List[Event]] = {}

    base_year = athens_now().year
    last_month = None
    current_date_key: Optional[str] = None

    i = 0
    while i < len(lines):
        ln = lines[i].strip()

        # Άδειες γραμμές -> skip
        if not ln:
            i += 1
            continue

        # Ημερομηνία dd/mm
        mdate = DATE_RE.match(ln)
        if mdate:
            dd = int(mdate.group(1))
            mm = int(mdate.group(2))

            # Heuristic rollover: αν ο μήνας "πέσει" (π.χ. 12 -> 1), προχωράμε έτος +1
            if last_month is not None and mm < last_month:
                base_year += 1
            last_month = mm

            # build date key
            try:
                d = datetime(base_year, mm, dd)
                current_date_key = d.strftime("%Y-%m-%d")
                schedule.setdefault(current_date_key, [])
            except Exception:
                warnings.append(f"Αδυναμία δημιουργίας ημερομηνίας από: {ln}")
                current_date_key = None

            i += 1
            continue

        # Αν δεν έχουμε ημερομηνία ακόμα, δεν μπορούμε να βάλουμε events
        if current_date_key is None:
            # πιθανό header ημέρας, το αγνοούμε
            i += 1
            continue

        # Event start: ώρα
        if TIME_RE.match(ln):
            time_str = normalize_spaces(ln)

            def next_nonempty(idx: int) -> Optional[Tuple[int, str]]:
                j = idx
                while j < len(lines):
                    s = lines[j].strip()
                    if s:
                        return j, s
                    j += 1
                return None

            n1 = next_nonempty(i + 1)
            n2 = next_nonempty((n1[0] + 1) if n1 else i + 1)
            n3 = next_nonempty((n2[0] + 1) if n2 else i + 1)

            if not (n1 and n2 and n3):
                warnings.append(f"Λείπουν γραμμές μετά την ώρα {time_str} στη μέρα {current_date_key}")
                i += 1
                continue

            channel = normalize_spaces(n1[1])
            match = normalize_spaces(n2[1])
            comp = normalize_spaces(n3[1])

            # peek για sport line (προαιρετικό)
            sport = ""
            n4 = next_nonempty(n3[0] + 1)
            if n4:
                maybe_sport = normalize_spaces(n4[1])
                # Αν η επόμενη γραμμή είναι καθαρό sport, την καταναλώνουμε
                if maybe_sport in SPORT_LINE_SET and not TIME_RE.match(maybe_sport) and not DATE_RE.match(maybe_sport):
                    sport = maybe_sport
                    i = n4[0] + 1
                else:
                    sport = infer_sport(channel, match, comp)
                    i = n3[0] + 1
            else:
                sport = infer_sport(channel, match, comp)
                i = n3[0] + 1

            ev = Event(
                date_key=current_date_key,
                time=time_str,
                channel=channel,
                match=match,
                comp=comp,
                sport=sport
            )
            schedule.setdefault(current_date_key, []).append(ev)
            continue

        # Οτιδήποτε άλλο (headers ημέρας κ.λπ.)
        i += 1

    # sort events per day by time
    def time_key(t: str) -> Tuple[int, int]:
        hh, mm = t.split(":")
        return int(hh), int(mm)

    for dk in schedule:
        schedule[dk].sort(key=lambda e: time_key(e.time))

    return schedule, warnings

def build_schedule_js_obj(schedule: Dict[str, List[Event]]) -> str:
    out: Dict[str, List[Dict[str, str]]] = {}
    for date_key, evs in schedule.items():
        out[date_key] = [
            {
                "time": e.time,
                "channel": e.channel,
                "match": e.match,
                "comp": e.comp,
                "sport": e.sport
            }
            for e in evs
        ]
    return json.dumps(out, ensure_ascii=False, indent=2)

def build_full_php_shortcode(schedule_json: str) -> str:
    # Ενσωματώνουμε το JSON σαν JS object (είναι ήδη σωστό json)
    return f"""<?php
function sportaki_tv_week_shortcode() {{
    ob_start();
    ?>
<div id="sportaki-tv-week"></div>

<style>
  #sportaki-tv-week .stw-widget{{
    background:#0b0b10;
    border-radius:12px;
    padding:16px 18px;
    font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
    color:#f5f7ff;
    box-shadow:0 4px 18px rgba(0,0,0,.35);
    border:1px solid #1f2538;
  }}
  #sportaki-tv-week .stw-header{{
    font-size:16px;
    font-weight:700;
    letter-spacing:.03em;
    text-transform:uppercase;
    margin-bottom:4px;
    color:#7fc3ff;
  }}
  #sportaki-tv-week .stw-sub{{
    font-size:12px;
    color:#9ca4ba;
    margin-bottom:10px;
  }}
  #sportaki-tv-week .stw-tabs{{
    display:flex;
    flex-wrap:wrap;
    gap:6px;
    margin-bottom:10px;
  }}
  #sportaki-tv-week .stw-tab{{
    border-radius:20px;
    border:1px solid #28324a;
    background:#111725;
    padding:4px 10px;
    font-size:11px;
    cursor:pointer;
    color:#c3d4ff;
  }}
  #sportaki-tv-week .stw-tab-active{{
    background:#227bc3;
    border-color:#4fb4ff;
    color:#ffffff;
    font-weight:600;
  }}
  #sportaki-tv-week .stw-day-title{{
    font-size:13px;
    font-weight:700;
    margin-bottom:6px;
    color:#e2e7ff;
  }}
  #sportaki-tv-week .stw-list{{
    list-style:none;
    margin:0;
    padding:0;
  }}
  #sportaki-tv-week .stw-item{{
    display:flex;
    gap:8px;
    padding:6px 4px;
    border-radius:8px;
    border:1px solid rgba(255,255,255,.03);
    margin-bottom:4px;
    background:linear-gradient(135deg,rgba(34,123,195,.25),rgba(15,24,43,.9));
  }}
  #sportaki-tv-week .stw-item:nth-child(even){{
    background:linear-gradient(135deg,rgba(15,24,43,.9),rgba(34,123,195,.18));
  }}
  #sportaki-tv-week .stw-time{{
    font-size:11px;
    font-weight:700;
    min-width:44px;
    text-align:center;
    padding:3px 4px;
    border-radius:6px;
    background:rgba(0,0,0,.35);
  }}
  #sportaki-tv-week .stw-main{{
    flex:1;
    min-width:0;
  }}
  #sportaki-tv-week .stw-match{{
    font-size:12px;
    font-weight:600;
    margin-bottom:2px;
  }}
  #sportaki-tv-week .stw-meta{{
    font-size:11px;
    color:#9ca4ba;
    display:flex;
    flex-wrap:wrap;
    gap:6px;
  }}
  #sportaki-tv-week .stw-channel{{
    font-weight:600;
  }}
  #sportaki-tv-week .stw-empty{{
    font-size:12px;
    color:#9ca4ba;
    padding:4px 2px;
  }}
</style>

<script>
document.addEventListener('DOMContentLoaded', function(){{

  // ---- ΝΕΟ ΠΡΟΓΡΑΜΜΑ ----
  var schedule = {schedule_json};

  function getAthensDate(){{
    var now = new Date();
    try{{
      var athensStr = now.toLocaleString("en-US",{{timeZone:"Europe/Athens"}});
      return new Date(athensStr);
    }}catch(e){{
      return now;
    }}
  }}

  function renderWeekWidget(){{
    var container = document.getElementById("sportaki-tv-week");
    if (!container) return;

    var today = getAthensDate();
    var todayKey = today.toISOString().slice(0,10);

    var days = Object.keys(schedule).sort();

    var html = '<div class="stw-widget">';
    html += '<div class="stw-header">📺 ΤΙ ΔΕΙΧΝΕΙ Η ΤΗΛΕΟΡΑΣΗ ΑΥΤΗ ΤΗΝ ΕΒΔΟΜΑΔΑ</div>';
    html += '<div class="stw-sub">Δες συγκεντρωμένα, ανά μέρα, όλα τα μεγάλα παιχνίδια σε COSMOTE TV, Novasports, ΕΡΤ και Sport24.</div>';

    html += '<div class="stw-tabs">';
    days.forEach(function(key){{
      var d = new Date(key + "T00:00:00");
      var labelDay = d.toLocaleDateString("el-GR",{{weekday:"short"}});
      var labelDate = d.toLocaleDateString("el-GR",{{day:"2-digit",month:"2-digit"}});
      var active = (key === todayKey) ? ' stw-tab-active' : '';
      html += '<button class="stw-tab'+active+'" data-day="'+key+'">'+labelDay+' '+labelDate+'</button>';
    }});
    html += '</div>';

    html += '<div class="stw-body"></div>';
    html += '</div>';

    container.innerHTML = html;

    function renderDay(key){{
      var body = container.querySelector(".stw-body");
      var daySched = schedule[key] || [];
      var d = new Date(key + "T00:00:00");
      var heading = d.toLocaleDateString("el-GR",{{weekday:"long",day:"2-digit",month:"2-digit"}});

      var inner = '<div class="stw-day-title">'+heading+'</div>';

      if (!daySched.length){{
        inner += '<div class="stw-empty">Δεν υπάρχουν καταχωρημένες μεταδόσεις για αυτή την ημέρα.</div>';
      }}else{{
        inner += '<ul class="stw-list">';
        daySched.forEach(function(item){{
          inner += '<li class="stw-item">';
          inner +=   '<div class="stw-time">'+item.time+'</div>';
          inner +=   '<div class="stw-main">';
          inner +=     '<div class="stw-match">'+item.match+'</div>';
          inner +=     '<div class="stw-meta">';
          inner +=       '<span class="stw-channel">'+item.channel+'</span>';
          if(item.comp){{ inner += '<span>• '+item.comp+'</span>'; }}
          inner +=     '</div>';
          inner +=   '</div>';
          inner += '</li>';
        }});
        inner += '</ul>';
      }}
      body.innerHTML = inner;
    }}

    var tabs = container.querySelectorAll(".stw-tab");
    tabs.forEach(function(btn){{
      btn.addEventListener("click", function(){{
        tabs.forEach(function(b){{ b.classList.remove("stw-tab-active"); }});
        this.classList.add("stw-tab-active");
        var key = this.getAttribute("data-day");
        renderDay(key);
      }});
    }});

    if (schedule[todayKey]){{
      renderDay(todayKey);
    }}else if (days.length){{
      renderDay(days[0]);
    }}
  }}

  renderWeekWidget();
}});
</script>
    <?php
    return ob_get_clean();
}}
add_shortcode('sportaki_tv_week', 'sportaki_tv_week_shortcode');
"""
# ---------------- GUI ----------------

class ContextMenuPlainText(QPlainTextEdit):
    """QPlainTextEdit με δεξί κλικ μενού Copy/Paste/Cut/Select All."""
    def __init__(self, read_only: bool = False):
        super().__init__()
        self.setReadOnly(read_only)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_menu)

    def show_menu(self, pos):
        menu = QMenu(self)

        act_cut = QAction("Αποκοπή", self)
        act_copy = QAction("Αντιγραφή", self)
        act_paste = QAction("Επικόλληση", self)
        act_select_all = QAction("Επιλογή όλων", self)

        act_cut.triggered.connect(self.cut)
        act_copy.triggered.connect(self.copy)
        act_paste.triggered.connect(self.paste)
        act_select_all.triggered.connect(self.selectAll)

        # Enable/disable
        has_sel = self.textCursor().hasSelection()
        act_copy.setEnabled(has_sel)
        act_cut.setEnabled(has_sel and (not self.isReadOnly()))
        act_paste.setEnabled(not self.isReadOnly())

        menu.addAction(act_cut)
        menu.addAction(act_copy)
        menu.addAction(act_paste)
        menu.addSeparator()
        menu.addAction(act_select_all)

        menu.exec(self.mapToGlobal(pos))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sportaki TV Week Converter (Input → PHP Shortcode)")
        self.resize(1100, 700)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        title = QLabel("📺 Converter: TV πρόγραμμα → έτοιμο PHP shortcode [sportaki_tv_week]")
        title.setStyleSheet("font-size:16px; font-weight:700;")
        layout.addWidget(title)

        # Input
        layout.addWidget(QLabel("Input (επικόλλησε εδώ το πρόγραμμα):"))
        self.input_box = ContextMenuPlainText(read_only=False)
        self.input_box.setPlaceholderText("Κάνε paste εδώ το πρόγραμμα της τηλεόρασης…")
        self.input_box.setMinimumHeight(220)
        layout.addWidget(self.input_box)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_convert = QPushButton("🔁 Μετατροπή")
        self.btn_clear = QPushButton("🧹 Καθάρισμα")
        self.btn_copy = QPushButton("📋 Αντιγραφή όλου του Output")
        btn_row.addWidget(self.btn_convert)
        btn_row.addWidget(self.btn_clear)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_copy)
        layout.addLayout(btn_row)

        # Output
        layout.addWidget(QLabel("Output (έτοιμο shortcode — read-only):"))
        self.output_box = ContextMenuPlainText(read_only=True)
        self.output_box.setMinimumHeight(260)
        layout.addWidget(self.output_box)

        self.btn_convert.clicked.connect(self.convert)
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_copy.clicked.connect(self.copy_output)

    def convert(self):
        text = self.input_box.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Κενό input", "Βάλε πρώτα το πρόγραμμα στο Input.")
            return

        schedule, warnings = parse_input(text)
        if not schedule:
            QMessageBox.warning(self, "Δεν βρέθηκαν events", "Δεν μπόρεσα να εντοπίσω ημέρες/ώρες με το format που περιμένω.")
            return

        schedule_json = build_schedule_js_obj(schedule)
        php = build_full_php_shortcode(schedule_json)

        self.output_box.setPlainText(php)

        if warnings:
            QMessageBox.information(
                self,
                "ΟΚ (με προειδοποιήσεις)",
                "Έγινε η μετατροπή, αλλά βρήκα μερικά σημεία που ίσως θέλουν έλεγχο:\n\n- " + "\n- ".join(warnings[:12]) +
                ("\n\n(Εμφανίζω μέχρι 12 προειδοποιήσεις.)" if len(warnings) > 12 else "")
            )

    def clear_all(self):
        self.input_box.clear()
        self.output_box.clear()

    def copy_output(self):
        out = self.output_box.toPlainText()
        if not out.strip():
            QMessageBox.warning(self, "Κενό output", "Δεν υπάρχει output για αντιγραφή. Πάτα πρώτα Μετατροπή.")
            return
        QApplication.clipboard().setText(out)
        QMessageBox.information(self, "Αντιγράφηκε", "✅ Αντιγράφηκε όλο το output στο clipboard.")

def main():
    app = QApplication([])
    w = MainWindow()
    w.show()
    app.exec()

if __name__ == "__main__":
    main()

