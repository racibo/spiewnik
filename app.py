import streamlit as st
import json
import random
import re
from collections import Counter

# ------------------------------
# 1. Konfiguracja i Style
# ------------------------------
st.set_page_config(
    layout="wide", 
    page_title="Śpiewnik Pro",
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
    .mobile-nav { display: none; } /* Domyślnie ukryte */

    @media (max-width: 800px) {
        /* Na telefonie ukrywamy górne kolumny przycisków */
        div[data-testid="column"]:has(button[key*="nav_"]) {
            display: none !important;
        }
        /* Pokazujemy dolny pasek nawigacji */
        .mobile-nav { 
            display: flex !important; 
            flex-wrap: nowrap; 
            justify-content: center; 
            gap: 5px; 
            padding: 10px 0;
            border-top: 1px solid #333;
        }
        .song-title { font-size: 20px !important; }
        
        /* Zmniejszenie tagów pod piosenką (Sekcja 9) */
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

# ------------------------------
# 2. Funkcje danych
# ------------------------------
def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return default

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_best_songs_all_time(ratings):
    if not ratings: return None
    best = max(ratings.items(), key=lambda x: x[1]["sum"]/x[1]["count"] if x[1]["count"]>0 else 0)
    return best[0]

def get_best_songs_week(ratings):
    if not ratings: return None
    best = max(ratings.items(), key=lambda x: x[1]["sum"]/x[1]["count"] if x[1]["count"]>0 else 0)
    return best[0]

def get_best_songs_today(ratings):
    if not ratings: return None
    best = max(ratings.items(), key=lambda x: x[1]["sum"]/x[1]["count"] if x[1]["count"]>0 else 0)
    return best[0]

def get_newest_song(songs):
    if not songs: return None
    return songs[-1]["title"]

songs = load_json("songs.json", [])
ratings = load_json("ratings.json", {}) 
user_tags = load_json("user_tags.json", {})

# ------------------------------
# 3. Logika Analizy
# ------------------------------
STOPWORDS = {"się", "i", "w", "z", "na", "do", "że", "o", "a", "to", "jak", "nie", "co", "mnie", "mi", "ci", "za", "ale", "bo", "jest", "tylko", "przez", "jeszcze", "kiedy", "już", "dla", "od", "ten", "ta"}

def get_keywords(songs_list, source="lyrics", limit=40):
    all_words = []
    for s in songs_list:
        text = " ".join([l["text"] for l in s["lyrics"] if "<br>" not in l["text"]]).lower() if source == "lyrics" else s["title"].lower()
        words = re.findall(r'\b\w{4,}\b', text)
        all_words.extend([w for w in words if w not in STOPWORDS])
    most_common = Counter(all_words).most_common(limit)
    return most_common if most_common else []

# ------------------------------
# 4. Stan aplikacji
# ------------------------------
if "current_idx" not in st.session_state:
    st.session_state.current_idx = random.randint(0, len(songs) - 1) if songs else 0
if "transposition" not in st.session_state: st.session_state.transposition = 0
if "kw_lyrics" not in st.session_state: st.session_state.kw_lyrics = get_keywords(songs, "lyrics")
if "kw_titles" not in st.session_state: st.session_state.kw_titles = get_keywords(songs, "title")
if "random_sample" not in st.session_state:
    st.session_state.random_sample = random.sample(songs, min(5, len(songs))) if songs else []

def set_song_by_idx(idx):
    if songs:
        st.session_state.current_idx = idx % len(songs)
        st.session_state.transposition = 0

# ------------------------------
# 5. RENDEROWANIE CHMURY TAGÓW
# ------------------------------
def render_expandable_cloud(items, key_prefix, on_click_action, initial_count=8):
    state_key = f"expanded_{key_prefix}"
    if state_key not in st.session_state: st.session_state[state_key] = False
    is_expanded = st.session_state[state_key]
    
    if len(items) <= initial_count:
        visible_items = items; needs_toggle = False
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
                st.session_state[state_key] = not st.session_state[state_key]; st.rerun()

# ------------------------------
# 6. SIDEBAR
# ------------------------------
with st.sidebar:
    st.title("Biblioteka")
    
    query = st.text_input("Szukaj:", placeholder="Tytuł...", key="main_search_input").lower()
    if query:
        found = [i for i, s in enumerate(songs) if query in (s["title"] + " " + " ".join([l["text"] for l in s["lyrics"]])).lower()]
        if found:
            sel = st.selectbox("Wyniki:", [songs[i]['title'] for i in found], key="search_results_select")
            if st.button("Idź", key="go_to_search_result"): 
                set_song_by_idx(found[[songs[i]['title'] for i in found].index(sel)])
                st.rerun()

    st.markdown("---")
    
    st.caption("TWOJE TAGI")
    all_ut_list = []
    for t_list in user_tags.values(): all_ut_list.extend(t_list)
    if all_ut_list:
        common_tags = [t[0] for t in Counter(all_ut_list).most_common(50)]
        render_expandable_cloud(common_tags, "side_ut", lambda t: (set_song_by_idx(random.choice([j for j, s in enumerate(songs) if t in user_tags.get(s["title"], [])])), st.rerun())[1], initial_count=6)
    else: st.caption("Brak.")

    st.markdown("---")
    st.caption("Z TEKSTU")
    if st.session_state.kw_lyrics:
        render_expandable_cloud([w[0] for w in st.session_state.kw_lyrics], "side_l", lambda w: (set_song_by_idx(random.choice([j for j, s in enumerate(songs) if w in " ".join([l["text"] for l in s["lyrics"]]).lower()])), st.rerun())[1], initial_count=9)

    st.markdown("---")
    st.caption("Z TYTUŁÓW")
    if st.session_state.kw_titles:
        render_expandable_cloud([w[0] for w in st.session_state.kw_titles], "side_t", lambda w: (set_song_by_idx(random.choice([j for j, s in enumerate(songs) if w in s["title"].lower()])), st.rerun())[1], initial_count=6)
    
    st.markdown("---")
    # To jest JEDYNY przycisk o tym kluczu w całym pliku:
    if st.button("Odśwież bazę", key="refresh_sidebar", use_container_width=True):
        st.session_state.kw_lyrics = get_keywords(songs, "lyrics")
        st.session_state.kw_titles = get_keywords(songs, "title")
        st.rerun()

# ------------------------------
# 7. LOGIKA I NAGŁÓWEK (WSZYSTKO W JEDNEJ LINII)
# ------------------------------
if not songs: 
    st.warning("Baza piosenek jest pusta.")
    st.stop()

# Najpierw definiujemy piosenkę
song = songs[st.session_state.current_idx]

# Potem rysujemy kompaktowy nagłówek
# Nowe proporcje: tytuł (c4) dostaje więcej miejsca, reszta jest ciasna
# Górna linia (widoczna głównie na PC)
c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1, 1, 1, 10, 1, 1, 1, 1])
with c1: st.button("⬅️", key="nav_prev", on_click=lambda: set_song_by_idx(st.session_state.current_idx - 1))
with c2: st.button("🎲", key="nav_rand", on_click=lambda: set_song_by_idx(random.randint(0, len(songs)-1)))
with c3: st.button("🆕", key="nav_last", on_click=lambda: set_song_by_idx(len(songs)-1))
with c4: st.markdown(f'<div class="song-title">{song["title"]}</div>', unsafe_allow_html=True)
with c5: st.button("➖", key="nav_t_down", on_click=lambda: exec('st.session_state.transposition -= 1'))
with c6: st.markdown(f'<div style="text-align:center; color:#ff4b4b; font-weight:bold;">{st.session_state.transposition:+}</div>', unsafe_allow_html=True)
with c7: st.button("➕", key="nav_t_up", on_click=lambda: exec('st.session_state.transposition += 1'))
with c8: st.button("➡️", key="nav_next", on_click=lambda: set_song_by_idx(st.session_state.current_idx + 1))
st.markdown('<hr style="margin: 5px 0 15px 0; opacity: 0.2;">', unsafe_allow_html=True)# ------------------------------
# 8. TREŚĆ UTWORU
# ------------------------------
def transpose_chord(chord, steps):
    D = ["C","Cis","D","Dis","E","F","Fis","G","Gis","A","B","H"]
    m = ["c","cis","d","dis","e","f","fis","g","gis","a","b","h"]
    match = re.match(r"^([A-H][is]*|[a-h][is]*)(.*)$", chord)
    if match:
        base, suffix = match.groups()
        if base in D: return D[(D.index(base) + steps) % 12] + suffix
        if base in m: return m[(m.index(base) + steps) % 12] + suffix
    return chord

