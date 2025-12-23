import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
import random
import re
from collections import Counter
import pandas as pd

# ------------------------------
# 1. Konfiguracja Google Sheets
# ------------------------------
def init_gsheet():
    """Inicjalizacja połączenia z Google Sheets"""
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key("1RG82ZtUZfNsOjXI7xHKDnwbnDUl2SwE5oDLMNJNYdkw")
        worksheet = spreadsheet.worksheet("Songs")
        return worksheet
    except Exception as e:
        st.error(f"Błąd połączenia z Google Sheets: {e}")
        return None

# Inicjalizujemy arkusz
ws = init_gsheet()

# ------------------------------
# 2. Funkcje obsługi danych z Sheets
# ------------------------------
def load_songs_from_sheets():
    """Ładuje wszystkie piosenki z arkusza"""
    if not ws:
        return []
    
    try:
        rows = ws.get_all_values()
        if not rows or len(rows) < 2:
            return []
        
        header = rows[0]
        songs = []
        
        for i, row in enumerate(rows[1:], start=2):
            if len(row) >= 2 and row[0].strip():
                title = row[0].strip()
                lyrics_raw = row[1].strip() if len(row) > 1 else ""
                ratings_sum = int(row[2]) if len(row) > 2 and row[2].isdigit() else 0
                ratings_count = int(row[3]) if len(row) > 3 and row[3].isdigit() else 0
                tags_raw = row[4].strip() if len(row) > 4 else ""
                
                # Parsujemy lyrics
                lyrics = []
                
                # Sprawdzamy czy to JSON format
                if lyrics_raw.startswith("["):
                    try:
                        lyrics_json = json.loads(lyrics_raw)
                        for item in lyrics_json:
                            if isinstance(item, dict):
                                text = item.get("text", "").strip()
                                chords = item.get("chords", [])
                                if isinstance(chords, str):
                                    chords = chords.split()
                                lyrics.append({"text": text, "chords": chords})
                    except:
                        # Fallback jeśli JSON jest nieprawidłowy
                        lyrics.append({"text": lyrics_raw, "chords": []})
                else:
                    # Stary format: Tekst | Chwyty
                    for line in lyrics_raw.split("\n"):
                        if "|" in line:
                            parts = line.split("|", 1)
                            lyrics.append({
                                "text": parts[0].strip(),
                                "chords": parts[1].strip().split() if parts[1].strip() else []
                            })
                        else:
                            lyrics.append({"text": line.strip(), "chords": []})
                
                # Parsujemy tags (format: tag1, tag2, tag3)
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                
                songs.append({
                    "title": title,
                    "lyrics": lyrics,
                    "ratings_sum": ratings_sum,
                    "ratings_count": ratings_count,
                    "tags": tags,
                    "row": i
                })
        
        return songs
    except Exception as e:
        st.error(f"Błąd podczas ładowania piosenek: {e}")
        return []

def save_song_to_sheets(row_idx, title, lyrics, ratings_sum, ratings_count, tags):
    """Zapisuje piosenkę do arkusza (aktualizuje istniejący wiersz)"""
    if not ws:
        return False
    
    try:
        lyrics_str = "\n".join([
            f"{l['text']} | {' '.join(l.get('chords', []))}" 
            for l in lyrics
        ])
        
        tags_str = ", ".join(tags)
        
        # Aktualizujemy kolumny A-E w wybranym wierszu
        ws.update(
            [[title, lyrics_str, str(ratings_sum), str(ratings_count), tags_str]],
            f"A{row_idx}:E{row_idx}",
            raw=False
        )
        return True
    except Exception as e:
        st.error(f"Błąd podczas zapisywania: {e}")
        return False

def add_song_to_sheets(title, lyrics, ratings_sum=0, ratings_count=0, tags=[]):
    """Dodaje nową piosenkę do arkusza"""
    if not ws:
        return False
    
    try:
        lyrics_str = "\n".join([
            f"{l['text']} | {' '.join(l.get('chords', []))}" 
            for l in lyrics
        ])
        tags_str = ", ".join(tags)
        
        ws.append_row([title, lyrics_str, str(ratings_sum), str(ratings_count), tags_str])
        return True
    except Exception as e:
        st.error(f"Błąd podczas dodawania piosenki: {e}")
        return False

def delete_song_from_sheets(row_idx):
    """Usuwa piosenkę z arkusza"""
    if not ws:
        return False
    
    try:
        ws.delete_rows(row_idx)
        return True
    except Exception as e:
        st.error(f"Błąd podczas usuwania: {e}")
        return False

