import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
import random
import re
from collections import Counter
import pandas as pd

# ---------------------------------------------------------
# 1. KONFIGURACJA STRONY (Musi być pierwsza)
# ---------------------------------------------------------
st.set_page_config(
    layout="wide", 
    page_title="Śpiewnik",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# 2. CSS - KLUCZOWE DLA RESPONSYWNOŚCI
# ---------------------------------------------------------
st.markdown("""
<style>
    /* Ogólne tło */
    [data-testid="stAppViewContainer"] { background-color: #0e1117; }
    [data-testid="stSidebar"] { background-color: #010409; }
    
    /* Stylizacja tytułu */
    .song-title {
        font-weight: bold;
        color: #ffffff;
        text-align: center;
        line-height: 1.1;
        font-size: 34px !important;
        margin-bottom: 10px !important;
    }

    /* Wiersze z tekstem piosenki */
    .song-row {
        display: flex;
        justify-content: flex-start;
        align-items: baseline;
        gap: 20px;
        margin-bottom: 0px !important;
    }
    .lyrics-col { flex: 0 0 auto; min-width: 150px; font-size: 16px; color: #eee; }
    .chords-col { color: #ff4b4b !important; font-weight: bold; font-size: 16px; }

    /* Buttony w sidebarze */
    [data-testid="stSidebar"] div.stButton > button:first-child {
        font-size: 10px !important;
        padding: 2px 4px !important;
        background-color: #1f2937 !important;
        color: #ffffff !important;
        border: 1px solid #4b5563 !important;
    }

    /* --- RESPONSIVE LOGIC (BEZWZGLĘDNE UKRYWANIE) --- */
    
    /* Domyślnie (Mobile First) */
    .desktop-only { display: none !important; }
    .mobile-only { display: block !important; }

    /* Ekrany większe niż 800px (Desktop/Tablet) */
    @media (min-width: 801px) {
        .desktop-only { display: block !important; }
        .mobile-only { display: none !important; }
        
        /* Zwiększ czcionkę tytułu na dużym ekranie */
        .song-title { font-size: 38px !important; }
    }

    /* Ekrany mniejsze (Mobile) */
    @media (max-width: 800px) {
        .song-title { font-size: 24px !important; margin-top: 5px; margin-bottom: 15px; }
        /* Mniejsze paddingi w expanderach na mobile */
        div[data-testid="stExpander"] button {
            font-size: 13px !important;
            padding: 4px !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. POŁĄCZENIE Z GOOGLE SHEETS
# ---------------------------------------------------------

def init_gsheet():
    """Inicjalizacja połączenia z Google Sheets"""
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Brak konfiguracji 'gcp_service_account' w secrets.toml")
            return None
            
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

ws = init_gsheet()

# ---------------------------------------------------------
# 4. FUNKCJE LOGIKI (ŁADOWANIE/ZAPIS)
# ---------------------------------------------------------

def load_songs_from_sheets():
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
                        lyrics_json = json.loads(lyrics_raw)
                        for item in lyrics_json:
                            if isinstance(item, dict):
                                text = item.get("text", "").strip()
                                chords = item.get("chords", [])
                                if isinstance(chords, str):
                                    chords = chords.split()
                                lyrics.append({"text": text, "chords": chords})
                    except:
                        lyrics.append({"text": lyrics_raw, "chords": []})
                else:
                    for line in lyrics_raw.split("\n"):
                        if "|" in line:
                            parts = line.split("|", 1)
                            lyrics.append({
                                "text": parts[0].strip(),
                                "chords": parts[1].strip().split() if parts[1].strip() else []
                            })
                        else:
                            lyrics.append({"text": line.strip(), "chords": []})
                
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                songs.append({
                    "title": title, "lyrics": lyrics, "ratings_sum": ratings_sum,
                    "ratings_count": ratings_count, "tags": tags, "row": i
                })
        return songs
    except Exception as e:
        st.error(f"Błąd podczas ładowania: {e}")
        return []

def save_song_to_sheets(row_idx, title, lyrics, ratings_sum, ratings_count, tags):
    if not ws: return False
    try:
        lyrics_str = "\n".join([f"{l['text']} | {' '.join(l.get('chords', []))}" for l in lyrics])
        tags_str = ", ".join(tags)
        ws.update([[title, lyrics_str, str(ratings_sum), str(ratings_count), tags_str]], f"A{row_idx}:E{row_idx}", raw=False)
        return True
    except Exception as e: st.error(f"Błąd zapisu: {e}"); return False

def add_song_to_sheets(title, lyrics, ratings_sum=0, ratings_count=0, tags=[]):
    if not ws: return False
    try:
        lyrics_str = "\n".join([f"{l['text']} | {' '.join(l.get('chords', []))}" for l in lyrics])
        tags_str = ", ".join(tags)
        ws.append_row([title, lyrics_str, str(ratings_sum), str(ratings_count), tags_str])
        return True
    except Exception as e: st.error(f"Błąd dodawania: {e}"); return False

def delete_song_from_sheets(row_idx):
    if not ws: return False
    try: ws.delete_rows(row_idx); return True
    except Exception as e: st.error(f"Błąd usuwania: {e}"); return False

def update_song_tags(row_idx, tags):
    if not ws: return False
    try: ws.update([[", ".join(tags)]], f"E{row_idx}"); return True
    except Exception as e: st.error(f"Błąd tagów: {e}"); return False

def update_song_ratings(row_idx, ratings_sum, ratings_count):
    if not ws: return False
    try: ws.update([[str(ratings_sum), str(ratings_count)]], f"C{row_idx}"); return True
    except Exception as e: st.error(f"Błąd ocen: {e}"); return False

# ---------------------------------------------------------
# 5. ZMIENNE I POMOCNICZE
# ---------------------------------------------------------

ADMIN_PIN = "1234"

RATING_TAGS = {
    1: ["Nie lubię", "Nie graj", "Żenada", "Pomiń", "Trudne", "Słabe", "Nudne"],
    2: ["Później", "Kiedyś", "Nie teraz", "Ćwiczyć", "Średnie", "Zapomnij"],
    3: ["Zagraj", "OK", "Niezła", "Ognisko", "Spokojna", "Klasyk", "Może być"],
    4: ["Następne", "Ładna", "Polecam", "Częściej", "Wpadająca", "Energia", "Na start"],
    5: ["HIT", "Koniecznie", "Ulubiona", "TOP", "Mistrz", "Hymn", "Wszyscy", "Legenda"]
}

STOPWORDS = {"się", "i", "w", "z", "na", "do", "że", "o", "a", "to", "jak", "nie", "co", "mnie", "mi", "ci", "za", "ale", "bo", "jest", "tylko", "przez", "jeszcze", "kiedy", "już", "dla", "od", "ten", "ta"}

def get_keywords(songs_list, source="lyrics", limit=40):
    all_words = []
    for s in songs_list:
        text = " ".join([l["text"] for l in s["lyrics"]]).lower() if source == "lyrics" else s["title"].lower()
        words = re.findall(r'\b\w{4,}\b', text)
        all_words.extend([w for w in words if w not in STOPWORDS])
    most_common = Counter(all_words).most_common(limit)
    return most_common if most_common else []

def get_best_songs_all_time(songs):
    if not songs: return None
    best = max(songs, key=lambda x: x["ratings_sum"] / x["ratings_count"] if x["ratings_count"] > 0 else 0)
    return best["title"] if best["ratings_count"] > 0 else None

def get_most_common_tags(songs, limit=10):
    all_tags = []
    for song in songs: all_tags.extend(song.get("tags", []))
    if not all_tags: return []
    return [t[0] for t in Counter(all_tags).most_common(limit)]

def get_most_visited_songs(songs, limit=10):
    rated_songs = [s for s in songs if s["ratings_count"] > 0]
    return sorted(rated_songs, key=lambda x: x["ratings_count"], reverse=True)[:limit]

def transpose_chord(chord, steps):
    D = ["C","Cis","D","Dis","E","F","Fis","G","Gis","A","B","H"]
    m = ["c","cis","d","dis","e","f","fis","g","gis","a","b","h"]
    match = re.match(r"^([A-H][is]*|[a-h][is]*)(.*)$", chord)
    if match:
        base, suffix = match.groups()
        if base in D: return D[(D.index(base) + steps) % 12] + suffix
        if base in m: return m[(m.index(base) + steps) % 12] + suffix
    return chord

def reload_songs():
    st.session_state.songs = load_songs_from_sheets()

# ---------------------------------------------------------
# 6. STAN SESJI
# ---------------------------------------------------------

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
    if st.session_state.songs:
        st.session_state.current_idx = idx % len(st.session_state.songs)
        st.session_state.transposition = 0

def render_expandable_cloud(items, key_prefix, on_click_action, initial_count=8):
    state_key = f"expanded_{key_prefix}"
    if state_key not in st.session_state: st.session_state[state_key] = False
    is_expanded = st.session_state[state_key]
    
    if len(items) <= initial_count:
        visible_items = items; needs_toggle = False
    else:
        visible_items = items if is_expanded else items[:initial_count]; needs_toggle = True

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

# ---------------------------------------------------------
# 7. SIDEBAR (Z PRZYWRÓCONYMI CHMURAMI TAGÓW)
# ---------------------------------------------------------

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
    
    # CHMURA: Wszystkie Tagi
    st.caption("WSZYSTKIE TAGI")
    all_tags = []
    for song in st.session_state.songs: all_tags.extend(song.get("tags", []))
    if all_tags:
        common_tags = [t[0] for t in Counter(all_tags).most_common(50)]
        render_expandable_cloud(common_tags, "side_tags", 
            lambda t: (set_song_by_idx(random.choice([j for j, s in enumerate(st.session_state.songs) if t in s.get("tags", [])])), st.rerun())[1], 
            initial_count=6)
    else:
        st.caption("Brak.")

    st.markdown("---")
    
    # CHMURA: Słowa z tekstu
    st.caption("Z TEKSTU")
    if st.session_state.kw_lyrics:
        render_expandable_cloud([w[0] for w in st.session_state.kw_lyrics], "side_l", 
            lambda w: (set_song_by_idx(random.choice([j for j, s in enumerate(st.session_state.songs) if w in " ".join([l["text"] for l in s["lyrics"]]).lower()])), st.rerun())[1], 
            initial_count=9)

    st.markdown("---")
    
    # CHMURA: Słowa z tytułów
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

# ---------------------------------------------------------
# 8. GŁÓWNY WIDOK
# ---------------------------------------------------------

if not st.session_state.songs:
    st.warning("Baza piosenek jest pusta.")
    st.stop()

song = st.session_state.songs[st.session_state.current_idx]

# =========================================================
# A. WIDOK DESKTOPOWY (Góra)
# Ukryty na mobile (klasa .desktop-only)
# =========================================================
st.markdown('<div class="desktop-only">', unsafe_allow_html=True)
c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1, 1, 1, 10, 1, 1, 1, 1])
with c1:
    if st.button("⬅️", key="d_prev"):
        set_song_by_idx(st.session_state.current_idx - 1); st.rerun()
with c2:
    if st.button("🎲", key="d_rand"):
        set_song_by_idx(random.randint(0, len(st.session_state.songs)-1)); st.rerun()
with c3:
    if st.button("🆕", key="d_last"):
        set_song_by_idx(len(st.session_state.songs)-1); st.rerun()
with c4:
    st.markdown(f'<div class="song-title">{song["title"]}</div>', unsafe_allow_html=True)
with c5:
    if st.button("➖", key="d_t_down"):
        st.session_state.transposition -= 1; st.rerun()
with c6:
    st.markdown(f'<div style="text-align:center; color:#ff4b4b; font-weight:bold; padding-top:5px;">{st.session_state.transposition:+}</div>', unsafe_allow_html=True)
with c7:
    if st.button("➕", key="d_t_up"):
        st.session_state.transposition += 1; st.rerun()
with c8:
    if st.button("➡️", key="d_next"):
        set_song_by_idx(st.session_state.current_idx + 1); st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# B. WIDOK MOBILNY (Tytuł góra)
# Ukryty na desktop (klasa .mobile-only)
# =========================================================
st.markdown(f'<div class="mobile-only"><div class="song-title">{song["title"]}</div></div>', unsafe_allow_html=True)

# =========================================================
# C. TEKST PIOSENKI (Zawsze widoczny)
# =========================================================
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

# =========================================================
# D. WIDOK MOBILNY (Sterowanie dół)
# Ukryty na desktop (klasa .mobile-only)
# =========================================================
st.markdown('<div class="mobile-only">', unsafe_allow_html=True)
st.markdown('<hr style="margin: 15px 0 10px 0; opacity: 0.3;">', unsafe_allow_html=True)
st.caption("🎹 Panel Sterowania")

# Transpozycja Mobile
col_tm1, col_tm2, col_tm3 = st.columns([1, 1, 1])
with col_tm1:
    if st.button("➖ Ton", key="m_t_down", use_container_width=True):
        st.session_state.transposition -= 1; st.rerun()
with col_tm2:
    st.markdown(f'<div style="text-align:center; color:#ff4b4b; font-weight:bold; padding-top: 8px; font-size: 18px;">{st.session_state.transposition:+}</div>', unsafe_allow_html=True)
with col_tm3:
    if st.button("➕ Ton", key="m_t_up", use_container_width=True):
        st.session_state.transposition += 1; st.rerun()

# Nawigacja Mobile
col_nm1, col_nm2, col_nm3, col_nm4 = st.columns(4)
with col_nm1:
    if st.button("⬅️", key="m_prev", use_container_width=True):
        set_song_by_idx(st.session_state.current_idx - 1); st.rerun()
with col_nm2:
    if st.button("🎲", key="m_rand", use_container_width=True):
        set_song_by_idx(random.randint(0, len(st.session_state.songs)-1)); st.rerun()
with col_nm3:
    if st.button("🆕", key="m_last", use_container_width=True):
        set_song_by_idx(len(st.session_state.songs)-1); st.rerun()
with col_nm4:
    if st.button("➡️", key="m_next", use_container_width=True):
        set_song_by_idx(st.session_state.current_idx + 1); st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# E. OCENY, TAGI (Wspólne)
# =========================================================
st.markdown('<hr style="margin: 15px 0 15px 0; opacity: 0.2;">', unsafe_allow_html=True)

st.subheader("⭐ Oceń tę piosenkę")
col_v1, col_v2 = st.columns([2, 1])
with col_v1:
    avg = song["ratings_sum"] / song["ratings_count"] if song["ratings_count"] > 0 else 0
    st.write(f"Średnia: **{avg:.1f}** ({song['ratings_count']} gł.)")
    score = st.radio("Twoja ocena:", [1,2,3,4,5], horizontal=True, key="rating_radio")
    if st.button("Zapisz ocenę", key="save_rate", use_container_width=True):
        if update_song_ratings(song["row"], song["ratings_sum"]+score, song["ratings_count"]+1):
            st.success("Zapisano!"); reload_songs(); st.rerun()

# CHMURA: Sugestie po ocenie
if score in RATING_TAGS:
    st.caption("Sugerowane tagi:")
    render_expandable_cloud(RATING_TAGS[score], f"sug_{score}", 
        lambda t: (song["tags"].append(t) or update_song_tags(song["row"], song["tags"]) or reload_songs() or st.rerun()) 
        if t not in song.get("tags", []) else None, initial_count=8)

st.markdown("---")

st.subheader("🏷️ Tagi")
most_common_tags = get_most_common_tags(st.session_state.songs, limit=3)
suggested_tags_state = "show_all_tags"

# Szybkie tagi
cols = st.columns(len(most_common_tags) + 1) if most_common_tags else []
for i, tag in enumerate(most_common_tags):
    with cols[i]:
        if st.button(tag, key=f"q_tag_{i}", use_container_width=True):
            if tag not in song.get("tags", []):
                song["tags"].append(tag); update_song_tags(song["row"], song["tags"]); reload_songs(); st.rerun()
            else: st.info("Już jest")

# Przycisk Więcej/Mniej
if len(most_common_tags) > 0:
    with cols[-1]:
        if st.session_state.get(suggested_tags_state, False):
            if st.button("Mniej ▲", key="hide_tags", use_container_width=True):
                st.session_state[suggested_tags_state] = False; st.rerun()
        else:
            if st.button("Więcej ▼", key="show_tags", use_container_width=True):
                st.session_state[suggested_tags_state] = True; st.rerun()

# CHMURA: Wszystkie dostępne tagi (rozwijana)
if st.session_state.get(suggested_tags_state, False):
    st.caption("Wszystkie tagi:")
    all_tags_list = get_most_common_tags(st.session_state.songs, limit=50)
    render_expandable_cloud(all_tags_list, "all_tags_cloud",
        lambda t: (song["tags"].append(t) or update_song_tags(song["row"], song["tags"]) or reload_songs() or st.rerun())
        if t not in song.get("tags", []) else None, initial_count=12)

st.caption("Przypisane:")
current_tags = song.get("tags", [])
if current_tags:
    cols = st.columns(3)
    for i, tag in enumerate(current_tags):
        with cols[i % 3]:
            if st.button(f"✕ {tag}", key=f"d_tag_{i}", use_container_width=True):
                song["tags"].remove(tag); update_song_tags(song["row"], song["tags"]); reload_songs(); st.rerun()
else: st.info("Brak")

nt = st.text_input("Nowy tag:", key="new_tag_input")
if st.button("Dodaj", key="add_tag_btn", use_container_width=True):
    if nt and nt not in current_tags:
        song["tags"].append(nt); update_song_tags(song["row"], song["tags"]); reload_songs(); st.rerun()

st.markdown("---")

# =========================================================
# F. POLECANE I ADMIN
# =========================================================
st.subheader("📚 Polecane")
c_rec1, c_rec2 = st.columns(2)
with c_rec1:
    if st.button("🔄 Losowe", key="ref_rnd", use_container_width=True):
        st.session_state.random_sample = random.sample(st.session_state.songs, min(5, len(st.session_state.songs))); st.rerun()
    for i, rs in enumerate(st.session_state.random_sample):
        if st.button(rs["title"], key=f"r_{i}", use_container_width=True):
            set_song_by_idx(next((j for j, s in enumerate(st.session_state.songs) if s["title"] == rs["title"]), 0)); st.rerun()
with c_rec2:
    ba = get_best_songs_all_time(st.session_state.songs)
    if ba:
        if st.button(f"🏆 TOP: {ba}", key="top_song_btn", use_container_width=True):
            set_song_by_idx(next((i for i, s in enumerate(st.session_state.songs) if s["title"] == ba), 0)); st.rerun()

st.markdown("---")
with st.expander("🛠️ Admin"):
    tab_edit, tab_add, tab_del, tab_stats = st.tabs(["Edycja", "Dodaj", "Usuń", "Stats"])
    
    with tab_edit:
        et = st.text_input("Tytuł:", value=song["title"], key="ed_t")
        el = [f"{l['text']} | {' '.join(l.get('chords', []))}" for l in song["lyrics"]]
        nc = st.text_area("Treść:", value="\n".join(el), height=200, key="ed_c")
        if st.button("Zapisz", key="save_ed", use_container_width=True):
            nl = []
            for line in nc.split("\n"):
                p = line.split("|", 1)
                nl.append({"text": p[0].strip(), "chords": p[1].strip().split() if len(p)>1 and p[1].strip() else []})
            if save_song_to_sheets(song["row"], et, nl, song["ratings_sum"], song["ratings_count"], song["tags"]):
                st.success("OK"); reload_songs(); st.rerun()

    with tab_add:
        nt = st.text_input("Tytuł:", key="add_t")
        nl = st.text_area("Treść:", placeholder="Tekst | C G a F", height=200, key="add_c")
        if st.button("Dodaj", key="btn_add", use_container_width=True):
            if nt and nl:
                pl = []
                for line in nl.split("\n"):
                    p = line.split("|", 1)
                    pl.append({"text": p[0].strip(), "chords": p[1].strip().split() if len(p)>1 and p[1].strip() else []})
                if add_song_to_sheets(nt, pl):
                    st.success("OK"); reload_songs(); st.session_state.current_idx = len(st.session_state.songs) - 1; st.rerun()

    with tab_del:
        if st.text_input("PIN", type="password", key="del_pin") == ADMIN_PIN:
            st.warning(f"Usuwasz: {song['title']}")
            if st.button("USUŃ", type="primary", use_container_width=True):
                if delete_song_from_sheets(song["row"]):
                    st.success("OK"); reload_songs(); set_song_by_idx(0); st.rerun()

    with tab_stats:
        c1, c2, c3 = st.columns(3)
        c1.metric("Piosenki", len(st.session_state.songs))
        c2.metric("Oceny", sum(s["ratings_count"] for s in st.session_state.songs))
        avg = sum(s["ratings_sum"] for s in st.session_state.songs) / max(sum(s["ratings_count"] for s in st.session_state.songs), 1)
        c3.metric("Średnia", f"{avg:.2f}")
        st.caption("Top 5 odwiedzin:")
        for s in get_most_visited_songs(st.session_state.songs, 5):
            st.write(f"- {s['title']} ({s['ratings_count']})")
