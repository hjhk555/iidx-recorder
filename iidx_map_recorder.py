import requests, re, yaml, sqlite3, traceback, html, sys
import matplotlib.pyplot as plt
from selenium import webdriver
from typing import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from fuzzywuzzy import fuzz

with open('config.yaml', 'r', encoding='utf-8') as f:
    config = dict(yaml.safe_load(f))

# global
dict_songs: Dict[str, 'SongInfo'] = dict()
dict_full_type = {'B': 'BASIC', 'N': 'NORMAL', 'H': 'HARD', 'A': 'ANOTHER', 'L': 'LEGGENDARIA'}
clear_name = config.get('clear_status')
db_conn: sqlite3.Connection
db_cursor: sqlite3.Cursor

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
                    base    TEXT,
                    clear   INTEGER
                    )'''
sql_create_map_index = '''CREATE INDEX IF NOT EXISTS idx_id_type ON maps(id, type)'''
sql_select_song = '''SELECT id, genre, artist, title, sub, bpm, ver FROM songs WHERE id = \'{id}\''''
sql_select_all_song = '''SELECT id, genre, artist, title, sub, bpm, ver FROM songs'''
sql_insert_song = '''INSERT INTO songs(id, genre, artist, title, sub, bpm, ver) VALUES (\'{id}\', \'{genre}\', \'{artist}\', \'{title}\', \'{sub}\', \'{bpm}\', \'{ver}\')'''
sql_update_song = '''UPDATE songs SET genre=\'{genre}\', artist=\'{artist}\', title=\'{title}\', sub=\'{sub}\', bpm=\'{bpm}\', ver=\'{ver}\' WHERE id=\'{id}\''''
sql_select_map = '''SELECT id, type, level, note, base, clear FROM maps WHERE id=\'{id}\' AND type=\'{type}\''''
sql_select_all_map = '''SELECT id, type, level, note, base, clear FROM maps'''
sql_insert_map = '''INSERT INTO maps(id, type, level, note, base, clear) VALUES (\'{id}\', \'{type}\', {level}, {note}, \'{base}\', {clear})'''
sql_update_map_info = '''UPDATE maps SET level={level}, note={note} WHERE id=\'{id}\' AND type=\'{type}\''''
sql_update_full_map = '''UPDATE maps SET level={level}, note={note}, base=\'{base}\', clear={clear} WHERE id=\'{id}\' AND type=\'{type}\''''

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
    type_name = ['SPB', 'SPN', 'SPH', 'SPA', 'SPL', 'DPB', 'DPN', 'DPH', 'DPA', 'DPL']
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
    dict_song_info = dict(chrome.execute_script('return titletbl'))
    # id: [spb:3, spn:5, sph:7, spa:9, spl:11, dpb:13, dpn:15, dph:17, dpa:19, dpl:21, title_note:23]
    dict_map_level = dict(chrome.execute_script('return actbl'))
    # id: [_, spb, spn, sph, spa, spl, dpb, dpn, dph, dpa, dpl, bpm]
    dict_map_note_bpm = dict(chrome.execute_script('return datatbl'))
    list_version_name = list(chrome.execute_script('return vertbl'))

    for id, info in dict_song_info.items():
        note_bpm = dict_map_note_bpm.get(id)
        map_level = dict_map_level.get(id)
        if note_bpm is None or map_level is None:
            continue
        try:
            # song
            song_info = dict()
            song_info['id'] = id
            song_info['ver'] = list_version_name[info[0]]
            song_info['genre'] = escape_chars(handle_html(info[3]))
            song_info['artist'] = escape_chars(handle_html(info[4]))
            song_info['title'] = escape_chars(handle_html(info[5]))
            sub = ''
            if len(info)>6: 
                sub += handle_html(info[6])
            if len(note_bpm)>23:
                sub += handle_html(map_level[23])
            song_info['sub'] = escape_chars(sub)
            song_info['bpm'] = note_bpm[11]
            db_cursor.execute(sql_select_song.format(**song_info))
            if len(db_cursor.fetchall()) == 0:
                db_cursor.execute(sql_insert_song.format(**song_info))
            else:
                db_cursor.execute(sql_update_song.format(**song_info))
            # map
            for i in range(len(type_idx)):
                level = map_level[type_idx[i]]
                if level == 0:
                    continue
                map_info = dict()
                map_info['id'] = id
                map_info['type'] = type_name[i]
                map_info['level'] = level
                map_info['note'] = note_bpm[i+1]
                map_info['base'] = '未定级'
                map_info['clear'] = 0         
                db_cursor.execute(sql_select_map.format(**map_info))
                if len(db_cursor.fetchall()) == 0:
                    db_cursor.execute(sql_insert_map.format(**map_info))
                else:
                    db_cursor.execute(sql_update_map_info.format(**map_info))
            db_conn.commit()
        except Exception as e:
            traceback.print_exc()
    chrome.quit()
    read_song_map()

