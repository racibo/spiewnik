import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
import random
import re
from collections import Counter

# ─────────────────────────────────────────────
#  POŁĄCZENIE Z GOOGLE SHEETS
# ─────────────────────────────────────────────

def init_gsheet():
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
            client = gspread.authorize(creds)
            return client.open_by_key("1RG82ZtUZfNsOjXI7xHKDnwbnDUl2SwE5oDLMNJNYdkw").worksheet("Songs")
        else:
            st.error("Brak konfiguracji 'gcp_service_account' w secrets.toml")
            return None
    except Exception as e:
        st.error(f"Błąd połączenia z Google Sheets: {e}")
        return None

ws = init_gsheet()

# ─────────────────────────────────────────────
#  LOGIKA BIZNESOWA
# ─────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def load_songs_cached():
    """Ładuje piosenki z cache'em 2 minuty — szybkie przełączanie bez callów API."""
    if not ws:
        return []
    try:
        rows = ws.get_all_values()
        if not rows or len(rows) < 2:
            return []
        songs = []
        for i, row in enumerate(rows[1:], start=2):
            if len(row) >= 2 and row[0].strip():
                title = row[0].strip()
                lyrics_raw = row[1].strip() if len(row) > 1 else ""
                ratings_sum = int(row[2]) if len(row) > 2 and row[2].isdigit() else 0
                ratings_count = int(row[3]) if len(row) > 3 and row[3].isdigit() else 0
                tags_raw = row[4].strip() if len(row) > 4 else ""
                lyrics = []
                if lyrics_raw.startswith("["):
                    try:
                        for item in json.loads(lyrics_raw):
                            if isinstance(item, dict):
                                chords = item.get("chords", [])
                                if isinstance(chords, str):
                                    chords = chords.split()
                                lyrics.append({"text": item.get("text", "").strip(), "chords": chords})
                    except Exception:
                        lyrics.append({"text": lyrics_raw, "chords": []})
                else:
                    for line in lyrics_raw.split("\n"):
                        if "|" in line:
                            parts = line.split("|", 1)
                            lyrics.append({"text": parts[0].strip(), "chords": parts[1].strip().split() if parts[1].strip() else []})
                        else:
                            lyrics.append({"text": line.strip(), "chords": []})
                songs.append({
                    "title": title,
                    "lyrics": lyrics,
                    "ratings_sum": ratings_sum,
                    "ratings_count": ratings_count,
                    "tags": [t.strip() for t in tags_raw.split(",") if t.strip()],
                    "row": i,
                })
        return songs
    except Exception as e:
        st.error(f"Błąd podczas ładowania piosenek: {e}")
        return []

def reload_songs():
    """Czyści cache i przeładowuje do session_state."""
    load_songs_cached.clear()
    st.session_state.songs = load_songs_cached()

def save_song_to_sheets(row_idx, title, lyrics, ratings_sum, ratings_count, tags):
    if not ws:
        return False
    try:
        lyrics_str = "\n".join([f"{l['text']} | {' '.join(l.get('chords', []))}" for l in lyrics])
        ws.update([[title, lyrics_str, str(ratings_sum), str(ratings_count), ", ".join(tags)]], f"A{row_idx}:E{row_idx}", raw=False)
        return True
    except Exception as e:
        st.error(f"Błąd podczas zapisywania: {e}")
        return False

def add_song_to_sheets(title, lyrics, ratings_sum=0, ratings_count=0, tags=None):
    if tags is None:
        tags = []
    if not ws:
        return False
    try:
        lyrics_str = "\n".join([f"{l['text']} | {' '.join(l.get('chords', []))}" for l in lyrics])
        ws.append_row([title, lyrics_str, str(ratings_sum), str(ratings_count), ", ".join(tags)])
        return True
    except Exception as e:
        st.error(f"Błąd podczas dodawania piosenki: {e}")
        return False

def delete_song_from_sheets(row_idx):
    if not ws:
        return False
    try:
        ws.delete_rows(row_idx)
        return True
    except Exception as e:
        st.error(f"Błąd podczas usuwania: {e}")
        return False

def update_song_tags(row_idx, tags):
    if not ws:
        return False
    try:
        ws.update([[", ".join(tags)]], f"E{row_idx}")
        return True
    except Exception as e:
        st.error(f"Błąd podczas aktualizacji tagów: {e}")
        return False

