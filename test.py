import requests, re, yaml, sqlite3, traceback, html
from selenium import webdriver

with open('config.yaml', 'r', encoding='utf-8') as f:
    config = dict(yaml.safe_load(f))

# sql
sql_create_song = '''CREATE TABLE IF NOT EXISTS songs(
                    id      TEXT    PRIMARY KEY     NOT NULL,
                    artist  TEXT,
                    title   TEXT,
                    sub     TEXT,
                    ver     TEXT,
                    genre   TEXT,
                    bpm     TEXT
                    )'''
sql_create_map = '''CREATE TABLE IF NOT EXISTS maps(
                    id      TEXT    NOT NULL,
                    type    TEXT    NOT NULL,
                    level   INTEGER,
                    note    INTEGER,
                    diff    TEXT,
                    clear   INTEGER
                    )'''
sql_create_map_index = '''CREATE INDEX IF NOT EXISTS idx_id_type ON maps(id, type)'''
sql_select_song = '''SELECT id, genre, artist, title, sub, bpm, ver FROM songs WHERE id = \'{id}\''''
sql_insert_song = '''INSERT INTO songs(id, genre, artist, title, sub, bpm, ver) VALUES (\'{id}\', \'{genre}\', \'{artist}\', \'{title}\', \'{sub}\', \'{bpm}\', \'{ver}\')'''
sql_update_song = '''UPDATE songs SET genre=\'{genre}\', artist=\'{artist}\', title=\'{title}\', sub=\'{sub}\', bpm=\'{bpm}\', ver=\'{ver}\' WHERE id=\'{id}\''''
sql_select_map = '''SELECT id, type, level, note, diff, clear FROM maps WHERE id=\'{id}\' AND type=\'{type}\''''
sql_insert_map = '''INSERT INTO maps(id, type, level, note, diff, clear) VALUES (\'{id}\', \'{type}\', {level}, {note}, \'{diff}\', {clear})'''
sql_update_map = '''UPDATE maps SET level={level}, note={note} WHERE id=\'{id}\' AND type=\'{type}\''''

def handle_html(str) -> str:
    return html.unescape(re.sub('<[^>]*>', '', str).strip())

def escape_chars(str) -> str:
    return re.sub('([\'])', '\\$1', str)

def get_js(url) -> str:
    req = requests.get(url)
    req.encoding = 'Shift-JIS'
    return req.text

def update_song():
    global db_conn, db_cursor

    url_song_info = config.get('url_song_info')
    url_map_info = config.get('url_map_info')
    url_note_bpm = config.get('url_note_bpm')
    url_version = config.get('url_version')
    type_name = ['spb', 'spn', 'sph', 'spa', 'spl', 'dpb', 'dpn', 'dph', 'dpa', 'dpl']
    type_idx = [3, 5, 7, 9, 11, 13, 15, 17, 19, 21]
    # 执行js
    chrome_option = webdriver.ChromeOptions()
    chrome_option.add_argument('headless')
    chrome = webdriver.Chrome(options=chrome_option)
    chrome.get('about:blank')

    chrome.execute_script(get_js(url_song_info))
    chrome.execute_script(get_js(url_map_info))
    chrome.execute_script(get_js(url_note_bpm))
    js_version = get_js(url_version)
    js_version = js_version[:js_version.find('referstr')]
    chrome.execute_script(js_version)
    # id: [ver, _, _, genre, artist, title, subtitle]
    song_info = dict(chrome.execute_script('return titletbl'))
    # id: [spb:3, spn:5, sph:7, spa:9, spl:11, dpb:13, dpn:15, dph:17, dpa:19, dpl:21, title_note:23]
    map_difficulty = dict(chrome.execute_script('return actbl'))
    # id: [_, spb, spn, sph, spa, spl, dpb, dpn, dph, dpa, dpl, bpm]
    map_note_bpm = dict(chrome.execute_script('return datatbl'))
    version_name = list(chrome.execute_script('return vertbl'))

    for id, info in song_info.items():
        note_bpm = map_note_bpm.get(id)
        map_diff = map_difficulty.get(id)
        if note_bpm is None or map_diff is None:
            continue
        try:
            # song
            dict_song = dict()
            dict_song['id'] = id
            dict_song['ver'] = version_name[info[0]]
            dict_song['genre'] = escape_chars(handle_html(info[3]))
            dict_song['artist'] = escape_chars(handle_html(info[4]))
            dict_song['title'] = escape_chars(handle_html(info[5]))
            sub = ''
            if len(info)>6: 
                sub += handle_html(info[6])
            if len(note_bpm)>23:
                sub += handle_html(map_diff[23])
            dict_song['sub'] = escape_chars(sub)
            dict_song['bpm'] = note_bpm[11]
            db_cursor.execute(sql_select_song.format(**dict_song))
            if len(db_cursor.fetchall()) == 0:
                db_cursor.execute(sql_insert_song.format(**dict_song))
            else:
                db_cursor.execute(sql_update_song.format(**dict_song))
            # map
            for i in range(len(type_idx)):
                level = map_diff[type_idx[i]]
                if level == 0:
                    continue
                dict_map = dict()
                dict_map['id'] = id
                dict_map['type'] = type_name[i]
                dict_map['level'] = level
                dict_map['note'] = note_bpm[i+1]
                dict_map['diff'] = '未定级'
                dict_map['clear'] = 0         
                db_cursor.execute(sql_select_map.format(**dict_map))
                if len(db_cursor.fetchall()) == 0:
                    db_cursor.execute(sql_insert_map.format(**dict_map))
                else:
                    db_cursor.execute(sql_update_map.format(**dict_map))
            db_conn.commit()
        except Exception as e:
            traceback.print_exc()

    chrome.quit()

def open_database():
    global db_conn, db_cursor
    db_name = config.get('db_name')
    db_conn = sqlite3.connect(db_name)
    db_cursor = db_conn.cursor()
    db_cursor.execute(sql_create_song)
    db_cursor.execute(sql_create_map)
    db_cursor.execute(sql_create_map_index)
    db_conn.commit()

if __name__ == '__main__':
    open_database()
    update_song()