def open_database():
    global db_conn, db_cursor
    db_name = config.get('db_name')
    db_conn = sqlite3.connect(db_name)
    db_cursor = db_conn.cursor()
    db_cursor.execute(sql_create_song)
    db_cursor.execute(sql_create_map)
    db_cursor.execute(sql_create_map_index)
    db_conn.commit()
    
def new_label(text, fixed = True, font = 'Arial', font_size = 10, alignment = Qt.AlignCenter) -> QLabel:
    label = QLabel(text)
    label.setFont(QFont(font, font_size))
    label.setAlignment(alignment)
    label.adjustSize()
    label.setScaledContents(True)
    if fixed:
        label.setFixedSize(label.width(), label.height())
    return label

def new_layout_labeled_combo(text, combo: QComboBox = None) -> tuple[QLayout, QComboBox]:
    layout = QHBoxLayout()
    layout.addWidget(new_label(text))
    if combo is None:
        combo = QComboBox()
    combo.setEditable(True)
    combo.completer().setCompletionMode(0)
    combo.completer().setFilterMode(Qt.MatchContains)
    layout.addWidget(combo)
    return layout, combo

class SongInfo:
    id: str
    title: str
    sub_title: str
    version: str
    artist: str
    genre: str
    bpm: str
    maps: Dict[str, 'MapInfo']
    def __init__(self, **kwargs):
        self.maps = dict()
        self.update(**kwargs)
    def update(self, **kwargs):
        self.id = kwargs.get('id')
        self.title = kwargs.get('title')
        self.sub_title = kwargs.get('sub_title')
        self.version = kwargs.get('version')
        self.artist = kwargs.get('artist')
        self.genre = kwargs.get('genre')
        self.bpm = kwargs.get('bpm')
    def add_map(self, **kwargs):
        map = MapInfo(self, **kwargs)
        self.maps[map.get_full_type()] = map

class MapInfo:
    song: SongInfo
    style: str
    type: str
    level: int
    notes: int
    base: str
    clear: int
    def __init__(self, song: SongInfo, **kwargs):
        self.song = song
        self.update(**kwargs)
    def update(self, **kwargs):
        self.style = kwargs.get('style')
        self.type = kwargs.get('type')
        self.level = kwargs.get('level')
        self.notes = kwargs.get('notes')
        self.base = kwargs.get('base')
        self.clear = kwargs.get('clear')
    def get_full_type(self):
        return self.style+self.type[:1]
    def save(self):
        global db_conn, db_cursor
        db_cursor.execute(sql_update_full_map.format(id=self.song.id, type=self.get_full_type(), level=self.level, note=self.notes, base=self.base, clear=self.clear))
        db_conn.commit()

def read_song_map():
    global db_cursor, dict_songs
    db_cursor.execute(sql_select_all_song)
    for row in db_cursor.fetchall():
        id = row[0]
        if id is None:
            continue
        song_info = dict()
        song_info['id'] = id
        song_info['genre'] = row[1]
        song_info['artist'] = row[2]
        song_info['title'] = row[3]
        song_info['sub_title'] = row[4]
        song_info['bpm'] = row[5]
        song_info['version'] = row[6]
        song = dict_songs.get(id)
        if song is None:
            dict_songs[id] = SongInfo(**song_info)
        else:
            song.update(**song_info)
    
    db_cursor.execute(sql_select_all_map)
    for row in db_cursor.fetchall():
        id = row[0]
        type_name = row[1]
        if id is None or type_name is None:
            continue
        song = dict_songs.get(id)
        if song is None:
            continue
        _type = dict_full_type.get(type_name[2:])
        if _type is None:
            continue
        clear = row[5]
        if clear >= len(clear_name):
            continue
        map_info = dict()
        map_info['style'] = type_name[:2]
        map_info['type'] = _type
        map_info['level'] = row[2]
        map_info['notes'] = row[3]
        map_info['base'] = row[4]
        map_info['clear'] = clear
        map = song.maps.get(type_name)
        if map is None:
            song.add_map(**map_info)
        else:
            map.update(**map_info)