def update_song_tags(row_idx, tags):
    """Aktualizuje tylko tagi piosenki"""
    if not ws:
        return False
    
    try:
        tags_str = ", ".join(tags)
        ws.update([[tags_str]], f"E{row_idx}")
        return True
    except Exception as e:
        st.error(f"Błąd podczas aktualizacji tagów: {e}")
        return False

def update_song_ratings(row_idx, ratings_sum, ratings_count):
    """Aktualizuje oceny piosenki"""
    if not ws:
        return False
    
    try:
        ws.update([
            [str(ratings_sum), str(ratings_count)]
        ], f"C{row_idx}")
        return True
    except Exception as e:
        st.error(f"Błąd podczas aktualizacji ocen: {e}")
        return False

# ------------------------------
# 3. Konfiguracja i Style
# ------------------------------
st.set_page_config(
    layout="wide", 
    page_title="Śpiewnik",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Główne tło i kontener */
    [data-testid="stAppViewContainer"] { background-color: #0e1117; }
    [data-testid="stSidebar"] { background-color: #010409; }
    
    /* TYTUŁ PIOSENKI */
    .song-title {
        font-weight: bold;
        color: #ffffff;
        text-align: center;
        line-height: 1.1;
        font-size: 34px !important;
        margin-bottom: 10px !important;
    }

    /* TEKST I CHWYTY */
    .song-row {
        display: flex;
        justify-content: flex-start;
        align-items: baseline;
        gap: 20px;
        margin-bottom: 0px !important;
    }
    .lyrics-col { flex: 0 0 auto; min-width: 150px; font-size: 16px; color: #eee; }
    .chords-col { color: #ff4b4b !important; font-weight: bold; font-size: 16px; }

    /* TAGI W SIDEBARZE */
    [data-testid="stSidebar"] div.stButton > button:first-child {
        font-size: 10px !important;
        padding: 2px 4px !important;
        background-color: #1f2937 !important;
        color: #ffffff !important;
        border: 1px solid #4b5563 !important;
    }

    /* UKRYWANIE ELEMENTÓW W ZALEŻNOŚCI OD EKRANU */
    .mobile-nav { display: none; }

    @media (max-width: 800px) {
        div[data-testid="column"]:has(button[key*="nav_"]) {
            display: none !important;
        }
        .mobile-nav { 
            display: flex !important; 
            flex-wrap: nowrap; 
            justify-content: center; 
            gap: 5px; 
            padding: 10px 0;
            border-top: 1px solid #333;
        }
        .song-title { font-size: 20px !important; }
        
        div[data-testid="stExpander"] button {
            font-size: 11px !important;
            padding: 2px !important;
        }
    }
</style>
""", unsafe_allow_html=True)

ADMIN_PIN = "1234"

# Tagi ocen
RATING_TAGS = {
    1: ["Nie lubię", "Nie graj", "Żenada", "Pomiń", "Trudne", "Słabe", "Nudne"],
    2: ["Później", "Kiedyś", "Nie teraz", "Ćwiczyć", "Średnie", "Zapomnij"],
    3: ["Zagraj", "OK", "Niezła", "Ognisko", "Spokojna", "Klasyk", "Może być"],
    4: ["Następne", "Ładna", "Polecam", "Częściej", "Wpadająca", "Energia", "Na start"],
    5: ["HIT", "Koniecznie", "Ulubiona", "TOP", "Mistrz", "Hymn", "Wszyscy", "Legenda"]
}

# Stopwords do analizy
STOPWORDS = {"się", "i", "w", "z", "na", "do", "że", "o", "a", "to", "jak", "nie", "co", "mnie", "mi", "ci", "za", "ale", "bo", "jest", "tylko", "przez", "jeszcze", "kiedy", "już", "dla", "od", "ten", "ta"}

# ------------------------------
# 4. Funkcje analizy
# ------------------------------
def get_keywords(songs_list, source="lyrics", limit=40):
    """Pobiera najczęstsze słowa z piosenek"""
    all_words = []
    for s in songs_list:
        if source == "lyrics":
            text = " ".join([l["text"] for l in s["lyrics"]]).lower()
        else:
            text = s["title"].lower()
        
        words = re.findall(r'\b\w{4,}\b', text)
        all_words.extend([w for w in words if w not in STOPWORDS])
    
    most_common = Counter(all_words).most_common(limit)
    return most_common if most_common else []

def get_best_songs_all_time(songs):
    """Zwraca najlepiej ocenianą piosenkę"""
    if not songs:
        return None
    
    best = max(
        songs,
        key=lambda x: x["ratings_sum"] / x["ratings_count"] if x["ratings_count"] > 0 else 0
    )
    return best["title"] if best["ratings_count"] > 0 else None

# Reload danych
def reload_songs():
    """Przeładowuje piosenki z arkusza"""
    st.session_state.songs = load_songs_from_sheets()

# Stan aplikacji
if "songs" not in st.session_state:
    st.session_state.songs = load_songs_from_sheets()

if "current_idx" not in st.session_state:
    st.session_state.current_idx = random.randint(0, len(st.session_state.songs) - 1) if st.session_state.songs else 0

if "transposition" not in st.session_state:
    st.session_state.transposition = 0

if "kw_lyrics" not in st.session_state:
    st.session_state.kw_lyrics = get_keywords(st.session_state.songs, "lyrics")

if "kw_titles" not in st.session_state:
    st.session_state.kw_titles = get_keywords(st.session_state.songs, "title")

if "random_sample" not in st.session_state:
    st.session_state.random_sample = random.sample(st.session_state.songs, min(5, len(st.session_state.songs))) if st.session_state.songs else []

def set_song_by_idx(idx):
    """Ustawia bieżącą piosenkę"""
    if st.session_state.songs:
        st.session_state.current_idx = idx % len(st.session_state.songs)
        st.session_state.transposition = 0

# ------------------------------
# 5. RENDEROWANIE CHMURY TAGÓW
# ------------------------------
def render_expandable_cloud(items, key_prefix, on_click_action, initial_count=8):
    """Renderuje rozszerzalną chmurę tagów"""
    state_key = f"expanded_{key_prefix}"
    if state_key not in st.session_state:
        st.session_state[state_key] = False
    is_expanded = st.session_state[state_key]
    
    if len(items) <= initial_count:
        visible_items = items
        needs_toggle = False
    else:
        visible_items = items if is_expanded else items[:initial_count]
        needs_toggle = True

    cols_num = 3 
    columns = st.columns(cols_num)
    
    for i, item in enumerate(visible_items):
        label = item if isinstance(item, str) else item[0]
        with columns[i % cols_num]:
            if st.button(label, key=f"{key_prefix}_{i}", use_container_width=True):
                on_click_action(label)

    if needs_toggle:
        next_idx = len(visible_items)
        with columns[next_idx % cols_num]:
            btn_label = "🔼" if is_expanded else "🔽"
            if st.button(btn_label, key=f"toggle_{key_prefix}", use_container_width=True):
                st.session_state[state_key] = not st.session_state[state_key]
                st.rerun()

# ------------------------------
# 6. SIDEBAR
# ------------------------------
with st.sidebar:
    st.title("Biblioteka")
    
    query = st.text_input("Szukaj:", placeholder="Tytuł...", key="main_search_input").lower()
    if query:
        found = [i for i, s in enumerate(st.session_state.songs) 
                if query in (s["title"] + " " + " ".join([l["text"] for l in s["lyrics"]])).lower()]
        if found:
            sel = st.selectbox("Wyniki:", [st.session_state.songs[i]['title'] for i in found], key="search_results_select")
            if st.button("Idź", key="go_to_search_result"):
                set_song_by_idx(found[[st.session_state.songs[i]['title'] for i in found].index(sel)])
                st.rerun()

    st.markdown("---")
    
    st.caption("WSZYSTKIE TAGI")
    all_tags = []
    for song in st.session_state.songs:
        all_tags.extend(song.get("tags", []))
    
    if all_tags:
        common_tags = [t[0] for t in Counter(all_tags).most_common(50)]
        render_expandable_cloud(common_tags, "side_tags", 
            lambda t: (set_song_by_idx(random.choice([j for j, s in enumerate(st.session_state.songs) if t in s.get("tags", [])])), st.rerun())[1], 
            initial_count=6)
    else:
        st.caption("Brak.")

    st.markdown("---")
    st.caption("Z TEKSTU")
    if st.session_state.kw_lyrics:
        render_expandable_cloud([w[0] for w in st.session_state.kw_lyrics], "side_l", 
            lambda w: (set_song_by_idx(random.choice([j for j, s in enumerate(st.session_state.songs) if w in " ".join([l["text"] for l in s["lyrics"]]).lower()])), st.rerun())[1], 
            initial_count=9)

    st.markdown("---")
    st.caption("Z TYTUŁÓW")
    if st.session_state.kw_titles:
        render_expandable_cloud([w[0] for w in st.session_state.kw_titles], "side_t", 
            lambda w: (set_song_by_idx(random.choice([j for j, s in enumerate(st.session_state.songs) if w in s["title"].lower()])), st.rerun())[1], 
            initial_count=6)
    
    st.markdown("---")
    if st.button("🔄 Odśwież bazę", key="refresh_sidebar", use_container_width=True):
        reload_songs()
        st.session_state.kw_lyrics = get_keywords(st.session_state.songs, "lyrics")
        st.session_state.kw_titles = get_keywords(st.session_state.songs, "title")
        st.rerun()

# ------------------------------
# 7. LOGIKA I NAGŁÓWEK
# ------------------------------
if not st.session_state.songs:
    st.warning("Baza piosenek jest pusta.")
    st.stop()

song = st.session_state.songs[st.session_state.current_idx]

# Górna linia nawigacji
c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1, 1, 1, 10, 1, 1, 1, 1])
with c1:
    if st.button("⬅️", key="nav_prev"):
        set_song_by_idx(st.session_state.current_idx - 1)
        st.rerun()
with c2:
    if st.button("🎲", key="nav_rand"):
        set_song_by_idx(random.randint(0, len(st.session_state.songs)-1))
        st.rerun()
with c3:
    if st.button("🆕", key="nav_last"):
        set_song_by_idx(len(st.session_state.songs)-1)
        st.rerun()
with c4:
    st.markdown(f'<div class="song-title">{song["title"]}</div>', unsafe_allow_html=True)
with c5:
    if st.button("➖", key="nav_t_down"):
        st.session_state.transposition -= 1
        st.rerun()
with c6:
    st.markdown(f'<div style="text-align:center; color:#ff4b4b; font-weight:bold;">{st.session_state.transposition:+}</div>', unsafe_allow_html=True)
with c7:
    if st.button("➕", key="nav_t_up"):
        st.session_state.transposition += 1
        st.rerun()
with c8:
    if st.button("➡️", key="nav_next"):
        set_song_by_idx(st.session_state.current_idx + 1)
        st.rerun()

st.markdown('<hr style="margin: 5px 0 15px 0; opacity: 0.2;">', unsafe_allow_html=True)

# ------------------------------
# 8. TREŚĆ UTWORU
# ------------------------------
def transpose_chord(chord, steps):
    """Transpozycja akordu"""
    D = ["C","Cis","D","Dis","E","F","Fis","G","Gis","A","B","H"]
    m = ["c","cis","d","dis","e","f","fis","g","gis","a","b","h"]
    match = re.match(r"^([A-H][is]*|[a-h][is]*)(.*)$", chord)
    if match:
        base, suffix = match.groups()
        if base in D:
            return D[(D.index(base) + steps) % 12] + suffix
        if base in m:
            return m[(m.index(base) + steps) % 12] + suffix
    return chord

st.markdown('<hr style="margin: 5px 0 15px 0; opacity: 0.2;">', unsafe_allow_html=True)

html = '<div class="song-container">'
for l in song["lyrics"]:
    clean_text = l["text"].strip()
    chds = [transpose_chord(c, st.session_state.transposition) for c in l.get("chords", [])]
    c_str = " ".join(chds)
    
    if clean_text or chds:
        html += f'<div class="song-row"><div class="lyrics-col">{clean_text or "&nbsp;"}</div><div class="chords-col">{c_str or "&nbsp;"}</div></div>'
    else:
        html += '<div style="height: 12px;"></div>'

st.markdown(html + '</div>', unsafe_allow_html=True)

# Dodatkowa nawigacja mobilna
st.markdown('<div class="mobile-nav">', unsafe_allow_html=True)
mb1, mb2, mb3, mb4, mb5, mb6, mb7 = st.columns([1,1,1,1,1,1,1])
with mb1:
    if st.button("⬅️", key="m_prev"):
        set_song_by_idx(st.session_state.current_idx - 1)
        st.rerun()
with mb2:
    if st.button("🎲", key="m_rand"):
        set_song_by_idx(random.randint(0, len(st.session_state.songs)-1))
        st.rerun()
with mb3:
    if st.button("🆕", key="m_last"):
        set_song_by_idx(len(st.session_state.songs)-1)
        st.rerun()
with mb4:
    if st.button("➖", key="m_t_down"):
        st.session_state.transposition -= 1
        st.rerun()
with mb5:
    st.markdown(f'<div style="color:#ff4b4b; text-align:center;">{st.session_state.transposition:+}</div>', unsafe_allow_html=True)
with mb6:
    if st.button("➕", key="m_t_up"):
        st.session_state.transposition += 1
        st.rerun()
with mb7:
    if st.button("➡️", key="m_next"):
        set_song_by_idx(st.session_state.current_idx + 1)
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<hr style="margin: 30px 0 10px 0; opacity: 0.2;">', unsafe_allow_html=True)

# Sekcja polecane
st.subheader("📚 Polecane utwory")
c_rec1, c_rec2 = st.columns(2)
with c_rec1:
    st.caption("Losowe propozycje:")
    if st.button("🔄 Odśwież listę", key="ref_rnd", use_container_width=True):
        st.session_state.random_sample = random.sample(st.session_state.songs, min(5, len(st.session_state.songs)))
        st.rerun()
    for i, rs in enumerate(st.session_state.random_sample):
        if st.button(rs["title"], key=f"r_{i}", use_container_width=True):
            set_song_by_idx(next((j for j, s in enumerate(st.session_state.songs) if s["title"] == rs["title"]), 0))
            st.rerun()
with c_rec2:
    st.caption("Najlepiej oceniane (TOP):")
    ba = get_best_songs_all_time(st.session_state.songs)
    if ba:
        if st.button(f"🏆 {ba}", key="top_song_btn", use_container_width=True):
            set_song_by_idx(next((i for i, s in enumerate(st.session_state.songs) if s["title"] == ba), 0))
            st.rerun()
    else:
        st.write("Brak ocen.")

st.markdown("---")

# OCENY I TAGI
tab_vote, tab_tags = st.tabs(["⭐ Oceń tę piosenkę", "🏷️ Tagi użytkownika"])

with tab_vote:
    col_v1, col_v2 = st.columns([2, 1])
    with col_v1:
        avg = song["ratings_sum"] / song["ratings_count"] if song["ratings_count"] > 0 else 0
        st.write(f"Średnia ocena: **{avg:.1f}** ({song['ratings_count']} głosów)")
        score = st.radio("Twoja ocena:", [1,2,3,4,5], horizontal=True, key="rating_radio")
        if st.button("Zapisz ocenę", key="btn_zapisz_ocene_main"):
            new_sum = song["ratings_sum"] + score
            new_count = song["ratings_count"] + 1
            
            if update_song_ratings(song["row"], new_sum, new_count):
                st.success("Ocena zapisana!")
                reload_songs()
                st.session_state.current_idx = next((i for i, s in enumerate(st.session_state.songs) if s["title"] == song["title"]), 0)
                st.rerun()
    
    if score in RATING_TAGS:
        st.caption("Sugerowane tagi:")
        render_expandable_cloud(RATING_TAGS[score], f"sug_tag_{score}", 
            lambda t: (song["tags"].append(t) or update_song_tags(song["row"], song["tags"]) or reload_songs() or st.rerun()) 
            if t not in song.get("tags", []) else None, 
            initial_count=8)

with tab_tags:
    current_tags = song.get("tags", [])
    if current_tags:
        cols = st.columns(3)
        for i, tag in enumerate(current_tags):
            with cols[i % 3]:
                if st.button(f"✕ {tag}", key=f"del_tag_{i}", use_container_width=True):
                    song["tags"].remove(tag)
                    update_song_tags(song["row"], song["tags"])
                    reload_songs()
                    st.rerun()
    
    nt = st.text_input("Dodaj własny tag:", key="new_tag_input")
    if st.button("Dodaj tag", key="add_tag_btn"):
        if nt and nt not in current_tags:
            song["tags"].append(nt)
            update_song_tags(song["row"], song["tags"])
            reload_songs()
            st.rerun()

# ------------------------------
# 9. PANEL ADMIN
# ------------------------------
with st.expander("🛠️ Panel Administracyjny"):
    tab_edit, tab_add, tab_del = st.tabs(["✏️ Edytuj bieżący", "➕ Dodaj piosenkę", "🗑️ Usuń"])
    
    with tab_edit:
        curr_id = st.session_state.current_idx
        
        et = st.text_input("Tytuł:", value=song["title"], key=f"edit_title_{curr_id}")
        
        el = [f"{l['text']} | {' '.join(l.get('chords', []))}" for l in song["lyrics"]]
        nc = st.text_area("Treść (Tekst | Chwyty):", value="\n".join(el), height=200, key=f"edit_area_{curr_id}")
        
        if st.button("Zapisz zmiany", key=f"btn_save_edit_{curr_id}"):
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
        st.subheader("Nowa piosenka")
        new_t = st.text_input("Tytuł piosenki:", key="add_new_title")
        new_l = st.text_area("Treść (Format: Tekst | Chwyty):", 
                            placeholder="Wpisz tekst piosenki...\nMożesz dodać chwyty po kresce |", 
                            height=200, key="add_new_area")
        if st.button("Dodaj do biblioteki", key="btn_add_new_song"):
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