st.markdown('<hr style="margin: 5px 0 15px 0; opacity: 0.2;">', unsafe_allow_html=True)

html = '<div class="song-container">'
for l in song["lyrics"]:
    # Pomijamy znaczniki techniczne
    if "<br>" in l["text"] or "---" in l["text"]: 
        continue
        
    clean_text = l["text"].strip()
    # Transpozycja chwytów
    chds = [transpose_chord(c, st.session_state.transposition) for c in l.get("chords", [])]
    c_str = " ".join(chds)
    
    # Renderujemy wiersz jeśli nie jest pusty
    if clean_text or chds: 
        html += f'<div class="song-row"><div class="lyrics-col">{clean_text or "&nbsp;"}</div><div class="chords-col">{c_str or "&nbsp;"}</div></div>'
    else:
        # Odstęp między zwrotkami
        html += '<div style="height: 12px;"></div>' 

st.markdown(html + '</div>', unsafe_allow_html=True)
# --- DODATKOWA NAWIGACJA MOBILNA (POD TEKSTEM) ---
st.markdown('<div class="mobile-nav">', unsafe_allow_html=True)
mb1, mb2, mb3, mb4, mb5, mb6, mb7 = st.columns([1,1,1,1,1,1,1])
with mb1: st.button("⬅️", key="m_prev", on_click=lambda: set_song_by_idx(st.session_state.current_idx - 1))
with mb2: st.button("🎲", key="m_rand", on_click=lambda: set_song_by_idx(random.randint(0, len(songs)-1)))
with mb3: st.button("🆕", key="m_last", on_click=lambda: set_song_by_idx(len(songs)-1))
with mb4: st.button("➖", key="m_t_down", on_click=lambda: exec('st.session_state.transposition -= 1'))
with mb5: st.markdown(f'<div style="color:#ff4b4b; text-align:center;">{st.session_state.transposition:+}</div>', unsafe_allow_html=True)
with mb6: st.button("➕", key="m_t_up", on_click=lambda: exec('st.session_state.transposition += 1'))
with mb7: st.button("➡️", key="m_next", on_click=lambda: set_song_by_idx(st.session_state.current_idx + 1))
st.markdown('</div>', unsafe_allow_html=True)
# --- PODMIEŃ CAŁĄ SEKCJĘ 9 ---
st.markdown('<hr style="margin: 30px 0 10px 0; opacity: 0.2;">', unsafe_allow_html=True)

