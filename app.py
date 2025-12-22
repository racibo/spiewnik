import streamlit as st
import json
import random
import re
from collections import Counter
from datetime import datetime, timedelta

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
        .main .block-container { padding-top: 0.5rem !important; padding-bottom: 2rem; max-width: 95%; }
        .song-title { font-size: 24px !important; font-weight: bold; margin: 0 !important; line-height: 1.1; }
        .song-container { margin-top: 5px; }
        .song-row { display: flex; flex-direction: row; padding: 1px 0; align-items: flex-start; }
        .lyrics-col { flex: 0 1 auto; min-width: 250px; font-size: 18px; font-weight: 500; line-height: 1.2; padding-right: 30px; }
        .chords-col { flex: 0 0 150px; font-weight: bold; color: #ff4b4b; font-family: monospace; font-size: 17px; }
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        
        /* Tag cloud styles */
        .tag-cloud { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
        .tag-btn { padding: 6px 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   color: white; border-radius: 20px; border: none; cursor: pointer; font-size: 12px;
                   transition: all 0.3s ease; white-space: nowrap; }
        .tag-btn:hover { transform: scale(1.05); box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
        
        /* MOBILE FIXES */
        @media (max-width: 768px) {
            .block-container { max-width: 100% !important; padding-top: 0.3rem !important; }
            .song-title { font-size: 18px !important; }
            .song-row { flex-direction: row; }
            .lyrics-col { min-width: 140px; font-size: 15px; padding-right: 10px; }
            .chords-col { flex: 0 0 80px; font-size: 13px; }
            .header-section { margin: 0 !important; padding: 5px 0 !important; }
        }
        @media (max-width: 600px) {
            .lyrics-col { font-size: 13px; min-width: 120px; padding-right: 8px; }
            .chords-col { flex: 0 0 70px; font-size: 11px; }
            .song-title { font-size: 16px !important; }
            .main .block-container { padding: 0.3rem !important; }
        }
    </style>
""", unsafe_allow_html=True)

ADMIN_PIN = "1234"

# Nowe tagi ocen
RATING_TAGS = {
    1: ["Tego nie lubię", "Tego nie graj", "Żenująca piosenka"],
    2: ["Zagraj to później"],
    3: ["To też zagraj"],
    4: ["To następne"],
    5: ["Zagraj to", "Koniecznie to musi być"]
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
    """Zwraca najlepiej ocenianą piosenkę wszech czasów"""
    if not ratings: return None
    best = max(ratings.items(), key=lambda x: x[1]["sum"]/x[1]["count"] if x[1]["count"]>0 else 0)
    return best[0]

def get_best_songs_week(ratings):
    """Zwraca najlepiej ocenianą w ostatnich 7 dniach (symulacja)"""
    if not ratings: return None
    best = max(ratings.items(), key=lambda x: x[1]["sum"]/x[1]["count"] if x[1]["count"]>0 else 0)
    return best[0]

def get_best_songs_today(ratings):
    """Zwraca najlepiej ocenianą dzisiaj (symulacja)"""
    if not ratings: return None
    best = max(ratings.items(), key=lambda x: x[1]["sum"]/x[1]["count"] if x[1]["count"]>0 else 0)
    return best[0]

def get_newest_song(songs):
    """Zwraca najnowszą piosenkę (ostatnio dodaną)"""
    if not songs: return None
    return songs[-1]["title"]

songs = load_json("songs.json", [])
ratings = load_json("ratings.json", {}) 
user_tags = load_json("user_tags.json", {})

# ------------------------------
# 3. Logika Analizy
# ------------------------------
STOPWORDS = {"się", "i", "w", "z", "na", "do", "że", "o", "a", "to", "jak", "nie", "co", "mnie", "mi", "ci", "za", "ale", "bo", "jest", "tylko", "przez", "jeszcze", "kiedy"}

def get_keywords(songs_list, source="lyrics", limit=8):
    all_words = []
    for s in songs_list:
        text = " ".join([l["text"] for l in s["lyrics"] if "<br>" not in l["text"]]).lower() if source == "lyrics" else s["title"].lower()
        words = re.findall(r'\b\w{4,}\b', text)
        all_words.extend([w for w in words if w not in STOPWORDS])
    most_common = Counter(all_words).most_common(30)
    return random.sample(most_common, min(limit, len(most_common))) if most_common else []

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
# 5. SIDEBAR (Trzy chmury)
# ------------------------------
with st.sidebar:
    st.title("📚 Biblioteka")
    st.info(f"Piosenek w bazie: **{len(songs)}**")
    
    query = st.text_input("🔍 Szukaj piosenki:").lower()
    if query:
        found = [i for i, s in enumerate(songs) if query in (s["title"] + " " + " ".join([l["text"] for l in s["lyrics"]])).lower()]
        if found:
            sel = st.selectbox("Wyniki:", [songs[i]['title'] for i in found])
            if st.button("Pokaż"): set_song_by_idx(found[[songs[i]['title'] for i in found].index(sel)]); st.rerun()

    st.markdown("---")
    
    # 1. Chmura Twoje Tagi - ULEPSZONA GRAFIKA
    st.subheader("⭐ Twoje Tagi")
    all_ut_list = []
    for t_list in user_tags.values(): all_ut_list.extend(t_list)
    if all_ut_list:
        tag_html = '<div class="tag-cloud">'
        for tag, count in Counter(all_ut_list).most_common(10):
            tag_html += f'<button class="tag-btn" onclick="alert(\'{tag}\')">{tag}</button>'
        tag_html += '</div>'
        st.markdown(tag_html, unsafe_allow_html=True)
        
        st.write("")  # Spacer
        col_tags = st.columns(3)
        for i, (tag, count) in enumerate(Counter(all_ut_list).most_common(10)):
            if col_tags[i % 3].button(f"🎯 {tag}", key=f"side_ut_{tag}", use_container_width=True):
                matches = [j for j, s in enumerate(songs) if tag in user_tags.get(s["title"], [])]
                if matches: set_song_by_idx(random.choice(matches)); st.rerun()
    else: st.caption("Brak dodanych tagów.")

    # 2. Chmura z TREŚCI
    st.subheader("🎵 Słowa z treści")
    c1, c2 = st.columns(2)
    for i, (w, c) in enumerate(st.session_state.kw_lyrics):
        if (c1 if i%2==0 else c2).button(f"#{w}", key=f"side_l_{w}", use_container_width=True):
            matches = [j for j, s in enumerate(songs) if w in " ".join([l["text"] for l in s["lyrics"]]).lower()]
            if matches: set_song_by_idx(random.choice(matches)); st.rerun()

    # 3. Chmura z TYTUŁÓW
    st.subheader("📖 Słowa z tytułów")
    c3, c4 = st.columns(2)
    for i, (w, c) in enumerate(st.session_state.kw_titles):
        if (c3 if i%2==0 else c4).button(f"{w.capitalize()}", key=f"side_t_{w}", use_container_width=True):
            matches = [j for j, s in enumerate(songs) if w in s["title"].lower()]
            if matches: set_song_by_idx(random.choice(matches)); st.rerun()
    
    if st.button("🔄 Odśwież chmury", key="refresh_sidebar"):
        st.session_state.kw_lyrics = get_keywords(songs, "lyrics")
        st.session_state.kw_titles = get_keywords(songs, "title")
        st.rerun()

# ------------------------------
# 6. NAGŁÓWEK - KOMPAKTOWY NA MOBILNYM
# ------------------------------
if not songs: st.stop()
song = songs[st.session_state.current_idx]

# Nagłówek - kompaktowy
st.markdown('<div class="header-section">', unsafe_allow_html=True)
h_col1, h_col2, h_col3 = st.columns([0.8, 3, 0.8])

with h_col1:
    c_n1, c_n2, c_n3, c_n4 = st.columns(4, gap="small")
    if c_n1.button("🎲", use_container_width=True, key="nav_random"): 
        set_song_by_idx(random.randint(0, len(songs)-1)); st.rerun()
    if c_n2.button("⬅️", use_container_width=True, key="nav_prev"): 
        set_song_by_idx(st.session_state.current_idx-1); st.rerun()
    if c_n3.button("➡️", use_container_width=True, key="nav_next"): 
        set_song_by_idx(st.session_state.current_idx+1); st.rerun()
    if c_n4.button("🆕", use_container_width=True, key="nav_newest"): 
        idx = next((i for i, s in enumerate(songs) if s["title"] == get_newest_song(songs)), 0)
        set_song_by_idx(idx); st.rerun()

with h_col2:
    st.markdown(f'<p class="song-title">{song["title"]}</p>', unsafe_allow_html=True)

with h_col3:
    t_c1, t_c2, t_c3 = st.columns([1, 1.2, 1])
    if t_c1.button("➖", key="tone_down"): 
        st.session_state.transposition -= 1; st.rerun()
    t_c2.markdown(f"<div style='text-align:center; font-size:11px; line-height:1.2;'>Tonacja<br><b>{st.session_state.transposition:+}</b></div>", unsafe_allow_html=True)
    if t_c3.button("➕", key="tone_up"): 
        st.session_state.transposition += 1; st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# ------------------------------
# 7. RENDER PIOSENKI
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

st.markdown('<hr style="margin: 2px 0 10px 0; opacity: 0.2;">', unsafe_allow_html=True)

html = '<div class="song-container">'
for l in song["lyrics"]:
    if "<br>" in l["text"] or "---" in l["text"]: continue
    clean_text = l["text"].strip()
    chds = [transpose_chord(c, st.session_state.transposition) for c in l.get("chords", [])]
    c_str = " ".join(chds)
    if not clean_text and not chds: html += '<div style="height:12px"></div>'
    else: html += f'<div class="song-row"><div class="lyrics-col">{clean_text or "&nbsp;"}</div><div class="chords-col">{c_str or "&nbsp;"}</div></div>'
st.markdown(html + '</div>', unsafe_allow_html=True)

# ------------------------------
# 8. OCENIANIE POD TEKSTEM Z NOWYMI TAGAMI
# ------------------------------
st.markdown('<hr style="margin: 20px 0 10px 0; opacity: 0.1;">', unsafe_allow_html=True)
r_col1, r_col2 = st.columns([2, 1])

with r_col1:
    stats = ratings.get(song["title"], {"sum": 0, "count": 0})
    avg = stats["sum"]/stats["count"] if stats["count"]>0 else 0
    st.write(f"Ocena: **{avg:.1f}** ⭐ ({stats['count']} głosów)")
    
    score = st.radio("Twoja ocena:", [1,2,3,4,5], horizontal=True, key=f"vote_radio_{st.session_state.current_idx}")
    
    if st.button("Zatwierdź ocenę", key="btn_vote"):
        stats["sum"] += score; stats["count"] += 1; ratings[song["title"]] = stats
        save_json("ratings.json", ratings)
        st.success(f"Ocena {score}⭐ zatwierdzona!")
        st.rerun()
    
    # Nowe tagi ocen
    if score in RATING_TAGS:
        st.write("**Sugerowane tagi:**")
        tag_cols = st.columns(len(RATING_TAGS[score]))
        for idx, tag in enumerate(RATING_TAGS[score]):
            if tag_cols[idx].button(tag, key=f"quick_tag_{score}_{idx}", use_container_width=True):
                current_ut = user_tags.get(song["title"], [])
                if tag not in current_ut:
                    current_ut.append(tag)
                    user_tags[song["title"]] = current_ut
                    save_json("user_tags.json", user_tags)
                st.rerun()

with r_col2:
    st.write("Tagi:")
    current_ut = user_tags.get(song["title"], [])
    
    # Wyświetlanie tagów z możliwością usuwania
    if current_ut:
        for tag in current_ut:
            col_tag, col_delete = st.columns([4, 1])
            col_tag.caption(f"🏷️ {tag}")
            if col_delete.button("✕", key=f"delete_tag_{song['title']}_{tag}"):
                current_ut.remove(tag)
                user_tags[song["title"]] = current_ut
                save_json("user_tags.json", user_tags)
                st.rerun()
    else:
        st.caption("Brak tagów")
    
    # Dodawanie nowych tagów
    nt = st.text_input("Dodaj tag:", key=f"input_tag_{st.session_state.current_idx}")
    if st.button("Zapisz tag", key="btn_tag"):
        if nt and nt not in current_ut:
            current_ut.append(nt)
            user_tags[song["title"]] = current_ut
            save_json("user_tags.json", user_tags)
            st.rerun()

# REKOMENDACJE
st.markdown('<hr style="margin: 20px 0 10px 0; opacity: 0.1;">', unsafe_allow_html=True)
st.subheader("📚 Polecane piosenki")

rec_col1, rec_col2 = st.columns(2)

# 5 LOSOWYCH PIOSENEK
with rec_col1:
    st.write("**🎲 5 losowych:**")
    if st.button("🔄 Losuj nowe", key="refresh_random"):
        st.session_state.random_sample = random.sample(songs, min(5, len(songs)))
        st.rerun()
    
    for i, rs in enumerate(st.session_state.random_sample):
        if st.button(rs["title"], key=f"random_btn_{i}", use_container_width=True):
            idx = next((j for j, s in enumerate(songs) if s["title"] == rs["title"]), None)
            if idx is not None:
                set_song_by_idx(idx)
                st.rerun()

# TOP OCENY
with rec_col2:
    st.write("**⭐ TOP oceny:**")
    
    # Wszystkie czasy
    best_all = get_best_songs_all_time(ratings)
    if best_all:
        all_time_stats = ratings[best_all]
        avg_all = all_time_stats["sum"]/all_time_stats["count"]
        if st.button(f"🏆 {best_all}\n({avg_all:.1f}★)", key=f"best_all_btn", use_container_width=True):
            idx = next((i for i, s in enumerate(songs) if s["title"] == best_all), None)
            if idx is not None:
                set_song_by_idx(idx)
                st.rerun()
    
    # Ostatnie 7 dni
    best_week = get_best_songs_week(ratings)
    if best_week and best_week != best_all:
        week_stats = ratings[best_week]
        avg_week = week_stats["sum"]/week_stats["count"]
        if st.button(f"📅 {best_week}\n(7dni - {avg_week:.1f}★)", key=f"best_week_btn", use_container_width=True):
            idx = next((i for i, s in enumerate(songs) if s["title"] == best_week), None)
            if idx is not None:
                set_song_by_idx(idx)
                st.rerun()
    
    # Dzisiaj
    best_today = get_best_songs_today(ratings)
    if best_today and best_today != best_all and best_today != best_week:
        today_stats = ratings[best_today]
        avg_today = today_stats["sum"]/today_stats["count"]
        if st.button(f"🔥 {best_today}\n(dzisiaj - {avg_today:.1f}★)", key=f"best_today_btn", use_container_width=True):
            idx = next((i for i, s in enumerate(songs) if s["title"] == best_today), None)
            if idx is not None:
                set_song_by_idx(idx)
                st.rerun()

st.markdown('<hr style="margin: 20px 0 10px 0; opacity: 0.1;">', unsafe_allow_html=True)

# ------------------------------
# 9. PANEL ZARZĄDZANIA Z EDYCJĄ TYTUŁU
# ------------------------------
with st.expander("🛠️ PANEL ZARZĄDZANIA"):
    tab1, tab2, tab3 = st.tabs(["✏️ Edytuj", "➕ Dodaj", "🗑️ Usuń"])
    
    with tab1:
        # EDYCJA TYTUŁU
        edit_title = st.text_input("Nowy tytuł:", value=song["title"], key=f"edit_title_{st.session_state.current_idx}")
        
        # Przygotowanie tekstu (bez br)
        editor_lines = [f"{l['text']} | {' '.join(l.get('chords', []))}" for l in song["lyrics"] if "<br>" not in l["text"]]
        
        new_c = st.text_area("Treść:", 
                            value="\n".join(editor_lines), 
                            height=300, 
                            key=f"editor_area_{st.session_state.current_idx}")
        
        if st.button("Zapisz zmiany", key="btn_save_edit"):
            # Zmiana tytułu
            if edit_title != song["title"]:
                songs[st.session_state.current_idx]["title"] = edit_title
                
                # Przenieś oceny i tagi
                if song["title"] in ratings:
                    ratings[edit_title] = ratings.pop(song["title"])
                if song["title"] in user_tags:
                    user_tags[edit_title] = user_tags.pop(song["title"])
            
            # Zmiana tekstu
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
            
    with tab2:
        n_t = st.text_input("Tytuł nowej piosenki:", key="new_title")
        n_l = st.text_area("Tekst | Akordy:", height=200, key="new_content")
        if st.button("Dodaj piosenkę", key="btn_add_song"):
            if n_t and n_l:
                parsed = [{"text": p.split("|")[0].strip(), "chords": p.split("|")[1].strip().split()} if "|" in p else {"text": p.strip(), "chords": []} for p in n_l.split("\n") if p.strip()]
                songs.append({"title": n_t, "lyrics": parsed})
                save_json("songs.json", songs)
                st.session_state.random_sample = random.sample(songs, min(5, len(songs)))
                st.success(f"Dodano piosenkę: {n_t}")
                st.rerun()
            else:
                st.error("Uzupełnij tytuł i tekst!")
            
    with tab3:
        pin = st.text_input("PIN administratora:", type="password", key="admin_pin")
        if pin == ADMIN_PIN:
            st.warning(f"⚠️ Czy na pewno chcesz usunąć '{song['title']}'?")
            if st.button("POTWIERDŹ USUNIĘCIE", key="btn_delete"):
                removed_title = songs[st.session_state.current_idx]["title"]
                songs.pop(st.session_state.current_idx)
                
                # Usuń oceny i tagi
                if removed_title in ratings:
                    del ratings[removed_title]
                if removed_title in user_tags:
                    del user_tags[removed_title]
                
                save_json("songs.json", songs)
                save_json("ratings.json", ratings)
                save_json("user_tags.json", user_tags)
                st.session_state.random_sample = random.sample(songs, min(5, len(songs))) if songs else []
                st.success("Piosenka usunięta!")
                st.rerun()