def new_clear_status_combo() -> QComboBox:
    combo = QComboBox()
    for i in range(len(clear_name)):
        combo.addItem(clear_name[i])
    return combo

class WidgetSongInfo(QWidget):
    info: SongInfo
    def __init__(self, info: SongInfo):
        super().__init__()
        self.info = info

class WidgetMapInfo(QWidget):
    info: MapInfo
    wgt_clear: QComboBox
    btn_select: QPushButton

    def __init__(self, info: MapInfo):
        super().__init__()
        self.info = info

        layout_main = QHBoxLayout()
        self.setLayout(layout_main)

        self.wgt_clear = new_clear_status_combo()
        self.wgt_clear.setMaximumWidth(120)
        layout_main.addWidget(self.wgt_clear)

        layout_title = QVBoxLayout()
        self.label_title = new_label('', font_size=15, fixed=False)
        layout_title.addWidget(self.label_title)
        self.label_sub_title = new_label('', fixed=False, font_size=8)
        layout_title.addWidget(self.label_sub_title)
        self.label_artist = new_label('', fixed=False)
        layout_title.addWidget(self.label_artist)
        self.label_genre = new_label('', fixed=False, font_size=8)
        layout_title.addWidget(self.label_genre)
        self.label_other_info = new_label('', fixed=False)
        layout_title.addWidget(self.label_other_info)
        layout_main.addLayout(layout_title)

        layout_level = QVBoxLayout()
        self.label_level = new_label('', fixed=False, font_size=15)
        layout_level.addWidget(self.label_level)
        self.label_base = new_label('', fixed=False, font_size=12)
        layout_level.addWidget(self.label_base)
        layout_main.addLayout(layout_level)

        self.btn_select = QPushButton()
        self.btn_select.setFixedWidth(100)
        self.btn_select.setFixedHeight(50)
        layout_main.addWidget(self.btn_select)

        self.update()
    def set_clear_changed_action(self, action: Callable[[Self], None]):
        if action is None:
            return
        self.wgt_clear.currentIndexChanged.connect(lambda x: action(self))
    def set_selected_action(self, action: Callable[[Self], None]):
        if action is None:
            return
        self.btn_select.clicked.connect(lambda x: action(self))
    def update(self):
        self.wgt_clear.setCurrentIndex(self.info.clear)
        self.label_title.setText(self.info.song.title)
        self.label_sub_title.setText(self.info.song.sub_title)
        self.label_artist.setText(self.info.song.artist)
        self.label_genre.setText(self.info.song.genre)
        self.label_other_info.setText(f'{self.info.song.bpm} BPM    {self.info.notes} NOTES    {self.info.song.version}')
        self.label_level.setText(f'{self.info.get_full_type()} {self.info.level}')
        self.label_base.setText(self.info.base)

def add_widget_to_list(widget: QWidget, list: QListWidget) -> QListWidgetItem:
    item = QListWidgetItem()
    item.setSizeHint(widget.sizeHint())
    list.addItem(item)
    list.setItemWidget(item, widget)
    return item