# SEKCJA POLECANE (Teraz na górze, bez zakładki)
st.subheader("📚 Polecane utwory")
c_rec1, c_rec2 = st.columns(2)
with c_rec1:
    st.caption("Losowe propozycje:")
    # Zmieniona nazwa przycisku na "Odśwież listę"
    if st.button("🔄 Odśwież listę", key="ref_rnd", use_container_width=True): 
        st.session_state.random_sample = random.sample(songs, min(5, len(songs)))
        st.rerun()
    for i, rs in enumerate(st.session_state.random_sample):
        if st.button(rs["title"], key=f"r_{i}", use_container_width=True): 
            set_song_by_idx(next((j for j, s in enumerate(songs) if s["title"] == rs["title"]), 0))
            st.rerun()
with c_rec2:
    st.caption("Najlepiej oceniane (TOP):")
    ba = get_best_songs_all_time(ratings)
    if ba:
        if st.button(f"🏆 {ba}", key="top_song_btn", use_container_width=True): 
            set_song_by_idx(next((i for i, s in enumerate(songs) if s["title"] == ba), 0))
            st.rerun()
    else:
        st.write("Brak ocen.")

st.markdown("---")

# OCENY I TAGI (W zakładkach pod polecanymi)
tab_vote, tab_tags = st.tabs(["⭐ Oceń tę piosenkę", "🏷️ Tagi użytkownika"])