def update_song_ratings(row_idx, ratings_sum, ratings_count):
    if not ws:
        return False
    try:
        ws.update([[str(ratings_sum), str(ratings_count)]], f"C{row_idx}")
        return True
    except Exception as e:
        st.error(f"Błąd podczas aktualizacji ocen: {e}")
        return False

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────

st.set_page_config(layout="wide", page_title="Śpiewnik", initial_sidebar_state="expanded")

ADMIN_PIN = "1234"

RATING_TAGS = {
    1: ["Nie lubię", "Nie graj", "Żenada", "Pomiń", "Trudne", "Słabe", "Nudne"],
    2: ["Później", "Kiedyś", "Nie teraz", "Ćwiczyć", "Średnie", "Zapomnij"],
    3: ["Zagraj", "OK", "Niezła", "Ognisko", "Spokojna", "Klasyk", "Może być"],
    4: ["Następne", "Ładna", "Polecam", "Częściej", "Wpadająca", "Energia", "Na start"],
    5: ["HIT", "Koniecznie", "Ulubiona", "TOP", "Mistrz", "Hymn", "Wszyscy", "Legenda"],
}

STOPWORDS = {"się","i","w","z","na","do","że","o","a","to","jak","nie","co","mnie","mi","ci","za","ale","bo","jest","tylko","przez","jeszcze","kiedy","już","dla","od","ten","ta"}

# ─────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────

