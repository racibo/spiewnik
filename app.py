import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
import random
import re
from collections import Counter
import pandas as pd

# --- KONFIGURACJA I POŁĄCZENIE Z GOOGLE SHEETS ---

def init_gsheet():
    """Inicjalizacja połączenia z Google Sheets"""
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]
            creds = Credentials.from_service_account_info(
                creds_dict,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            client = gspread.authorize(creds)
            # ID arkusza z oryginalnego kodu
            spreadsheet = client.open_by_key("1RG82ZtUZfNsOjXI7xHKDnwbnDUl2SwE5oDLMNJNYdkw")
            worksheet = spreadsheet.worksheet("Songs")
            return worksheet
        else:
            st.error("Brak konfiguracji 'gcp_service_account' w secrets.toml")
            return None
    except Exception as e:
        st.error(f"Błąd połączenia z Google Sheets: {e}")
        return None

ws = init_gsheet()

# --- FUNKCJE LOGIKI BIZNESOWEJ ---

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
    if not ws:
        return False
    
    try:
        lyrics_str = "\n".join([
            f"{l['text']} | {' '.join(l.get('chords', []))}" 
            for l in lyrics
        ])
        
        tags_str = ", ".join(tags)
        
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
        tags_str = ", ".join(tags)
        ws.update([[tags_str]], f"E{row_idx}")
        return True
    except Exception as e:
        st.error(f"Błąd podczas aktualizacji tagów: {e}")
        return False

def update_song_ratings(row_idx, ratings_sum, ratings_count):
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

# --- CONFIG & STYLING ---

st.set_page_config(
    layout="wide", 
    page_title="Śpiewnik",
    initial_sidebar_state="expanded" 
)

st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background-color: #0e1117; }
    [data-testid="stSidebar"] { background-color: #010409; }

    .song-title {
        font-weight: bold;
        color: #ffffff;
        text-align: center;
        line-height: 1.1;
        font-size: 28px !important;
        margin-bottom: 12px !important;
        margin-top: -20px !important;
    }

    .song-tags-header {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 8px;
        margin-bottom: 12px;
        flex-wrap: wrap;
    }

    .song-tag-badge {
        background-color: #21262d;
        border: 1px solid #30363d;
        color: #c9d1d9;
        padding: 4px 10px;
        border-radius: 16px;
        font-size: 12px;
        font-weight: 500;
    }

    .song-row {
        display: flex;
        justify-content: flex-start;
        align-items: baseline;
        gap: 20px;
        margin-bottom: 0px !important;
    }
    .lyrics-col { 
        flex: 0 0 auto; 
        min-width: 150px; 
        font-size: 16px; 
        color: #eee; 
    }
    .chords-col { 
        color: #ff4b4b !important; 
        font-weight: bold; 
        font-size: 16px; 
    }

    div.stButton > button {
        border-radius: 8px;
        transition: all 0.2s;
    }
    
    .nav-btn div.stButton > button {
        padding: 0.5rem 0.2rem !important;
        font-size: 14px !important;
        height: auto !important;
    }

    .list-btn div.stButton > button {
        text-align: left !important;
        justify-content: flex-start !important;
        border: 1px solid #30363d !important;
        background-color: #161b22 !important;
    }

    .tag-btn div.stButton > button {
        padding: 2px 8px !important;
        font-size: 12px !important;
        min-height: 0px !important;
        height: 28px !important;
        background-color: #21262d;
        border: 1px solid #30363d;
        color: #c9d1d9;
    }
    .tag-btn div.stButton > button:hover {
        border-color: #8b949e;
        color: #fff;
    }
    
    [data-testid="stSidebar"] div.stButton > button {
        font-size: 11px !important;
        padding: 2px 8px !important;
    }

    hr { margin: 10px 0 !important; }
</style>
""", unsafe_allow_html=True)

ADMIN_PIN = "1234"

RATING_TAGS = {
    1: ["Nie lubię", "Nie graj", "Żenada", "Pomiń", "Trudne", "Słabe", "Nudne"],
    2: ["Później", "Kiedyś", "Nie teraz", "Ćwiczyć", "Średnie", "Zapomnij"],
    3: ["Zagraj", "OK", "Niezła", "Ognisko", "Spokojna", "Klasyk", "Może być"],
    4: ["Następne", "Ładna", "Polecam", "Częściej", "Wpadająca", "Energia", "Na start"],
    5: ["HIT", "Koniecznie", "Ulubiona", "TOP", "Mistrz", "Hymn", "Wszyscy", "Legenda"]
}

STOPWORDS = {"się", "i", "w", "z", "na", "do", "że", "o", "a", "to", "jak", "nie", "co", "mnie", "mi", "ci", "za", "ale", "bo", "jest", "tylko", "przez", "jeszcze", "kiedy", "już", "dla", "od", "ten", "ta"}

# --- HELPERS ---

def get_keywords(songs_list, source="lyrics", limit=40):
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

def get_most_common_tags(songs, limit=10):
    all_tags = []
    for song in songs:
        all_tags.extend(song.get("tags", []))
    if not all_tags:
        return []
    return [t[0] for t in Counter(all_tags).most_common(limit)]

def get_most_visited_songs(songs, limit=10):
    rated_songs = [s for s in songs if s["ratings_count"] > 0]
    return sorted(rated_songs, key=lambda x: x["ratings_count"], reverse=True)[:limit]

def reload_songs():
    st.session_state.songs = load_songs_from_sheets()

# --- NOWE FUNKCJE REKOMENDACJI ---

def get_recommended_songs_rotational(songs, limit=5):
    """
    Nowa logika losowania:
    - 2 piosenki oceniane (bez negatywnych tagów)
    - 2 piosenki 'dziewicze' (bez ocen i bez tagów)
    - 1 piosenka całkowicie losowa
    """
    if not songs:
        return []

    # 1. Piosenki oceniane i "bezpieczne"
    negative_tags_set = set(RATING_TAGS.get(1, []))
    rated_safe_songs = [
        s for s in songs 
        if s["ratings_count"] > 0 
        and not any(tag in negative_tags_set for tag in s.get("tags", []))
    ]

    # 2. Piosenki niezbadane (brak ocen i brak tagów)
    unexplored_songs = [
        s for s in songs 
        if s["ratings_count"] == 0 and not s.get("tags")
    ]

    selection = []

    # Losujemy 2 z ocenianych (jeśli są)
    if len(rated_safe_songs) >= 2:
        selection.extend(random.sample(rated_safe_songs, 2))
    else:
        selection.extend(rated_safe_songs)
    
    # Losujemy 2 z niezbadanych (jeśli są)
    if len(unexplored_songs) >= 2:
        selection.extend(random.sample(unexplored_songs, 2))
    else:
        selection.extend(unexplored_songs)
    
    # Uzupełniamy do limit-1 z puli ogólnej (wykluczając już wybrane), by zostawić miejsce na Jokera
    # Jeśli mamy mniej piosenek niż limit-1, dobieramy ile się da
    needed = max(0, (limit - 1) - len(selection))
    if needed > 0:
        remaining_pool = [s for s in songs if s not in selection]
        if len(remaining_pool) >= needed:
            selection.extend(random.sample(remaining_pool, needed))
        else:
            selection.extend(remaining_pool)

    # 3. Piąta piosenka - Joker (zupełnie losowa z CAŁEJ puli)
    if songs:
        selection.append(random.choice(songs))

    # Ostateczne przycięcie do limitu (na wypadek duplikatów przy małej bazie) i przemieszanie
    random.shuffle(selection)
    return selection[:limit]

# --- FUNKCJE RENDEROWANIA ---

def render_expandable_cloud(items, key_prefix, on_click_action, initial_count=8):
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

def render_compact_tags(items, key_prefix, on_click_action, limit=None):
    if not items:
        return
    visible_items = items[:limit] if limit else items
    cols_num = 4
    rows = [visible_items[i:i + cols_num] for i in range(0, len(visible_items), cols_num)]
    
    st.markdown('<div class="tag-btn">', unsafe_allow_html=True)
    for r_idx, row_items in enumerate(rows):
        cols = st.columns(cols_num)
        for i, item in enumerate(row_items):
            label = item if isinstance(item, str) else item[0]
            with cols[i]:
                if st.button(label, key=f"{key_prefix}_{r_idx}_{i}", use_container_width=True):
                    on_click_action(label)
    st.markdown('</div>', unsafe_allow_html=True)

# --- STATE MANAGEMENT ---

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
    # Użycie nowej logiki rotacyjnej przy starcie
    st.session_state.random_sample = get_recommended_songs_rotational(st.session_state.songs, limit=5)

def set_song_by_idx(idx):
    if st.session_state.songs:
        st.session_state.current_idx = idx % len(st.session_state.songs)
        st.session_state.transposition = 0

# --- SIDEBAR ---

with st.sidebar:
    st.title("Biblioteka")
    
    query = st.text_input("Szukaj:", placeholder="Tytuł lub tekst...", key="main_search_input").lower()
    if query:
        found = [i for i, s in enumerate(st.session_state.songs) 
                if query in (s["title"] + " " + " ".join([l["text"] for l in s["lyrics"]])).lower()]
        if found:
            for idx in found:
                s_title = st.session_state.songs[idx]['title']
                if st.button(s_title, key=f"search_res_{idx}", use_container_width=True):
                    set_song_by_idx(idx)
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

if not st.session_state.songs:
    st.warning("Baza piosenek jest pusta lub brak połączenia.")
    st.stop()

# --- GŁÓWNY WIDOK PIOSENKI ---

song = st.session_state.songs[st.session_state.current_idx]

st.markdown(f'<div class="song-title">{song["title"]}</div>', unsafe_allow_html=True)

if song.get("tags"):
    tags_html = '<div class="song-tags-header">'
    for tag in song["tags"]:
        tags_html += f'<span class="song-tag-badge">{tag}</span>'
    tags_html += '</div>'
    st.markdown(tags_html, unsafe_allow_html=True)

st.markdown('<hr style="margin: 5px 0 15px 0; opacity: 0.2;">', unsafe_allow_html=True)

def transpose_chord(chord, steps):
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
st.markdown('<hr style="margin: 15px 0 10px 0; opacity: 0.2;">', unsafe_allow_html=True)

# --- PANEL STEROWANIA ---

st.markdown('<div class="nav-btn">', unsafe_allow_html=True)
col_nav1, col_nav2 = st.columns(2)
with col_nav1:
    if st.button("⬅️ Wstecz", key="nav_prev", use_container_width=True):
        set_song_by_idx(st.session_state.current_idx - 1)
        st.rerun()
with col_nav2:
    if st.button("➡️ Dalej", key="nav_next", use_container_width=True):
        set_song_by_idx(st.session_state.current_idx + 1)
        st.rerun()

col_nav3, col_nav4 = st.columns(2)
with col_nav3:
    if st.button("🎲 Losowa", key="nav_rand", use_container_width=True):
        set_song_by_idx(random.randint(0, len(st.session_state.songs)-1))
        st.rerun()
with col_nav4:
    if st.button("⭐️ Ostatnia", key="nav_last", use_container_width=True):
        set_song_by_idx(len(st.session_state.songs)-1)
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

st.caption("Zmień tonację")
ct1, ct2, ct3 = st.columns([1, 1, 1])
with ct1:
    if st.button("➖ pół tonu", key="t_down", use_container_width=True):
        st.session_state.transposition -= 1
        st.rerun()
with ct2:
    st.markdown(f'<div style="text-align:center; padding-top:5px; font-weight:bold; color:#aaa;">{st.session_state.transposition:+}</div>', unsafe_allow_html=True)
with ct3:
    if st.button("➕ pół tonu", key="t_up", use_container_width=True):
        st.session_state.transposition += 1
        st.rerun()

st.markdown('<hr style="opacity: 0.1;">', unsafe_allow_html=True)

col_rate_info, col_rate_act = st.columns([1, 2])
with col_rate_info:
    avg = song["ratings_sum"] / song["ratings_count"] if song["ratings_count"] > 0 else 0
    st.markdown(f"<div style='font-size:12px; color:#888;'>Średnia: <b>{avg:.1f}</b><br>Głosów: {song['ratings_count']}</div>", unsafe_allow_html=True)
with col_rate_act:
    score = st.feedback("stars", key="rating_feedback") 
    if score is None: 
         score_rad = st.radio("Oceń:", [1,2,3,4,5], horizontal=True, label_visibility="collapsed", key="rating_radio_backup")
         if st.button("Zapisz", key="save_rating_btn", use_container_width=True):
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

st.markdown('<hr style="opacity: 0.1;">', unsafe_allow_html=True)

st.caption("Sugerowane tagi (kliknij by dodać):")
score_for_tags = 3 
if 'rating_radio_backup' in st.session_state: score_for_tags = st.session_state.rating_radio_backup

if score_for_tags in RATING_TAGS:
    render_compact_tags(RATING_TAGS[score_for_tags], f"sug_{score_for_tags}", 
        lambda t: (song["tags"].append(t) or update_song_tags(song["row"], song["tags"]) or reload_songs() or st.rerun()) 
        if t not in song.get("tags", []) else None)

st.caption("Tagi tej piosenki. X usuwa tę etykietę")
current_tags = song.get("tags", [])

if current_tags:
    st.markdown('<div class="tag-btn">', unsafe_allow_html=True)
    cols = st.columns(4)
    for i, tag in enumerate(current_tags):
        with cols[i % 4]:
            if st.button(f"✕ {tag}", key=f"del_{i}", use_container_width=True):
                song["tags"].remove(tag)
                update_song_tags(song["row"], song["tags"])
                reload_songs()
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# USUNIĘTO SEKCJĘ "POPULARNE TAGI" Z TEGO MIEJSCA

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

st.markdown('<hr style="opacity: 0.1;">', unsafe_allow_html=True)

st.subheader("📚 Polecane")
# Zaktualizowane taby - dodano "Wg Tagów"
tab_tags, tab_rand, tab_top = st.tabs(["🏷️ Wg Tagów", "🎲 Losowe", "🏆 Top Oceniane"])

with tab_tags:
    st.caption("Wybierz tag, aby zobaczyć listę piosenek:")
    # Pobieranie wszystkich unikalnych tagów z bazy
    all_unique_tags = sorted(list(set(t for s in st.session_state.songs for t in s.get("tags", []))))
    
    selected_tag_search = st.selectbox("Wybierz tag:", [""] + all_unique_tags, key="tag_search_box")
    
    if selected_tag_search:
        tagged_songs = [s for s in st.session_state.songs if selected_tag_search in s.get("tags", [])]
        st.write(f"Znaleziono {len(tagged_songs)} piosenek:")
        
        st.markdown('<div class="list-btn">', unsafe_allow_html=True)
        # Wyświetlamy wszystkie (można by stronicować, ale prośba była o "dość liczną" listę)
        for i, ts in enumerate(tagged_songs):
            # Używamy unikalnego klucza dla przycisku
            if st.button(f"{ts['title']}", key=f"tag_search_res_{i}", use_container_width=True):
                # Znajdź indeks w głównej tablicy i przełącz
                real_idx = next((j for j, s in enumerate(st.session_state.songs) if s["title"] == ts["title"]), 0)
                set_song_by_idx(real_idx)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

with tab_rand:
    if st.button("🔄 Losuj inne", key="reroll_recs", use_container_width=True):
        # Użycie nowej funkcji rotacyjnej
        st.session_state.random_sample = get_recommended_songs_rotational(st.session_state.songs, limit=5)
        st.rerun()
        
    st.markdown('<div class="list-btn">', unsafe_allow_html=True)
    for i, rs in enumerate(st.session_state.random_sample):
        # Oznaczenie wizualne dla piosenek z ocenami vs bez (opcjonalne, ale pomocne)
        prefix = "⭐" if rs["ratings_count"] > 0 else "🆕"
        if st.button(f"{prefix} {rs['title']}", key=f"rec_r_{i}", use_container_width=True):
            set_song_by_idx(next((j for j, s in enumerate(st.session_state.songs) if s["title"] == rs["title"]), 0))
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.caption("Legenda: ⭐ Oceniana, 🆕 Nowa/Niezbadana")

with tab_top:
    top_visited = get_most_visited_songs(st.session_state.songs, limit=5)
    st.markdown('<div class="list-btn">', unsafe_allow_html=True)
    for i, ts in enumerate(top_visited):
         if st.button(f"{i+1}. {ts['title']} (głosów: {ts['ratings_count']})", key=f"rec_t_{i}", use_container_width=True):
            set_song_by_idx(next((j for j, s in enumerate(st.session_state.songs) if s["title"] == ts["title"]), 0))
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

with st.expander("🛠️ Panel Administracyjny"):
    tab_edit, tab_add, tab_del, tab_stats = st.tabs(["✏️ Edytuj bieżący", "➕ Dodaj piosenkę", "🗑️ Usuń", "📊 Statystyki"])
    
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
        st.subheader("Nowa piosenka")
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
        st.subheader("📊 Statystyki")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📚 Liczba piosenek", len(st.session_state.songs))
        
        with col2:
            rated_songs = [s for s in st.session_state.songs if s["ratings_count"] > 0]
            st.metric("⭐ Oceniane piosenki", len(rated_songs))
        
        with col3:
            total_ratings = sum(s["ratings_count"] for s in st.session_state.songs)
            st.metric("🗳️ Łącznie ocen", total_ratings)
        
        with col4:
            avg_rating = sum(s["ratings_sum"] for s in st.session_state.songs) / max(total_ratings, 1) if total_ratings > 0 else 0
            st.metric("⬇️ Średnia ocena", f"{avg_rating:.2f}")
        
        st.markdown("---")
        
        st.caption("🔥 Najczęściej odwiedzane piosenki:")
        most_visited = get_most_visited_songs(st.session_state.songs, limit=10)
        if most_visited:
            for i, s in enumerate(most_visited, 1):
                avg = s["ratings_sum"] / s["ratings_count"] if s["ratings_count"] > 0 else 0
                st.write(f"{i}. **{s['title']}** - {s['ratings_count']} ocen (średnia: {avg:.1f})")
        
        st.markdown("---")
        
        st.caption("🏆 Najczęściej używane tagi:")
        all_tags_list = get_most_common_tags(st.session_state.songs, limit=20)
        if all_tags_list:
            tag_counts = Counter()
            for s in st.session_state.songs:
                tag_counts.update(s.get("tags", []))
            
            for i, (tag, count) in enumerate(tag_counts.most_common(20), 1):
                st.write(f"{i}. **{tag}** - {count}x")
        else:
            st.info("Brak tagów")