with tab_vote:
    col_v1, col_v2 = st.columns([2, 1])
    with col_v1:
        stats = ratings.get(song["title"], {"sum": 0, "count": 0})
        avg = stats["sum"]/stats["count"] if stats["count"]>0 else 0
        st.write(f"Średnia ocena: **{avg:.1f}**")
        score = st.radio("Twoja ocena:", [1,2,3,4,5], horizontal=True, key="rating_radio")
        if st.button("Zapisz ocenę", key="btn_zapisz_ocene_main"):
            stats["sum"] += score; stats["count"] += 1; ratings[song["title"]] = stats
            save_json("ratings.json", ratings)
            st.rerun()
    if score in RATING_TAGS:
        st.caption("Sugerowane tagi:")
        render_expandable_cloud(RATING_TAGS[score], f"sug_tag_{score}", lambda t: (user_tags.setdefault(song["title"], []).append(t) or save_json("user_tags.json", user_tags) or st.rerun()) if t not in user_tags.get(song["title"], []) else None, initial_count=8)

with tab_tags:
    current_ut = user_tags.get(song["title"], [])
    if current_ut:
        cols = st.columns(2)
        for i, tag in enumerate(current_ut):
            with cols[i%3]:
                if st.button(f"✕ {tag}", key=f"del_tag_{i}", use_container_width=True):
                    current_ut.remove(tag); user_tags[song["title"]] = current_ut; save_json("user_tags.json", user_tags); st.rerun()
    
    nt = st.text_input("Dodaj własny tag:", key="new_tag_input")
    if st.button("Dodaj tag", key="add_tag_btn"):
        if nt and nt not in current_ut:
            current_ut.append(nt); user_tags[song["title"]] = current_ut; save_json("user_tags.json", user_tags); st.rerun()
# ------------------------------
# 10. PANEL ADMIN (Edycja i Dodawanie)
# ------------------------------
with st.expander("🛠️ Panel Administracyjny"):
    tab_edit, tab_add, tab_del = st.tabs(["📝 Edytuj bieżący", "➕ Dodaj piosenkę", "🗑️ Usuń"])
    
    with tab_edit:
        # Dodajemy indeks do klucza, aby wymusić odświeżenie danych przy zmianie piosenki
        curr_id = st.session_state.current_idx 
        
        et = st.text_input("Tytuł:", value=song["title"], key=f"edit_title_{curr_id}")
        
        el = [f"{l['text']} | {' '.join(l.get('chords', []))}" for l in song["lyrics"] if "<br>" not in l["text"]]
        nc = st.text_area("Treść (Tekst | Chwyty):", value="\n".join(el), height=200, key=f"edit_area_{curr_id}")
        
        if st.button("Zapisz zmiany", key=f"btn_save_edit_{curr_id}"):
            nl = []
            for line in nc.split("\n"):
                p = line.split("|")
                nl.append({"text": p[0].strip(), "chords": p[1].strip().split()} if len(p)>1 else {"text": line.strip(), "chords": []})
            
            songs[st.session_state.current_idx] = {"title": et, "lyrics": nl}
            save_json("songs.json", songs)
            st.success("Zmiany zapisane!") # Dodatkowe potwierdzenie
            st.rerun()

    with tab_add:
        st.subheader("Nowa piosenka")
        new_t = st.text_input("Tytuł piosenki:", key="add_new_title")
        new_l = st.text_area("Treść (Format: Tekst | Chwyty):", placeholder="Wpisz tekst piosenki...\nMożesz dodać chwyty po kresce |", height=200, key="add_new_area")
        if st.button("Dodaj do biblioteki", key="btn_add_new_song"):
            if new_t and new_l:
                parsed_lyrics = []
                for line in new_l.split("\n"):
                    parts = line.split("|")
                    parsed_lyrics.append({"text": parts[0].strip(), "chords": parts[1].strip().split() if len(parts)>1 else []})
                songs.append({"title": new_t, "lyrics": parsed_lyrics})
                save_json("songs.json", songs)
                st.success(f"Dodano: {new_t}")
                set_song_by_idx(len(songs)-1); st.rerun()
            else:
                st.error("Podaj tytuł i treść!")

    with tab_del:
        if st.text_input("PIN blokady", type="password", key="del_pin") == ADMIN_PIN:
            if st.button("POTWIERDZAM USUNIĘCIE", type="primary", use_container_width=True):
                songs.pop(st.session_state.current_idx)
                save_json("songs.json", songs)
                set_song_by_idx(0); st.rerun()
