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
        .main .block-container { padding-top: 0.5rem !important; padding-bottom: 2rem; max-width: 95%; }
        .song-title { font-size: 24px !important; font-weight: bold; margin: 0 !important; line-height: 1.1; }
        .song-container { margin-top: 5px; }
        .song-row { display: flex; flex-direction: row; padding: 1px 0; align-items: flex-start; }
        .lyrics-col { flex: 0 1 auto; min-width: 250px; font-size: 18px; font-weight: 500; line-height: 1.2; padding-right: 30px; }
        .chords-col { flex: 0 0 150px; font-weight: bold; color: #ff4b4b; font-family: monospace; font-size: 17px; }
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
/* MOBILE FIXES */
        @media (max-width: 768px) {
            .block-container { max-width: 100% !important; }
            .song-row { flex-direction: row; }
            .lyrics-col { min-width: 150px; font-size: 16px; padding-right: 15px; }
            .chords-col { flex: 0 0 100px; font-size: 14px; }
        }
        @media (max-width: 600px) {
            .lyrics-col { font-size: 14px; min-width: 120px; padding-right: 10px; }
            .chords-col { flex: 0 0 80px; font-size: 12px; }
            .song-title { font-size: 18px !important; }
        }
    </style>
""", unsafe_allow_html=True)

ADMIN_PIN = "1234"

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

def set_song_by_idx(idx):
    if songs:
        st.session_state.current_idx = idx % len(songs)
        st.session_state.transposition = 0

# ------------------------------
# 5. SIDEBAR (Trzy chmury)
# ------------------------------
with st.sidebar:
    st.title("📂 Biblioteka")
    st.info(f"Piosenek w bazie: **{len(songs)}**")
    
    query = st.text_input("🔍 Szukaj piosenki:").lower()
    if query:
        found = [i for i, s in enumerate(songs) if query in (s["title"] + " " + " ".join([l["text"] for l in s["lyrics"]])).lower()]
        if found:
            sel = st.selectbox("Wyniki:", [songs[i]['title'] for i in found])
            if st.button("Pokaż"): set_song_by_idx(found[[songs[i]['title'] for i in found].index(sel)]); st.rerun()

    st.markdown("---")
    
    # 1. Chmura Twoje Tagi
    st.subheader("⭐ Twoje Tagi")
    all_ut_list = []
    for t_list in user_tags.values(): all_ut_list.extend(t_list)
    if all_ut_list:
        c_ut1, c_ut2 = st.columns(2)
        for i, (tag, count) in enumerate(Counter(all_ut_list).most_common(10)):
            if (c_ut1 if i%2==0 else c_ut2).button(f"{tag}", key=f"side_ut_{tag}", use_container_width=True):
                matches = [j for j, s in enumerate(songs) if tag in user_tags.get(s["title"], [])]
                if matches: set_song_by_idx(random.choice(matches)); st.rerun()
    else: st.caption("Brak dodanych tagów.")

    # 2. Chmura z TREŚCI
    st.subheader("📝 Słowa z treści")
    c1, c2 = st.columns(2)
    for i, (w, c) in enumerate(st.session_state.kw_lyrics):
        if (c1 if i%2==0 else c2).button(f"#{w}", key=f"side_l_{w}", use_container_width=True):
            matches = [j for j, s in enumerate(songs) if w in " ".join([l["text"] for l in s["lyrics"]]).lower()]
            set_song_by_idx(random.choice(matches)); st.rerun()

    # 3. Chmura z TYTUŁÓW
    st.subheader("📖 Słowa z tytułów")
    c3, c4 = st.columns(2)
    for i, (w, c) in enumerate(st.session_state.kw_titles):
        if (c3 if i%2==0 else c4).button(f"{w.capitalize()}", key=f"side_t_{w}", use_container_width=True):
            matches = [j for j, s in enumerate(songs) if w in s["title"].lower()]
            set_song_by_idx(random.choice(matches)); st.rerun()
    
    if st.button("🔄 Odśwież chmury", key="refresh_sidebar"):
        st.session_state.kw_lyrics = get_keywords(songs, "lyrics")
        st.session_state.kw_titles = get_keywords(songs, "title")
        st.rerun()

# ------------------------------
# 6. NAGŁÓWEK
# ------------------------------
if not songs: st.stop()
song = songs[st.session_state.current_idx]

h_col1, h_col2, h_col3 = st.columns([1.5, 3.5, 1.5])
with h_col1:
    c_n1, c_n2, c_n3, c_n4 = st.columns(4, gap="small")
    if c_n1.button("🎲", use_container_width=True): set_song_by_idx(random.randint(0, len(songs)-1)); st.rerun()
    if c_n2.button("⬅️", use_container_width=True): set_song_by_idx(st.session_state.current_idx-1); st.rerun()
    if c_n3.button("➡️", use_container_width=True): set_song_by_idx(st.session_state.current_idx+1); st.rerun()
    if c_n4.button("🔝", use_container_width=True): set_song_by_idx(len(songs)-1); st.rerun()
with h_col2:
    st.markdown(f'<p class="song-title">{song["title"]}</p>', unsafe_allow_html=True)
with h_col3:
    t_c1, t_c2, t_c3 = st.columns([1, 1.2, 1])
    if t_c1.button("➖"): st.session_state.transposition -= 1
    t_c2.markdown(f"<div style='text-align:center; font-size:12px; line-height:1;'>Tonacja<br><b>{st.session_state.transposition:+}</b></div>", unsafe_allow_html=True)
    if t_c3.button("➕"): st.session_state.transposition += 1

# ------------------------------
# 7. RENDER PIEŚNI
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
# 8. OCENIANIE POD TEKSTEM
# ------------------------------
st.markdown('<hr style="margin: 20px 0 10px 0; opacity: 0.1;">', unsafe_allow_html=True)
r_col1, r_col2 = st.columns([2, 1])
with r_col1:
    stats = ratings.get(song["title"], {"sum": 0, "count": 0})
    avg = stats["sum"]/stats["count"] if stats["count"]>0 else 0
    st.write(f"Ocena: **{avg:.1f}** ⭐ ({stats['count']} gł.)")
    score = st.radio("Twoja ocena:", [1,2,3,4,5], horizontal=True, key=f"vote_radio_{st.session_state.current_idx}")
    if st.button("Zatwierdź ocenę", key="btn_vote"):
        stats["sum"] += score; stats["count"] += 1; ratings[song["title"]] = stats
        save_json("ratings.json", ratings); st.rerun()
with r_col2:
    st.write("Tagi:")
    current_ut = user_tags.get(song["title"], [])
    
    # Wyświetlanie tagów z możliwością usuwania
    if current_ut:
        for tag in current_ut:
            col_tag, col_delete = st.columns([4, 1])
            col_tag.caption(tag)
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

# ------------------------------
# 9. PANEL ZARZĄDZANIA (POPRAWIONE ODŚWIEŻANIE)
# ------------------------------
with st.expander("🛠️ PANEL ZARZĄDZANIA"):
    tab1, tab2, tab3 = st.tabs(["✏️ Edytuj", "➕ Dodaj", "🗑️ Usuń"])
    
    with tab1:
        # Przygotowanie tekstu (bez br)
        editor_lines = [f"{l['text']} | {' '.join(l.get('chords', []))}" for l in song["lyrics"] if "<br>" not in l["text"]]
        
        # KLUCZOWA POPRAWKA: key zawiera current_idx, wymuszając odświeżenie treści
        new_c = st.text_area("Treść:", 
                            value="\n".join(editor_lines), 
                            height=300, 
                            key=f"editor_area_{st.session_state.current_idx}")
        
        if st.button("Zapisz zmiany", key="btn_save_edit"):
            new_lyrics = []
            for line in new_c.split("\n"):
                if "|" in line:
                    p = line.split("|")
                    new_lyrics.append({"text": p[0].strip(), "chords": p[1].strip().split()})
                else:
                    new_lyrics.append({"text": line.strip(), "chords": []})
            songs[st.session_state.current_idx]["lyrics"] = new_lyrics
            save_json("songs.json", songs); st.success("Zapisano!"); st.rerun()
            
    with tab2:
        n_t = st.text_input("Tytuł nowej piosenki:", key="new_title")
        n_l = st.text_area("Tekst | Akordy:", height=200, key="new_content")
        if st.button("Dodaj piosenkę", key="btn_add_song"):
            parsed = [{"text": p.split("|")[0].strip(), "chords": p.split("|")[1].strip().split()} if "|" in p else {"text": p.strip(), "chords": []} for p in n_l.split("\n")]
            songs.append({"title": n_t, "lyrics": parsed})
            save_json("songs.json", songs); st.rerun()
            
    with tab3:
        pin = st.text_input("PIN administratora:", type="password", key="admin_pin")
        if pin == ADMIN_PIN:
            if st.button("POTWIERDŹ USUNIĘCIE", key="btn_delete"):
                songs.pop(st.session_state.current_idx); save_json("songs.json", songs); st.rerun()