class WidgetSongFilter(QGroupBox):
    combo_artist: QComboBox
    combo_genre: QComboBox
    combo_title: QComboBox
    combo_version: QComboBox
    combo_bpm: QComboBox
    def __init__(self, parent = None):
        super().__init__('曲目筛选', parent)
        layout_main = QVBoxLayout()
        self.setLayout(layout_main)

        layout, self.combo_title = new_layout_labeled_combo('*曲名*：')
        layout_main.addLayout(layout)

        layout, self.combo_artist = new_layout_labeled_combo('*曲师*：')
        layout_main.addLayout(layout)

        layout_line3 = QHBoxLayout()
        layout, self.combo_genre = new_layout_labeled_combo('*曲风*：')
        layout_line3.addLayout(layout)
        layout, self.combo_bpm = new_layout_labeled_combo('*BPM*：')
        layout_line3.addLayout(layout)
        layout, self.combo_version = new_layout_labeled_combo('版本：')
        layout_line3.addLayout(layout)
        layout_line3.setStretch(0, 3)
        layout_line3.setStretch(1, 1)
        layout_line3.setStretch(2, 1)
        layout_main.addLayout(layout_line3)
    def clear(self):
        self.combo_title.clear()
        self.combo_genre.clear()
        self.combo_version.clear()
        self.combo_artist.clear()
        self.combo_bpm.clear()
    def clear_text(self):
        self.combo_title.clearEditText()
        self.combo_genre.clearEditText()
        self.combo_version.clearEditText()
        self.combo_artist.clearEditText()
        self.combo_bpm.clearEditText()

class WidgetMapFilter(QWidget):
    wgt_song_filter: WidgetSongFilter
    combo_base: QComboBox
    combo_clear: QComboBox
    combo_level: QComboBox
    combo_style: QComboBox
    combo_type: QComboBox
    def __init__(self, parent = None):
        super().__init__(parent)
        layout_main = QVBoxLayout()
        self.setLayout(layout_main)

        self.wgt_song_filter = WidgetSongFilter(self)
        layout_main.addWidget(self.wgt_song_filter)

        wgt_map_filter = QGroupBox('谱面筛选')
        layout_map_filter = QVBoxLayout()
        wgt_map_filter.setLayout(layout_map_filter)

        layout_line1 = QHBoxLayout()
        layout, self.combo_style = new_layout_labeled_combo('游玩风格：')
        layout_line1.addLayout(layout)
        layout, self.combo_type = new_layout_labeled_combo('类型：')
        layout_line1.addLayout(layout)
        layout, self.combo_level = new_layout_labeled_combo('难度：')
        layout_line1.addLayout(layout)
        layout, self.combo_base = new_layout_labeled_combo('定数：')
        layout_line1.addLayout(layout)
        layout, self.combo_clear = new_layout_labeled_combo('通关状态：')
        layout_line1.addLayout(layout)
        layout_map_filter.addLayout(layout_line1)
        layout_main.addWidget(wgt_map_filter)
    def clear(self):
        self.wgt_song_filter.clear()
        self.combo_clear.clear()
        self.combo_base.clear()
        self.combo_type.clear()
        self.combo_level.clear()
        self.combo_style.clear()
    def clear_text(self):
        self.wgt_song_filter.clear_text()
        self.combo_clear.clearEditText()
        self.combo_base.clearEditText()
        self.combo_type.clearEditText()
        self.combo_level.clearEditText()
        self.combo_style.clearEditText()

# class WidgetSongSearch(QWidget):

def set_to_sorted_list(target: set, key = None) -> list:
     res = list(target)
     res.sort(key = key)
     return res

