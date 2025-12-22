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
        /* Główne tło */
        [data-testid="stAppViewContainer"] { background-color: #0e1117; }
        [data-testid="stSidebar"] { background-color: #010409; }
        
        /* Kontener główny - marginesy */
        .main .block-container { 
            padding-top: 1rem !important; 
            padding-bottom: 3rem; 
            max-width: 100%; 
            padding-left: 1rem;
            padding-right: 1rem;
        }
        
        /* TYTUŁ I NAWIGACJA */
        .song-title { 
            font-size: 24px !important; 
            font-weight: bold; 
            margin: 0 !important; 
            line-height: 1.5; 
            color: #fff; 
            text-align: center;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        /* UKŁAD WIERSZA (Tekst + Chwyty) - POPRAWIONY */
        .song-container { margin-top: 15px; }
        
        .song-row {
            display: flex;
            justify-content: flex-start; /* Dosuwa wszystko do lewej */
            align-items: baseline;
            gap: 20px; /* To jest kluczowe - ustawia odstęp (np. 2 cm) między tekstem a chwytem */
        }

        .lyrics-col {
            flex: 0 0 auto; /* Kolumna tekstu zajmuje tylko tyle miejsca, ile potrzebuje */
            min-width: 150px; /* Ale nie mniej niż 150px, żeby chwyty były w równej kolumnie */
        }

        .chords-col {
            color: #ff4b4b;
            font-weight: bold;
        }
        
        /* STYLIZACJA PRZYCISKÓW */
        div.stButton > button:first-child {
            border-radius: 12px !important;
            border: 1px solid #30363d;
            font-size: 11px !important;
            min-height: 0px !important;
            height: auto !important;
            padding: 4px 8px !important;
            background-color: #161b22;
            color: #c9d1d9;
            width: 100%;
        }
        div.stButton > button:first-child:hover {
            border-color: #ff4b4b;
            color: #ff4b4b;
            background-color: #21262d;
        }
        div.stButton > button:first-child:active {
            background-color: #ff4b4b;
            color: white;
        }

        /* SPECJALNY STYL DLA SIDEBARU (MNIEJSZE TAGI) */
        [data-testid="stSidebar"] div.stButton > button:first-child {
            font-size: 10px !important; /* Mniejsza czcionka w menu */
            padding: 3px 5px !important;
            white-space: normal !important; /* Pozwól na zawijanie długich słów */
            line-height: 1.1 !important;
            height: auto !important;
        }

        /* TONACJA - STYL LINIOWY */
        .tone-display {
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
            font-weight: bold;
            color: #888;
            height: 100%;
            margin: 0 5px;
        }

        /* MOBILE FIXES */
        @media (max-width: 600px) {
            .lyrics-col { font-size: 15px; padding-right: 15px; }
            .chords-col { font-size: 14px; }
            .song-title { font-size: 18px !important; }
            /* Na bardzo małych ekranach chwyty mogą spaść pod spód jeśli tekst jest długi */
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
    
    query = st.text_input("Szukaj:", placeholder="Tytuł...").lower()
    if query:
        found = [i for i, s in enumerate(songs) if query in (s["title"] + " " + " ".join([l["text"] for l in s["lyrics"]])).lower()]
        if found:
            sel = st.selectbox("Wyniki:", [songs[i]['title'] for i in found])
            if st.button("Idź"): 
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
    if st.button("Odśwież", key="refresh_sidebar", use_container_width=True):
        st.session_state.kw_lyrics = get_keywords(songs, "lyrics")
        st.session_state.kw_titles = get_keywords(songs, "title")
        st.rerun()

# ------------------------------
# 7. NAGŁÓWEK (Nowy Układ Liniowy)
# ------------------------------
if not songs: st.stop()
song = songs[st.session_state.current_idx]

# Stwórz 5 kolumn o różnych szerokościach
c1, c2, c3, c4, c5 = st.columns([0.5, 0.5, 3, 0.5, 0.5])

with c1:
    st.button("⬅️", key="prev", use_container_width=True)
with c2:
    st.button("🎲", key="rand", use_container_width=True)
with c3:
    st.markdown(f"<h2 style='text-align:center;'>{song['title']}</h2>", unsafe_allow_html=True)
with c4:
    st.button("🆕", key="newest", use_container_width=True)
with c5:
    st.button("➡️", key="next", use_container_width=True)

# Pasek narzędzi (Losuj | Tonacja)
# Zrobiony bardzo kompaktowo, pod tytułem
t1, t2, t3, t4, t5 = st.columns([1, 1, 0.5, 0.8, 0.5])

with t1:
    if st.button("🎲 Losuj", use_container_width=True, key="sub_rand"): 
        set_song_by_idx(random.randint(0, len(songs)-1)); st.rerun()

# Puste miejsce t2 dla odstępu

# Sekcja Tonacji w jednej linii
with t3:
    if st.button("➖", key="tone_down", use_container_width=True): 
        st.session_state.transposition -= 1; st.rerun()
with t4:
    st.markdown(f'<div class="tone-display">Tonacja: {st.session_state.transposition:+}</div>', unsafe_allow_html=True)
with t5:
    if st.button("➕", key="tone_up", use_container_width=True): 
        st.session_state.transposition += 1; st.rerun()

# ------------------------------
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
    if "<br>" in l["text"] or "---" in l["text"]: continue
    clean_text = l["text"].strip()
    chds = [transpose_chord(c, st.session_state.transposition) for c in l.get("chords", [])]
    c_str = " ".join(chds)
    
    if not clean_text and not chds: 
        html += '<div style="height:15px"></div>'
    else: 
        # Ważne: chords-col jest zaraz za lyrics-col
        html += f'<div class="song-row"><div class="lyrics-col">{clean_text or "&nbsp;"}</div><div class="chords-col">{c_str or "&nbsp;"}</div></div>'
st.markdown(html + '</div>', unsafe_allow_html=True)

# ------------------------------
# 9. OCENY I TAGI
# ------------------------------
st.markdown('<hr style="margin: 40px 0 10px 0; opacity: 0.2;">', unsafe_allow_html=True)

tab_vote, tab_tags, tab_rec = st.tabs(["⭐ Oceny", "🏷️ Tagi", "📚 Polecane"])

with tab_vote:
    col_v1, col_v2 = st.columns([2, 1])
    with col_v1:
        stats = ratings.get(song["title"], {"sum": 0, "count": 0})
        avg = stats["sum"]/stats["count"] if stats["count"]>0 else 0
        st.write(f"Ocena: **{avg:.1f}** ({stats['count']} gł.)")
        score = st.radio("Twoja ocena:", [1,2,3,4,5], horizontal=True, label_visibility="collapsed")
        if st.button("Zapisz", use_container_width=True, key="btn_zapisz_ocene"):
            stats["sum"] += score; stats["count"] += 1; ratings[song["title"]] = stats
            save_json("ratings.json", ratings)
            st.rerun()
            
    with col_v2:
        st.info("Oceń, by dostać tagi.")

    if score in RATING_TAGS:
        st.caption("Sugerowane:")
        render_expandable_cloud(RATING_TAGS[score], f"sug_tag_{score}", lambda t: (user_tags.setdefault(song["title"], []).append(t) or save_json("user_tags.json", user_tags) or st.rerun()) if t not in user_tags.get(song["title"], []) else None, initial_count=8)

with tab_tags:
    current_ut = user_tags.get(song["title"], [])
    if current_ut:
        st.caption("Usuń tag:")
        cols = st.columns(3)
        for i, tag in enumerate(current_ut):
            with cols[i%3]:
                if st.button(f"✕ {tag}", key=f"del_{i}_{tag}", use_container_width=True):
                    current_ut.remove(tag); user_tags[song["title"]] = current_ut; save_json("user_tags.json", user_tags); st.rerun()
    else: st.caption("Brak tagów.")
    
    st.markdown("---")
    nt = st.text_input("Dodaj tag:", label_visibility="collapsed", placeholder="Nowy tag...")
    if st.button("Dodaj", use_container_width=True):
        if nt and nt not in current_ut:
            current_ut.append(nt); user_tags[song["title"]] = current_ut; save_json("user_tags.json", user_tags); st.rerun()

with tab_rec:
    c_rec1, c_rec2 = st.columns(2)
    with c_rec1:
        st.caption("Losowe:")
        if st.button("Nowe", key="ref_rnd", use_container_width=True): st.session_state.random_sample = random.sample(songs, min(5, len(songs))); st.rerun()
        for i, rs in enumerate(st.session_state.random_sample):
            if st.button(rs["title"], key=f"r_{i}", use_container_width=True): set_song_by_idx(next((j for j, s in enumerate(songs) if s["title"] == rs["title"]), 0)); st.rerun()
    with c_rec2:
        st.caption("TOP:")
        ba = get_best_songs_all_time(ratings)
        if ba and st.button(f"🏆 {ba}", use_container_width=True): set_song_by_idx(next((i for i, s in enumerate(songs) if s["title"] == ba), 0)); st.rerun()

# ------------------------------
# 10. PANEL ADMIN
# ------------------------------
with st.expander("🛠️ Admin"):
    tab_e1, tab_e2 = st.tabs(["Edycja", "Opcje"])
    with tab_e1:
        et = st.text_input("Tytuł:", value=song["title"])
        el = [f"{l['text']} | {' '.join(l.get('chords', []))}" for l in song["lyrics"] if "<br>" not in l["text"]]
        nc = st.text_area("Treść:", value="\n".join(el), height=200)
        if st.button("Zapisz", use_container_width=True, key="btn_zapisz_edycje"):
            if et != song["title"]:
                songs[st.session_state.current_idx]["title"] = et
                if song["title"] in ratings: ratings[et] = ratings.pop(song["title"])
                if song["title"] in user_tags: user_tags[et] = user_tags.pop(song["title"])
            nl = []
            for line in nc.split("\n"):
                p = line.split("|")
                nl.append({"text": p[0].strip(), "chords": p[1].strip().split()} if len(p)>1 else {"text": line.strip(), "chords": []})
            songs[st.session_state.current_idx]["lyrics"] = nl
            save_json("songs.json", songs); save_json("ratings.json", ratings); save_json("user_tags.json", user_tags); st.rerun()
    
    with tab_e2:
        if st.text_input("PIN", type="password", key="admin_pin_input") == ADMIN_PIN:
            # Poprawione wcięcia i klucz przycisku
            if st.button("USUŃ UTWÓR", key=f"btn_delete_{st.session_state.current_idx}", type="primary", use_container_width=True):
                t_to_del = songs[st.session_state.current_idx]["title"]
                songs.pop(st.session_state.current_idx)
                if t_to_del in ratings: del ratings[t_to_del]
                if t_to_del in user_tags: del user_tags[t_to_del]
                save_json("songs.json", songs)
                st.session_state.current_idx = 0
                st.rerun()