st.markdown("""
<style>
    .song-title {
        font-weight: bold;
        color: var(--text-color);
        text-align: center;
        line-height: 1.1;
        font-size: 28px !important;
        margin-bottom: 6px !important;
        margin-top: 6px;
    }

    /* Klikalne tagi nad piosenką */
    .song-tags-header {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 6px;
        margin-bottom: 10px;
        flex-wrap: wrap;
    }
    .song-tag-badge {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(255,75,75,0.4);
        color: #ff4b4b;
        padding: 3px 10px;
        border-radius: 16px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.15s;
    }
    .song-tag-badge:hover { background-color: rgba(255,75,75,0.15); }

    /* Wiersz tekstu + chwytów */
    .song-row {
        display: flex;
        justify-content: flex-start;
        align-items: baseline;
        gap: 20px;
        margin-bottom: 0px !important;
        page-break-inside: avoid;
    }
    .lyrics-col {
        flex: 0 0 auto;
        min-width: 150px;
        font-size: 16px;
        color: var(--text-color);
    }
    .chords-col {
        color: #ff4b4b !important;
        font-weight: bold;
        font-size: 16px;
    }

    /* Przyciski nawigacji */
    div.stButton > button { border-radius: 8px; transition: all 0.2s; }

    .nav-btn div.stButton > button {
        padding: 0.5rem 0.2rem !important;
        font-size: 14px !important;
        height: auto !important;
    }
    .list-btn div.stButton > button {
        text-align: left !important;
        justify-content: flex-start !important;
        border: 1px solid var(--secondary-background-color) !important;
    }
    .tag-btn div.stButton > button {
        padding: 2px 8px !important;
        font-size: 12px !important;
        min-height: 0px !important;
        height: 28px !important;
        background-color: var(--secondary-background-color);
        border: 1px solid var(--secondary-background-color);
        color: var(--text-color);
    }
    [data-testid="stSidebar"] div.stButton > button {
        font-size: 11px !important;
        padding: 2px 8px !important;
    }

    hr { margin: 8px 0 !important; }

    /* Tryb pełnoekranowy */
    body.fullscreen-mode [data-testid="stSidebar"],
    body.fullscreen-mode [data-testid="stHeader"],
    body.fullscreen-mode [data-testid="stToolbar"],
    body.fullscreen-mode .controls-section,
    body.fullscreen-mode .stExpander {
        display: none !important;
    }
    body.fullscreen-mode [data-testid="stAppViewContainer"] > section:last-child {
        padding: 1rem 2rem !important;
    }

    /* Transpozycja — ukryty span z danymi per-wiersz */
    .chord-token { display: inline; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def get_keywords(songs_list, source="lyrics", limit=40):
    all_words = []
    for s in songs_list:
        text = (" ".join([l["text"] for l in s["lyrics"]]) if source == "lyrics" else s["title"]).lower()
        all_words.extend([w for w in re.findall(r'\b\w{4,}\b', text) if w not in STOPWORDS])
    return Counter(all_words).most_common(limit)

def get_most_common_tags(songs, limit=10):
    c = Counter(t for s in songs for t in s.get("tags", []))
    return [t[0] for t in c.most_common(limit)]

def get_most_visited_songs(songs, limit=10):
    return sorted([s for s in songs if s["ratings_count"] > 0], key=lambda x: x["ratings_count"], reverse=True)[:limit]

def get_recommended_songs_rotational(songs, limit=5):
    if not songs:
        return []
    neg = set(RATING_TAGS.get(1, []))
    rated_safe = [s for s in songs if s["ratings_count"] > 0 and not any(t in neg for t in s.get("tags", []))]
    unexplored = [s for s in songs if s["ratings_count"] == 0 and not s.get("tags")]
    selection = []
    selection.extend(random.sample(rated_safe, min(2, len(rated_safe))))
    selection.extend(random.sample(unexplored, min(2, len(unexplored))))
    needed = max(0, (limit - 1) - len(selection))
    remaining = [s for s in songs if s not in selection]
    selection.extend(random.sample(remaining, min(needed, len(remaining))))
    if songs:
        selection.append(random.choice(songs))
    random.shuffle(selection)
    return selection[:limit]

def set_song_by_idx(idx):
    if st.session_state.songs:
        st.session_state.current_idx = idx % len(st.session_state.songs)
        st.session_state.transposition = 0

# ─────────────────────────────────────────────
#  RENDEROWANIE TAGÓW / CHMURY
# ─────────────────────────────────────────────

def render_expandable_cloud(items, key_prefix, on_click_action, initial_count=8):
    state_key = f"expanded_{key_prefix}"
    if state_key not in st.session_state:
        st.session_state[state_key] = False
    is_expanded = st.session_state[state_key]
    visible = items if (is_expanded or len(items) <= initial_count) else items[:initial_count]
    needs_toggle = len(items) > initial_count

    cols = st.columns(3)
    for i, item in enumerate(visible):
        label = item if isinstance(item, str) else item[0]
        with cols[i % 3]:
            if st.button(label, key=f"{key_prefix}_{i}", use_container_width=True):
                on_click_action(label)

    if needs_toggle:
        next_i = len(visible)
        with cols[next_i % 3]:
            if st.button("🔼" if is_expanded else "🔽", key=f"toggle_{key_prefix}", use_container_width=True):
                st.session_state[state_key] = not st.session_state[state_key]
                st.rerun()

def render_compact_tags(items, key_prefix, on_click_action, limit=None):
    if not items:
        return
    visible = items[:limit] if limit else items
    st.markdown('<div class="tag-btn">', unsafe_allow_html=True)
    rows = [visible[i:i+4] for i in range(0, len(visible), 4)]
    for r_idx, row_items in enumerate(rows):
        cols = st.columns(4)
        for i, item in enumerate(row_items):
            label = item if isinstance(item, str) else item[0]
            with cols[i]:
                if st.button(label, key=f"{key_prefix}_{r_idx}_{i}", use_container_width=True):
                    on_click_action(label)
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  TRANSPOZYCJA (czysta funkcja)
# ─────────────────────────────────────────────

_NOTES_MAJ = ["C","Cis","D","Dis","E","F","Fis","G","Gis","A","B","H"]
_NOTES_MIN = ["c","cis","d","dis","e","f","fis","g","gis","a","b","h"]

def transpose_chord(chord, steps):
    if steps == 0:
        return chord
    m = re.match(r"^([A-H][is]*|[a-h][is]*)(.*)$", chord)
    if m:
        base, suffix = m.groups()
        if base in _NOTES_MAJ:
            return _NOTES_MAJ[(_NOTES_MAJ.index(base) + steps) % 12] + suffix
        if base in _NOTES_MIN:
            return _NOTES_MIN[(_NOTES_MIN.index(base) + steps) % 12] + suffix
    return chord

def build_song_html(song, transposition):
    """
    Generuje HTML piosenki z data-* na akordach — JS może zmieniać
    transpozycję bez rerenderu Streamlit.
    """
    lines = []
    # Tytuł
    lines.append(f'<div class="song-title">{song["title"]}</div>')

    # Tagi — klikalne (uruchamiają sendPrompt przez JS)
    if song.get("tags"):
        tags_html = '<div class="song-tags-header">'
        for tag in song["tags"]:
            # onclick wysyła komendę przez postMessage (obsługiwana przez fragment JS poniżej)
            safe = tag.replace("'", "\\'")
            tags_html += f'<span class="song-tag-badge" onclick="filterByTag(\'{safe}\')">{tag}</span>'
        tags_html += '</div>'
        lines.append(tags_html)

    lines.append('<hr style="margin: 5px 0 12px 0; opacity: 0.2;">')

    # Tekst + akordy z data-atrybutami (oryginalne akordy bez transpozycji)
    lines.append('<div class="song-container" id="song-container">')
    for l in song["lyrics"]:
        text = l["text"].strip()
        orig_chords = l.get("chords", [])
        transposed = [transpose_chord(c, transposition) for c in orig_chords]
        c_str = " ".join(transposed)
        # data-chords przechowuje oryginalne akordy (do JS transpozycji)
        data_attr = " ".join(orig_chords)
        if text or orig_chords:
            lines.append(
                f'<div class="song-row">'
                f'<div class="lyrics-col">{text or "&nbsp;"}</div>'
                f'<div class="chords-col" data-chords="{data_attr}">{c_str or "&nbsp;"}</div>'
                f'</div>'
            )
        else:
            lines.append('<div style="height: 10px;"></div>')
    lines.append('</div>')
    return "\n".join(lines)

# ─────────────────────────────────────────────
#  STATE
# ─────────────────────────────────────────────

if "songs" not in st.session_state:
    st.session_state.songs = load_songs_cached()

if "current_idx" not in st.session_state:
    st.session_state.current_idx = random.randint(0, max(0, len(st.session_state.songs) - 1))

if "transposition" not in st.session_state:
    st.session_state.transposition = 0

if "kw_lyrics" not in st.session_state:
    st.session_state.kw_lyrics = get_keywords(st.session_state.songs, "lyrics")

if "kw_titles" not in st.session_state:
    st.session_state.kw_titles = get_keywords(st.session_state.songs, "title")

if "random_sample" not in st.session_state:
    st.session_state.random_sample = get_recommended_songs_rotational(st.session_state.songs, limit=5)

if "tag_filter" not in st.session_state:
    st.session_state.tag_filter = None

# Obsługa kliknięcia tagu z HTML (przez query param / JS bridge)
# Streamlit nie ma natywnego JS→Python bridge, więc używamy st.query_params
qp = st.query_params
if "tag" in qp:
    st.session_state.tag_filter = qp["tag"]
    # skocz do losowej piosenki z tym tagiem
    matches = [j for j, s in enumerate(st.session_state.songs) if st.session_state.tag_filter in s.get("tags", [])]
    if matches:
        set_song_by_idx(random.choice(matches))
    st.query_params.clear()
    st.rerun()

# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────

with st.sidebar:
    st.title("Biblioteka")

    # ── Wyszukiwarka ──
    query = st.text_input("Szukaj:", placeholder="Tytuł lub tekst...", key="main_search_input").lower()
    if query:
        found = [i for i, s in enumerate(st.session_state.songs)
                 if query in (s["title"] + " " + " ".join(l["text"] for l in s["lyrics"])).lower()]
        if found:
            for idx in found:
                if st.button(st.session_state.songs[idx]["title"], key=f"search_res_{idx}", use_container_width=True):
                    set_song_by_idx(idx)
                    st.rerun()

    st.markdown("---")

    # ── TAGI — na samej górze sidebara (przed słowami kluczowymi) ──
    st.caption("🏷️ TAGI")
    all_tags_flat = [t for s in st.session_state.songs for t in s.get("tags", [])]
    if all_tags_flat:
        common_tags = [t for t, _ in Counter(all_tags_flat).most_common(50)]

        def _jump_to_tag(tag):
            matches = [j for j, s in enumerate(st.session_state.songs) if tag in s.get("tags", [])]
            if matches:
                set_song_by_idx(random.choice(matches))
            st.rerun()

        render_expandable_cloud(common_tags, "side_tags", _jump_to_tag, initial_count=9)
    else:
        st.caption("Brak tagów.")

    st.markdown("---")
    st.caption("Z TEKSTU")
    if st.session_state.kw_lyrics:
        def _jump_to_lyrics_kw(w):
            matches = [j for j, s in enumerate(st.session_state.songs) if w in " ".join(l["text"] for l in s["lyrics"]).lower()]
            if matches:
                set_song_by_idx(random.choice(matches))
            st.rerun()
        render_expandable_cloud([w for w, _ in st.session_state.kw_lyrics], "side_l", _jump_to_lyrics_kw, initial_count=9)

    st.markdown("---")
    st.caption("Z TYTUŁÓW")
    if st.session_state.kw_titles:
        def _jump_to_title_kw(w):
            matches = [j for j, s in enumerate(st.session_state.songs) if w in s["title"].lower()]
            if matches:
                set_song_by_idx(random.choice(matches))
            st.rerun()
        render_expandable_cloud([w for w, _ in st.session_state.kw_titles], "side_t", _jump_to_title_kw, initial_count=6)

    st.markdown("---")
    if st.button("🔄 Odśwież bazę", key="refresh_sidebar", use_container_width=True):
        reload_songs()
        st.session_state.kw_lyrics = get_keywords(st.session_state.songs, "lyrics")
        st.session_state.kw_titles = get_keywords(st.session_state.songs, "title")
        st.rerun()

# ─────────────────────────────────────────────
#  GUARD
# ─────────────────────────────────────────────

if not st.session_state.songs:
    st.warning("Baza piosenek jest pusta lub brak połączenia.")
    st.stop()

song = st.session_state.songs[st.session_state.current_idx]

# ─────────────────────────────────────────────
#  PIOSENKA — widok główny
# ─────────────────────────────────────────────

song_html = build_song_html(song, st.session_state.transposition)
st.markdown(song_html, unsafe_allow_html=True)

# JS: obsługa kliknięcia tagu (ustawia query param i przeładowuje)
# JS: obsługa transpozycji bez rerenderu Streamlit
st.markdown("""
<script>
function filterByTag(tag) {
    const url = new URL(window.location.href);
    url.searchParams.set('tag', tag);
    window.location.href = url.toString();
}

// ── Transpozycja przez JS ───────────────────────────────
const NOTES_MAJ = ["C","Cis","D","Dis","E","F","Fis","G","Gis","A","B","H"];
const NOTES_MIN = ["c","cis","d","dis","e","f","fis","g","gis","a","b","h"];

function transposeChord(chord, steps) {
    if (steps === 0) return chord;
    const m = chord.match(/^([A-H][is]*|[a-h][is]*)(.*)$/);
    if (!m) return chord;
    const [, base, suffix] = m;
    let arr = NOTES_MAJ.includes(base) ? NOTES_MAJ : (NOTES_MIN.includes(base) ? NOTES_MIN : null);
    if (!arr) return chord;
    return arr[((arr.indexOf(base) + steps) % 12 + 12) % 12] + suffix;
}

let jsTransposition = 0;

function applyJsTransposition() {
    document.querySelectorAll('.chords-col[data-chords]').forEach(el => {
        const orig = el.getAttribute('data-chords');
        if (!orig.trim()) return;
        el.textContent = orig.trim().split(/[ \t]+/).map(c => transposeChord(c, jsTransposition)).join(' ');
    });
    const disp = document.getElementById('js-trans-display');
    if (disp) disp.textContent = (jsTransposition >= 0 ? '+' : '') + jsTransposition;
}

window._transposeUp = function() { jsTransposition++; applyJsTransposition(); }
window._transposeDown = function() { jsTransposition--; applyJsTransposition(); }
window._transposeReset = function() { jsTransposition = 0; applyJsTransposition(); }
</script>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  PANEL STEROWANIA (domyślnie zwinięty)
# ─────────────────────────────────────────────

st.markdown('<div class="controls-section">', unsafe_allow_html=True)

with st.expander("🎛️ Sterowanie", expanded=False):

    # ── Nawigacja ──
    st.markdown('<div class="nav-btn">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("⬅️ Wstecz", key="nav_prev", use_container_width=True):
            set_song_by_idx(st.session_state.current_idx - 1)
            st.rerun()
    with c2:
        if st.button("➡️ Dalej", key="nav_next", use_container_width=True):
            set_song_by_idx(st.session_state.current_idx + 1)
            st.rerun()
    with c3:
        if st.button("🎲 Losowa", key="nav_rand", use_container_width=True):
            set_song_by_idx(random.randint(0, len(st.session_state.songs) - 1))
            st.rerun()
    with c4:
        if st.button("⭐️ Ostatnia", key="nav_last", use_container_width=True):
            set_song_by_idx(len(st.session_state.songs) - 1)
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<hr style="opacity: 0.15;">', unsafe_allow_html=True)

    # ── Transpozycja — JS (zero rerenderów) + Python backup ──
    st.caption("Zmień tonację (JS — bez przeładowania)")
    # Przyciski JS wywoływane przez onclick — nie triggerują Streamlit
    st.markdown("""
    <div style="display:flex; gap:8px; align-items:center; margin-bottom:6px;">
        <button onclick="window._transposeDown()" style="padding:4px 14px; border-radius:6px; cursor:pointer; border:1px solid #ccc; background:var(--secondary-background-color); color:var(--text-color); font-size:14px;">➖</button>
        <span id="js-trans-display" style="font-weight:bold; min-width:30px; text-align:center; color:var(--text-color);">+0</span>
        <button onclick="window._transposeUp()" style="padding:4px 14px; border-radius:6px; cursor:pointer; border:1px solid #ccc; background:var(--secondary-background-color); color:var(--text-color); font-size:14px;">➕</button>
        <button onclick="window._transposeReset()" style="padding:4px 14px; border-radius:6px; cursor:pointer; border:1px solid #ccc; background:var(--secondary-background-color); color:var(--text-color); font-size:13px;">↺ Reset</button>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<hr style="opacity: 0.15;">', unsafe_allow_html=True)

    # ── Ocena ──
    col_rate_info, col_rate_act = st.columns([1, 2])
    with col_rate_info:
        avg = song["ratings_sum"] / song["ratings_count"] if song["ratings_count"] > 0 else 0
        st.markdown(f"<div style='font-size:12px; opacity:0.7;'>Średnia: <b>{avg:.1f}</b><br>Głosów: {song['ratings_count']}</div>", unsafe_allow_html=True)
    with col_rate_act:
        score = st.feedback("stars", key="rating_feedback")
        if score is None:
            score_rad = st.radio("Oceń:", [1, 2, 3, 4, 5], horizontal=True, label_visibility="collapsed", key="rating_radio_backup")
            if st.button("Zapisz ocenę", key="save_rating_btn", use_container_width=True):
                new_sum = song["ratings_sum"] + score_rad
                new_count = song["ratings_count"] + 1
                update_song_ratings(song["row"], new_sum, new_count)
                st.success("Zapisano!")
                reload_songs()
                st.rerun()
        elif score is not None:
            r_val = score + 1
            if st.button(f"Wyślij ocenę {r_val}/5", key="send_stars", use_container_width=True):
                update_song_ratings(song["row"], song["ratings_sum"] + r_val, song["ratings_count"] + 1)
                st.toast("Ocena dodana!")
                reload_songs()
                st.rerun()

    st.markdown('<hr style="opacity: 0.15;">', unsafe_allow_html=True)

    # ── Tagi piosenki ──
    st.caption("Sugerowane tagi (kliknij by dodać):")
    score_for_tags = 3
    if "rating_radio_backup" in st.session_state:
        score_for_tags = st.session_state.rating_radio_backup
    if score_for_tags in RATING_TAGS:
        def _add_suggested_tag(t):
            if t not in song.get("tags", []):
                song["tags"].append(t)
                update_song_tags(song["row"], song["tags"])
                reload_songs()
                st.rerun()
        render_compact_tags(RATING_TAGS[score_for_tags], f"sug_{score_for_tags}", _add_suggested_tag)

    st.caption("Tagi tej piosenki (X = usuń):")
    current_tags = song.get("tags", [])
    if current_tags:
        st.markdown('<div class="tag-btn">', unsafe_allow_html=True)
        cols = st.columns(4)
        for i, tag in enumerate(current_tags):
            with cols[i % 4]:
                if st.button(f"✕ {tag}", key=f"del_tag_{i}", use_container_width=True):
                    song["tags"].remove(tag)
                    update_song_tags(song["row"], song["tags"])
                    reload_songs()
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    c_add_t1, c_add_t2 = st.columns([3, 1])
    with c_add_t1:
        new_tag_txt = st.text_input("Nowy tag", placeholder="Wpisz...", label_visibility="collapsed", key="new_tag_input")
    with c_add_t2:
        if st.button("➕", key="add_tag_plus", use_container_width=True):
            if new_tag_txt and new_tag_txt not in current_tags:
                song["tags"].append(new_tag_txt)
                update_song_tags(song["row"], song["tags"])
                reload_songs()
                st.rerun()

    st.markdown('<hr style="opacity: 0.15;">', unsafe_allow_html=True)

    # ── Polecane ──
    st.subheader("📚 Polecane")
    tab_tags, tab_rand, tab_top = st.tabs(["🏷️ Wg Tagów", "🎲 Losowe", "🏆 Top"])

    with tab_tags:
        all_unique_tags = sorted(set(t for s in st.session_state.songs for t in s.get("tags", [])))
        selected_tag = st.selectbox("Wybierz tag:", [""] + all_unique_tags, key="tag_search_box")
        if selected_tag:
            tagged = [s for s in st.session_state.songs if selected_tag in s.get("tags", [])]
            st.caption(f"{len(tagged)} piosenek:")
            st.markdown('<div class="list-btn">', unsafe_allow_html=True)
            for i, ts in enumerate(tagged):
                if st.button(ts["title"], key=f"tag_search_res_{i}", use_container_width=True):
                    real_idx = next((j for j, s in enumerate(st.session_state.songs) if s["title"] == ts["title"]), 0)
                    set_song_by_idx(real_idx)
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    with tab_rand:
        if st.button("🔄 Losuj inne", key="reroll_recs", use_container_width=True):
            st.session_state.random_sample = get_recommended_songs_rotational(st.session_state.songs, limit=5)
            st.rerun()
        st.markdown('<div class="list-btn">', unsafe_allow_html=True)
        for i, rs in enumerate(st.session_state.random_sample):
            prefix = "⭐" if rs["ratings_count"] > 0 else "🆕"
            if st.button(f"{prefix} {rs['title']}", key=f"rec_r_{i}", use_container_width=True):
                set_song_by_idx(next((j for j, s in enumerate(st.session_state.songs) if s["title"] == rs["title"]), 0))
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_top:
        top_visited = get_most_visited_songs(st.session_state.songs, limit=5)
        st.markdown('<div class="list-btn">', unsafe_allow_html=True)
        for i, ts in enumerate(top_visited):
            if st.button(f"{i+1}. {ts['title']} ({ts['ratings_count']} głosów)", key=f"rec_t_{i}", use_container_width=True):
                set_song_by_idx(next((j for j, s in enumerate(st.session_state.songs) if s["title"] == ts["title"]), 0))
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Panel Administracyjny ──
    with st.expander("🛠️ Panel Administracyjny"):
        tab_edit, tab_add, tab_del, tab_stats = st.tabs(["✏️ Edytuj", "➕ Dodaj", "🗑️ Usuń", "📊 Statystyki"])

        with tab_edit:
            curr_id = st.session_state.current_idx
            et = st.text_input("Tytuł:", value=song["title"], key=f"edit_title_{curr_id}")
            el = [f"{l['text']} | {' '.join(l.get('chords', []))}" for l in song["lyrics"]]
            nc = st.text_area("Treść (Tekst | Chwyty):", value="\n".join(el), height=200, key=f"edit_area_{curr_id}")
            if st.button("Zapisz zmiany", key=f"btn_save_edit_{curr_id}", use_container_width=True):
                nl = []
                for line in nc.split("\n"):
                    p = line.split("|", 1)
                    if len(p) > 1:
                        nl.append({"text": p[0].strip(), "chords": p[1].strip().split() if p[1].strip() else []})
                    else:
                        nl.append({"text": line.strip(), "chords": []})
                if save_song_to_sheets(song["row"], et, nl, song["ratings_sum"], song["ratings_count"], song["tags"]):
                    st.success("Zmiany zapisane!")
                    reload_songs()
                    st.rerun()

        with tab_add:
            new_t = st.text_input("Tytuł piosenki:", key="add_new_title")
            new_l = st.text_area("Treść (Format: Tekst | Chwyty):",
                                 placeholder="Wpisz tekst piosenki...\nMożesz dodać chwyty po kresce |",
                                 height=200, key="add_new_area")
            if st.button("Dodaj do biblioteki", key="btn_add_new_song", use_container_width=True):
                if new_t and new_l:
                    parsed_lyrics = []
                    for line in new_l.split("\n"):
                        parts = line.split("|", 1)
                        if len(parts) > 1:
                            parsed_lyrics.append({"text": parts[0].strip(), "chords": parts[1].strip().split() if parts[1].strip() else []})
                        else:
                            parsed_lyrics.append({"text": line.strip(), "chords": []})
                    if add_song_to_sheets(new_t, parsed_lyrics):
                        st.success(f"Dodano: {new_t}")
                        reload_songs()
                        st.session_state.current_idx = len(st.session_state.songs) - 1
                        st.rerun()
                else:
                    st.error("Podaj tytuł i treść!")

        with tab_del:
            pin_input = st.text_input("PIN blokady", type="password", key="del_pin")
            if pin_input == ADMIN_PIN:
                st.warning(f"⚠️ Zamierzasz usunąć: **{song['title']}**")
                if st.button("POTWIERDZAM USUNIĘCIE", type="primary", use_container_width=True):
                    if delete_song_from_sheets(song["row"]):
                        st.success("Piosenka usunięta!")
                        reload_songs()
                        set_song_by_idx(0)
                        st.rerun()
            elif pin_input:
                st.error("Błędny PIN!")

        with tab_stats:
            col1, col2, col3, col4 = st.columns(4)
            total_ratings = sum(s["ratings_count"] for s in st.session_state.songs)
            with col1:
                st.metric("📚 Piosenek", len(st.session_state.songs))
            with col2:
                st.metric("⭐ Ocenianych", len([s for s in st.session_state.songs if s["ratings_count"] > 0]))
            with col3:
                st.metric("🗳️ Ocen łącznie", total_ratings)
            with col4:
                avg_r = sum(s["ratings_sum"] for s in st.session_state.songs) / max(total_ratings, 1) if total_ratings else 0
                st.metric("⬇️ Średnia", f"{avg_r:.2f}")

            st.markdown("---")
            st.caption("🔥 Najczęściej odwiedzane:")
            for i, s in enumerate(get_most_visited_songs(st.session_state.songs, limit=10), 1):
                a = s["ratings_sum"] / s["ratings_count"] if s["ratings_count"] else 0
                st.write(f"{i}. **{s['title']}** — {s['ratings_count']} ocen (śr. {a:.1f})")

            st.markdown("---")
            st.caption("🏆 Najczęstsze tagi:")
            tag_counts = Counter(t for s in st.session_state.songs for t in s.get("tags", []))
            for i, (tag, count) in enumerate(tag_counts.most_common(20), 1):
                st.write(f"{i}. **{tag}** — {count}×")

st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  TRYB PEŁNOEKRANOWY (przycisk na dole)
# ─────────────────────────────────────────────

st.markdown("""
<div style="text-align:center; margin-top: 8px;">
    <button id="fullscreen-toggle"
        onclick="toggleFullscreen()"
        style="background:transparent; border:1px solid rgba(128,128,128,0.3);
               border-radius:8px; padding:4px 16px; cursor:pointer;
               color:var(--text-color); font-size:13px; opacity:0.6;">
        📖 Tryb gry
    </button>
</div>
<script>
let _fsActive = false;
function toggleFullscreen() {
    _fsActive = !_fsActive;
    document.body.classList.toggle('fullscreen-mode', _fsActive);
    document.getElementById('fullscreen-toggle').textContent = _fsActive ? '✕ Wyjdź z trybu gry' : '📖 Tryb gry';
}
</script>
""", unsafe_allow_html=True)