class WidgetMapSearch(QWidget):
    wgt_filter: WidgetMapFilter
    wgt_map_list: QVBoxLayout
    btn_search: QPushButton
    btn_clear_text: QPushButton
    btn_load: QPushButton
    list_maps: List[MapInfo] = []
    def __init__(self, clear_editable = True, on_clear_change: Callable[[WidgetMapInfo], None] = None, text_map_select ='选择', on_map_select: Callable[[WidgetMapInfo], None] = None, parent = None):
        super().__init__(parent)

        self.clear_editable = clear_editable
        self.on_clear_change = on_clear_change
        self.text_map_select = text_map_select
        self.on_map_select = on_map_select

        layout_main = QVBoxLayout()
        self.setLayout(layout_main)

        self.wgt_filter = WidgetMapFilter(self)
        layout_main.addWidget(self.wgt_filter)

        layout_line2 = QHBoxLayout()

        self.btn_clear_text = QPushButton('重置')
        self.btn_clear_text.setMaximumWidth(150)
        self.btn_clear_text.clicked.connect(self.reset)
        layout_line2.addWidget(self.btn_clear_text)
        self.btn_search = QPushButton('检索')
        self.btn_search.setMaximumWidth(150)
        self.btn_search.clicked.connect(self.do_search)
        layout_line2.addWidget(self.btn_search)
        self.btn_sort_clear = QPushButton('检索并按通关状态排序(禁用模糊搜索和通关状态过滤器)')
        self.btn_sort_clear.setMaximumWidth(500)
        self.btn_sort_clear.clicked.connect(self.sort_by_clear)
        layout_line2.addWidget(self.btn_sort_clear)
        layout_main.addLayout(layout_line2)
        
        scroll_area = QScrollArea()
        scroll_area.setMinimumHeight(750)
        scroll_area.setWidgetResizable(True)
        self.wgt_map_list = QListWidget()
        scroll_area.setWidget(self.wgt_map_list)
        layout_main.addWidget(scroll_area)
        self.reset()

        self.fetch_combo_options()
        self.do_search()
    def inner_on_clear_change(self, widget: WidgetMapInfo):
        if self.on_clear_change is not None:
            self.on_clear_change(widget)
        self.fetch_combo_options()
    def inner_on_map_select(self, widget: WidgetMapInfo):
        if self.on_map_select is not None:
            self.on_map_select(widget)
        self.fetch_combo_options()
    def reset(self):
        self.wgt_filter.clear_text()
        self.do_search()
    def fetch_combo_options(self):
        opt_title = set()
        opt_artist = set()
        opt_bpm = set()
        opt_genre = set()
        opt_version = set()
        opt_style = set()
        opt_type = set()
        opt_level = set()
        opt_base = set()
        opt_clear = set()
        for song in dict_songs.values():
            opt_title.add(song.title)
            opt_artist.add(song.artist)
            opt_bpm.add(song.bpm)
            opt_genre.add(song.genre)
            opt_version.add(song.version)
            for map in song.maps.values():
                opt_style.add(map.style)
                opt_type.add(map.type)
                opt_level.add(str(map.level))
                opt_base.add(map.base)
                opt_clear.add(clear_name[map.clear])
        filter_title = self.wgt_filter.wgt_song_filter.combo_title.currentText()
        filter_artist = self.wgt_filter.wgt_song_filter.combo_artist.currentText()
        filter_genre = self.wgt_filter.wgt_song_filter.combo_genre.currentText()
        filter_bpm = self.wgt_filter.wgt_song_filter.combo_bpm.currentText()
        filter_version = self.wgt_filter.wgt_song_filter.combo_version.currentText()
        filter_style = self.wgt_filter.combo_style.currentText()
        filter_type = self.wgt_filter.combo_type.currentText()
        filter_level = self.wgt_filter.combo_level.currentText()
        filter_base = self.wgt_filter.combo_base.currentText()
        filter_clear = self.wgt_filter.combo_clear.currentText()
        self.wgt_filter.clear()
        self.wgt_filter.wgt_song_filter.combo_title.addItems(set_to_sorted_list(opt_title))
        self.wgt_filter.wgt_song_filter.combo_version.addItems(set_to_sorted_list(opt_version))
        self.wgt_filter.wgt_song_filter.combo_bpm.addItems(set_to_sorted_list(opt_bpm))
        self.wgt_filter.wgt_song_filter.combo_genre.addItems(set_to_sorted_list(opt_genre))
        self.wgt_filter.wgt_song_filter.combo_artist.addItems(set_to_sorted_list(opt_artist))
        self.wgt_filter.combo_clear.addItems(set_to_sorted_list(opt_clear, lambda x: clear_name.index(x)))
        self.wgt_filter.combo_type.addItems(set_to_sorted_list(opt_type, lambda x: list(dict_full_type.values()).index(x)))
        self.wgt_filter.combo_base.addItems(set_to_sorted_list(opt_base))
        self.wgt_filter.combo_style.addItems(set_to_sorted_list(opt_style, lambda x: 0 if x=='SP' else 1))
        self.wgt_filter.combo_level.addItems(set_to_sorted_list(opt_level, lambda x: int(x)))
        self.wgt_filter.wgt_song_filter.combo_title.setCurrentText(filter_title)
        self.wgt_filter.wgt_song_filter.combo_artist.setCurrentText(filter_artist)
        self.wgt_filter.wgt_song_filter.combo_genre.setCurrentText(filter_genre)
        self.wgt_filter.wgt_song_filter.combo_bpm.setCurrentText(filter_bpm)
        self.wgt_filter.wgt_song_filter.combo_version.setCurrentText(filter_version)
        self.wgt_filter.combo_style.setCurrentText(filter_style)
        self.wgt_filter.combo_type.setCurrentText(filter_type)
        self.wgt_filter.combo_level.setCurrentText(filter_level)
        self.wgt_filter.combo_base.setCurrentText(filter_base)
        self.wgt_filter.combo_clear.setCurrentText(filter_clear)
    def do_search(self):
        self.list_maps.clear()
        filter_title = self.wgt_filter.wgt_song_filter.combo_title.currentText().strip()
        filter_artist = self.wgt_filter.wgt_song_filter.combo_artist.currentText().strip()
        filter_genre = self.wgt_filter.wgt_song_filter.combo_genre.currentText().strip()
        filter_bpm = self.wgt_filter.wgt_song_filter.combo_bpm.currentText().strip()
        filter_version = self.wgt_filter.wgt_song_filter.combo_version.currentText().strip()
        filter_style = self.wgt_filter.combo_style.currentText().strip()
        filter_type = self.wgt_filter.combo_type.currentText().strip()
        filter_level = self.wgt_filter.combo_level.currentText().strip()
        filter_base = self.wgt_filter.combo_base.currentText().strip()
        filter_clear = self.wgt_filter.combo_clear.currentText().strip()

        for song in dict_songs.values():
            if filter_bpm!='' and filter_bpm not in song.bpm or \
                    filter_version!='' and song.version!=filter_version:
                continue
            for map in song.maps.values():
                if filter_style!='' and map.style!=filter_style or \
                        filter_type != '' and map.type != filter_type or \
                        filter_level != '' and str(map.level) != filter_level or \
                        filter_base != '' and map.base != filter_base or \
                        filter_clear != '' and clear_name[map.clear] != filter_clear:
                    continue
                self.list_maps.append(map)

        self.list_maps.sort(key=lambda x : (x.song.title, x.song.sub_title))
        if filter_genre!='':
            self.list_maps.sort(key=lambda x : (-fuzz.partial_ratio(filter_genre.upper(), x.song.genre.upper()), abs(len(x.song.genre)- len(filter_genre))))
        if filter_artist!='':
            self.list_maps.sort(key=lambda x : (-fuzz.partial_ratio(filter_artist.upper(), x.song.artist.upper()), abs(len(x.song.artist)-len(filter_artist))))
        if filter_title!='':
            self.list_maps.sort(key=lambda x : (-fuzz.partial_ratio(filter_title.upper(), (x.song.title+' '+x.song.sub_title).upper()), abs(len(x.song.title)+len(x.song.sub_title)-len(filter_title))))
        self.wgt_map_list.clear()
        self.load_songs()
    def load_songs(self, beginIdx=0, count=100):
        cur_len = len(self.wgt_map_list)
        if cur_len > 0:
            self.wgt_map_list.takeItem(cur_len-1)
        if len(self.list_maps) == 0:
            add_widget_to_list(new_label('未找到谱面，请调整过滤条件或从textage.cc导入谱面数据', font_size=15), self.wgt_map_list)
        endIdx = min(beginIdx+count, len(self.list_maps))
        for i in range(beginIdx, endIdx):
            widget_map_info = WidgetMapInfo(self.list_maps[i])
            widget_map_info.wgt_clear.setEnabled(self.clear_editable)
            widget_map_info.btn_select.setText(self.text_map_select)
            widget_map_info.set_clear_changed_action(self.inner_on_clear_change)
            widget_map_info.set_selected_action(self.on_map_select)
            add_widget_to_list(widget_map_info, self.wgt_map_list)
        next_load = min(count, len(self.list_maps)-endIdx)
        if next_load > 0:
            widget = QWidget()
            layout = QHBoxLayout()
            widget.setLayout(layout)
            btn_load = QPushButton(f'加载后{next_load}张谱面')
            btn_load.setMaximumWidth(300)
            btn_load.clicked.connect(lambda x: self.load_songs(endIdx, next_load))
            layout.addWidget(btn_load)
            add_widget_to_list(widget, self.wgt_map_list)
    def sort_by_clear(self):
        self.wgt_filter.wgt_song_filter.combo_title.clearEditText()
        self.wgt_filter.wgt_song_filter.combo_genre.clearEditText()
        self.wgt_filter.wgt_song_filter.combo_artist.clearEditText()
        self.wgt_filter.wgt_song_filter.combo_bpm.clearEditText()
        self.wgt_filter.combo_clear.clearEditText()
        self.do_search()
        self.list_maps.sort(key=lambda map: -map.clear)
        self.wgt_map_list.clear()
        self.load_songs()

