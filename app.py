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
        
        /* Kontener główny - marginesy mobilne */
        .main .block-container { 
            padding-top: 0.5rem !important; 
            padding-bottom: 3rem; 
            max-width: 100%; 
            padding-left: 1rem;
            padding-right: 1rem;
        }
        
        /* Style tekstu piosenki */
        .song-title { font-size: 22px !important; font-weight: bold; margin: 0 !important; line-height: 1.2; color: #fff; }
        .song-container { margin-top: 10px; }
        .song-row { display: flex; flex-direction: row; padding: 2px 0; align-items: flex-start; flex-wrap: wrap; }
        
        /* Lyrics & Chords - Mobile Optimized */
        .lyrics-col { 
            flex: 1 1 auto; 
            min-width: 200px; 
            font-size: 16px; 
            font-weight: 500; 
            line-height: 1.3; 
            padding-right: 15px; 
            color: #e0e0e0;
        }
        .chords-col { 
            flex: 0 0 auto; 
            font-weight: bold; 
            color: #ff4b4b; 
            font-family: monospace; 
            font-size: 15px; 
        }
        
        /* Ukrycie standardowych elementów Streamlit */
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        
        /* STYLIZACJA PRZYCISKÓW - MAŁE TAGI */
        div.stButton > button:first-child {
            border-radius: 12px !important;
            border: 1px solid #30363d;
            font-size: 11px !important; /* Mniejsza czcionka */
            padding: 4px 2px !important; /* Małe odstępy */
            min-height: 0px !important;
            height: auto !important;
            width: 100%;
            margin-bottom: 2px;
            background-color: #161b22;
            color: #c9d1d9;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
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

        /* MOBILE FIXES */
        @media (max-width: 600px) {
            .lyrics-col { font-size: 14px; min-width: 100%; padding-right: 0; margin-bottom: 2px; }
            .chords-col { font-size: 13px; width: 100%; display: block; margin-bottom: 8px; }
            .song-row { flex-direction: column; border-bottom: 1px solid #1f242b; padding-bottom: 4px; margin-bottom: 4px; }
            .song-title { font-size: 18px !important; }
            
            /* Nawigacja na górze - większe przyciski dotykowe */
            .header-btn button { min-height: 40px !important; }
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
# 5. RENDEROWANIE CHMURY TAGÓW (Z ROZWIJANIEM)
# ------------------------------
def render_expandable_cloud(items, key_prefix, on_click_action, initial_count=8):
    """
    Renderuje siatkę przycisków. Zawsze pokazuje 'initial_count' przycisków.
    Ostatni przycisk to 'Więcej', który rozwija listę.
    """
    state_key = f"expanded_{key_prefix}"
    if state_key not in st.session_state:
        st.session_state[state_key] = False

    is_expanded = st.session_state[state_key]
    
    # Jeśli lista jest krótka, po prostu pokaż wszystko bez przycisku "Więcej"
    if len(items) <= initial_count:
        visible_items = items
        needs_toggle = False
    else:
        # Jeśli zwinięte: pokaż N-1 elementów, a N-ty to przycisk "Więcej"
        # Jeśli rozwinięte: pokaż wszystkie + przycisk "Mniej"
        visible_items = items if is_expanded else items[:initial_count]
        needs_toggle = True

    # Renderowanie siatki - 3 kolumny są optymalne dla Mobile
    cols_num = 3 
    columns = st.columns(cols_num)
    
    # Rysuj elementy
    for i, item in enumerate(visible_items):
        label = item if isinstance(item, str) else item[0] # Obsługa krotek i stringów
        
        # Wybór kolumny
        with columns[i % cols_num]:
            if st.button(label, key=f"{key_prefix}_{i}", use_container_width=True):
                on_click_action(label)

    # Przycisk sterujący (Więcej/Mniej) na końcu
    if needs_toggle:
        # Umieść przycisk w kolejnym wolnym slocie siatki
        next_idx = len(visible_items)
        with columns[next_idx % cols_num]:
            btn_label = "🔼 Mniej" if is_expanded else "🔽 Więcej"
            if st.button(btn_label, key=f"toggle_{key_prefix}", use_container_width=True):
                st.session_state[state_key] = not st.session_state[state_key]
                st.rerun()

# ------------------------------
# 6. SIDEBAR
# ------------------------------
with st.sidebar:
    st.title("📚 Biblioteka")
    st.caption(f"Baza: {len(songs)} utworów")
    
    query = st.text_input("🔍 Szukaj:", placeholder="Tytuł lub tekst...").lower()
    if query:
        found = [i for i, s in enumerate(songs) if query in (s["title"] + " " + " ".join([l["text"] for l in s["lyrics"]])).lower()]
        if found:
            sel = st.selectbox("Wyniki:", [songs[i]['title'] for i in found])
            if st.button("Idź do piosenki", use_container_width=True): 
                set_song_by_idx(found[[songs[i]['title'] for i in found].index(sel)])
                st.rerun()

    st.markdown("---")
    
    # 1. Twoje Tagi
    st.subheader("⭐ Twoje Tagi")
    all_ut_list = []
    for t_list in user_tags.values(): all_ut_list.extend(t_list)
    
    if all_ut_list:
        common_tags = [t[0] for t in Counter(all_ut_list).most_common(50)] # Pobierz dużo, ale pokażemy tylko część
        def filter_by_tag(tag):
            matches = [j for j, s in enumerate(songs) if tag in user_tags.get(s["title"], [])]
            if matches: set_song_by_idx(random.choice(matches)); st.rerun()
            
        render_expandable_cloud(common_tags, "side_ut", filter_by_tag, initial_count=8)
    else:
        st.caption("Brak tagów.")

    # 2. Słowa z treści
    st.markdown("---")
    st.subheader("🎵 Z tekstu")
    if st.session_state.kw_lyrics:
        def filter_by_lyric(word):
            matches = [j for j, s in enumerate(songs) if word in " ".join([l["text"] for l in s["lyrics"]]).lower()]
            if matches: set_song_by_idx(random.choice(matches)); st.rerun()
            
        render_expandable_cloud([w[0] for w in st.session_state.kw_lyrics], "side_l", filter_by_lyric, initial_count=11)

    # 3. Słowa z tytułów
    st.markdown("---")
    st.subheader("📖 Z tytułów")
    if st.session_state.kw_titles:
        def filter_by_title_word(word):
            matches = [j for j, s in enumerate(songs) if word in s["title"].lower()]
            if matches: set_song_by_idx(random.choice(matches)); st.rerun()
            
        render_expandable_cloud([w[0] for w in st.session_state.kw_titles], "side_t", filter_by_title_word, initial_count=8)
    
    st.markdown("---")
    if st.button("🔄 Odśwież chmury", key="refresh_sidebar", use_container_width=True):
        st.session_state.kw_lyrics = get_keywords(songs, "lyrics")
        st.session_state.kw_titles = get_keywords(songs, "title")
        st.rerun()

# ------------------------------
# 7. NAGŁÓWEK I NAWIGACJA
# ------------------------------
if not songs: st.stop()
song = songs[st.session_state.current_idx]

# Kontener nawigacji
c1, c2, c3 = st.columns([1, 4, 1])

with c1:
    # Siatka przycisków nawigacyjnych
    n1, n2 = st.columns(2)
    if n1.button("🎲", use_container_width=True, help="Losuj"): 
        set_song_by_idx(random.randint(0, len(songs)-1)); st.rerun()
    if n2.button("🆕", use_container_width=True, help="Najnowsza"): 
        idx = next((i for i, s in enumerate(songs) if s["title"] == get_newest_song(songs)), 0)
        set_song_by_idx(idx); st.rerun()

with c2:
    st.markdown(f'<div style="text-align: center;"><p class="song-title">{song["title"]}</p></div>', unsafe_allow_html=True)
    # Nawigacja lewo/prawo pod tytułem na mobile
    np1, np2 = st.columns(2)
    if np1.button("⬅️ Poprzednia", use_container_width=True): 
        set_song_by_idx(st.session_state.current_idx-1); st.rerun()
    if np2.button("Następna ➡️", use_container_width=True): 
        set_song_by_idx(st.session_state.current_idx+1); st.rerun()

with c3:
    # Transpozycja
    tc1, tc2 = st.columns(2)
    if tc1.button("➖", key="td", use_container_width=True): 
        st.session_state.transposition -= 1; st.rerun()
    if tc2.button("➕", key="tu", use_container_width=True): 
        st.session_state.transposition += 1; st.rerun()
    st.markdown(f"<div style='text-align:center; font-size:10px; color:#888'>Tonacja: {st.session_state.transposition:+}</div>", unsafe_allow_html=True)

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

st.markdown('<hr style="margin: 10px 0; opacity: 0.2;">', unsafe_allow_html=True)

html = '<div class="song-container">'
for l in song["lyrics"]:
    if "<br>" in l["text"] or "---" in l["text"]: continue
    clean_text = l["text"].strip()
    chds = [transpose_chord(c, st.session_state.transposition) for c in l.get("chords", [])]
    c_str = " ".join(chds)
    
    # Warunek pustej linii
    if not clean_text and not chds: 
        html += '<div style="height:15px"></div>'
    else: 
        html += f'<div class="song-row"><div class="lyrics-col">{clean_text or "&nbsp;"}</div><div class="chords-col">{c_str or "&nbsp;"}</div></div>'
st.markdown(html + '</div>', unsafe_allow_html=True)

# ------------------------------
# 9. OCENY I TAGI (DOLNA SEKCJA)
# ------------------------------
st.markdown('<hr style="margin: 30px 0 10px 0; opacity: 0.2;">', unsafe_allow_html=True)

# Używamy Tabs dla porządku na małym ekranie
tab_vote, tab_tags, tab_rec = st.tabs(["⭐ Oceny", "🏷️ Tagi", "📚 Polecane"])

with tab_vote:
    col_v1, col_v2 = st.columns([2, 1])
    with col_v1:
        stats = ratings.get(song["title"], {"sum": 0, "count": 0})
        avg = stats["sum"]/stats["count"] if stats["count"]>0 else 0
        st.write(f"Średnia: **{avg:.1f}** ({stats['count']} gł.)")
        
        score = st.radio("Twoja ocena:", [1,2,3,4,5], horizontal=True, label_visibility="collapsed")
        
        if st.button("Zapisz ocenę", use_container_width=True):
            stats["sum"] += score; stats["count"] += 1; ratings[song["title"]] = stats
            save_json("ratings.json", ratings)
            st.success("Zapisano!")
            st.rerun()
            
    with col_v2:
        st.info("Oceń utwór, aby zobaczyć sugestie tagów.")

    if score in RATING_TAGS:
        st.caption("Sugerowane tagi (kliknij by dodać):")
        tags_to_show = RATING_TAGS[score]
        
        def add_suggested_tag(tag):
            current_ut = user_tags.get(song["title"], [])
            if tag not in current_ut:
                current_ut.append(tag)
                user_tags[song["title"]] = current_ut
                save_json("user_tags.json", user_tags)
                st.rerun()
        
        # Wyświetlamy sugestie z rozwijaniem
        render_expandable_cloud(tags_to_show, f"sug_tag_{score}", add_suggested_tag, initial_count=8)

with tab_tags:
    current_ut = user_tags.get(song["title"], [])
    
    if current_ut:
        st.write("Przypisane tagi:")
        # Wyświetlanie tagów do usunięcia w siatce
        cols = st.columns(3)
        for i, tag in enumerate(current_ut):
            with cols[i%3]:
                if st.button(f"✕ {tag}", key=f"del_{i}_{tag}", use_container_width=True):
                    current_ut.remove(tag)
                    user_tags[song["title"]] = current_ut
                    save_json("user_tags.json", user_tags)
                    st.rerun()
    else:
        st.caption("Brak przypisanych tagów.")
        
    st.markdown("---")
    new_tag = st.text_input("Nowy tag:", label_visibility="collapsed", placeholder="Wpisz własny tag...")
    if st.button("Dodaj tag", use_container_width=True):
        if new_tag and new_tag not in current_ut:
            current_ut.append(new_tag)
            user_tags[song["title"]] = current_ut
            save_json("user_tags.json", user_tags)
            st.rerun()

with tab_rec:
    c_rec1, c_rec2 = st.columns(2)
    with c_rec1:
        st.caption("Losowe:")
        if st.button("🔄 Nowe", key="ref_rnd", use_container_width=True):
            st.session_state.random_sample = random.sample(songs, min(5, len(songs)))
            st.rerun()
        for i, rs in enumerate(st.session_state.random_sample):
            if st.button(rs["title"], key=f"r_{i}", use_container_width=True):
                idx = next((j for j, s in enumerate(songs) if s["title"] == rs["title"]), None)
                if idx is not None: set_song_by_idx(idx); st.rerun()
                
    with c_rec2:
        st.caption("TOP Oceny:")
        best_all = get_best_songs_all_time(ratings)
        if best_all and st.button(f"🏆 {best_all}", use_container_width=True):
             idx = next((i for i, s in enumerate(songs) if s["title"] == best_all), None)
             if idx: set_song_by_idx(idx); st.rerun()
             
        best_week = get_best_songs_week(ratings)
        if best_week and best_week != best_all and st.button(f"📅 {best_week}", use_container_width=True):
             idx = next((i for i, s in enumerate(songs) if s["title"] == best_week), None)
             if idx: set_song_by_idx(idx); st.rerun()

# ------------------------------
# 10. PANEL ADMIN
# ------------------------------
with st.expander("🛠️ Edycja / Admin"):
    tab_e1, tab_e2 = st.tabs(["Edycja", "Dodaj/Usuń"])
    
    with tab_e1:
        edit_title = st.text_input("Tytuł:", value=song["title"])
        editor_lines = [f"{l['text']} | {' '.join(l.get('chords', []))}" for l in song["lyrics"] if "<br>" not in l["text"]]
        new_c = st.text_area("Tekst | Akordy:", value="\n".join(editor_lines), height=250)
        
        if st.button("Zapisz Zmiany", use_container_width=True):
            if edit_title != song["title"]:
                songs[st.session_state.current_idx]["title"] = edit_title
                if song["title"] in ratings: ratings[edit_title] = ratings.pop(song["title"])
                if song["title"] in user_tags: user_tags[edit_title] = user_tags.pop(song["title"])
            
            new_lyrics = []
            for line in new_c.split("\n"):
                if "|" in line:
                    p = line.split("|")
                    new_lyrics.append({"text": p[0].strip(), "chords": p[1].strip().split()})
                else:
                    new_lyrics.append({"text": line.strip(), "chords": []})
            songs[st.session_state.current_idx]["lyrics"] = new_lyrics
            save_json("songs.json", songs)
            save_json("ratings.json", ratings)
            save_json("user_tags.json", user_tags)
            st.success("Zapisano!")
            st.rerun()

    with tab_e2:
        st.caption("Dodawanie:")
        n_t = st.text_input("Nowy tytuł")
        n_l = st.text_area("Treść (Tekst | Akordy)")
        if st.button("Dodaj Nową", use_container_width=True):
            if n_t and n_l:
                parsed = [{"text": p.split("|")[0].strip(), "chords": p.split("|")[1].strip().split()} if "|" in p else {"text": p.strip(), "chords": []} for p in n_l.split("\n") if p.strip()]
                songs.append({"title": n_t, "lyrics": parsed})
                save_json("songs.json", songs)
                st.success("Dodano!")
                st.rerun()
        
        st.markdown("---")
        st.caption("Usuwanie:")
        if st.text_input("PIN", type="password") == ADMIN_PIN:
            if st.button("USUŃ ten utwór", type="primary", use_container_width=True):
                t = songs[st.session_state.current_idx]["title"]
                songs.pop(st.session_state.current_idx)
                if t in ratings: del ratings[t]
                if t in user_tags: del user_tags[t]
                save_json("songs.json", songs)
                st.session_state.current_idx = 0
                st.rerun()