def on_map_clear_changed(widget: WidgetMapInfo):
    new_clear = widget.wgt_clear.currentIndex()
    map_info = widget.info
    map_info.clear = new_clear
    map_info.save()
    widget.update()

class PageMapManage(QWidget):
    def __init__(self, parent = None):
        super().__init__(parent)

        layout_main = QVBoxLayout()
        self.setLayout(layout_main)

        self.wgt_map_search = WidgetMapSearch(on_clear_change=on_map_clear_changed)
        layout_main.addWidget(self.wgt_map_search)

        layout_tools = QHBoxLayout()
        self.btn_update_songs = QPushButton('从textage.cc获取谱面数据（需要一定时间）')
        self.btn_update_songs.setFixedWidth(400)
        self.btn_update_songs.clicked.connect(self.on_click_update_songs)
        layout_tools.addWidget(self.btn_update_songs)
        self.btn_gen_pie_pic = QPushButton('生成当前过滤条件（除模糊搜索、通关状态）的完成度图')
        self.btn_gen_pie_pic.setFixedWidth(500)
        self.btn_gen_pie_pic.clicked.connect(self.on_click_gen_pie_pic)
        layout_tools.addWidget(self.btn_gen_pie_pic)
        layout_main.addLayout(layout_tools)
    def on_click_update_songs(self):
        update_song()
        self.wgt_map_search.fetch_combo_options()
        self.wgt_map_search.reset()
    def on_click_gen_pie_pic(self):
        self.wgt_map_search.sort_by_clear()
        if len(self.wgt_map_search.list_maps) == 0:
            return
        title = '谱面完成度'
        filter_version = self.wgt_map_search.wgt_filter.wgt_song_filter.combo_version.currentText().strip()
        filter_style = self.wgt_map_search.wgt_filter.combo_style.currentText().strip()
        filter_type = self.wgt_map_search.wgt_filter.combo_type.currentText().strip()
        filter_level = self.wgt_map_search.wgt_filter.combo_level.currentText().strip()
        filter_base = self.wgt_map_search.wgt_filter.combo_base.currentText().strip()
        if filter_base!='':
            title = filter_base+' '+title
        if filter_style!='' or filter_type!='':
            if filter_style=='':
                full_type = filter_type
            else:
                full_type = filter_style+filter_type[:1]
            if filter_level!='':
                full_type += filter_level
            title = full_type+' '+title
        elif filter_level!='':
            title = filter_level+'级 '+title
        else :
            title = '全难度 '+title
        if filter_version!='':
            title = filter_version+'版本 '+title
        cnt_clear = [0]*len(clear_name)
        for map in self.wgt_map_search.list_maps:
            cnt_clear[map.clear] +=1
        draw_num = []
        draw_label = []
        for i in range(len(cnt_clear)):
            if cnt_clear[i]!=0:
                draw_num.append(cnt_clear[i])
                draw_label.append(f'{clear_name[i]}:{cnt_clear[i]}')
        plt.pie(draw_num, labels=draw_label, autopct='%.2f%%')
        plt.title(title)
        plt.show()

class PageSettings(QWidget):
    def __init__(self, parent = None):
        super().__init__(parent)

def start_app():
    plt.rcParams['font.sans-serif']=['SimHei']
    plt.rcParams['axes.unicode_minus'] = False

    app = QApplication(sys.argv)
    
    win_home = QMainWindow()
    win_home.setWindowTitle('BeatMania IIDX点灯助手 by hjhk')

    page_map_manage = PageMapManage(win_home)
    win_home.setCentralWidget(page_map_manage)
    win_home.show()

    app.exec()

if __name__ == '__main__':
    open_database()
    read_song_map()
    start_app()