import sys, yaml, traceback
import matplotlib.pyplot as plt
from selenium import webdriver
from typing import *
from fuzzywuzzy import fuzz

from utils import *
from database import *
from data import *
from widget import *

def fetch_remote_map_info():
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
    dict_song_info: Dict[str, List] = dict(chrome.execute_script('return titletbl'))
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
            song_info['genre'] = escape_chars_for_sql(handle_html(info[3]))
            song_info['artist'] = escape_chars_for_sql(handle_html(info[4]))
            song_info['title'] = escape_chars_for_sql(handle_html(info[5]))
            sub = ''
            if len(info) > 6:
                sub += handle_html(info[6])
            if len(note_bpm) > 23:
                sub += handle_html(map_level[23])
            song_info['sub'] = escape_chars_for_sql(sub)
            song_info['bpm'] = note_bpm[11]
            sql = sql_select_song.format(**song_info)
            db_cursor.execute(sql)
            if len(db_cursor.fetchall()) == 0:
                sql = sql_insert_song.format(**song_info)
            else:
                sql = sql_update_song.format(**song_info)
            db_cursor.execute(sql)
            # map
            for i in range(len(type_idx)):
                level = map_level[type_idx[i]]
                if level == 0:
                    continue
                map_info = dict()
                map_info['id'] = id
                map_info['type'] = type_name[i]
                map_info['level'] = level
                map_info['note'] = note_bpm[i + 1]
                map_info['base'] = ''
                map_info['clear'] = 0
                map_info['hidden'] = 0
                sql = sql_select_map.format(**map_info)
                db_cursor.execute(sql)
                if len(db_cursor.fetchall()) == 0:
                    sql = sql_insert_map.format(**map_info)
                else:
                    sql = sql_update_map_info.format(**map_info)
                db_cursor.execute(sql)
            db_conn.commit()
        except sqlite3.OperationalError:
            print(f'error executing sql: {sql}', file=sys.stderr)
            traceback.print_exc()
        except Exception as e:
            traceback.print_exc()
    chrome.quit()
    read_song_map()

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
        full_type = full_type_name.get(type_name[2:])
        if full_type is None:
            continue
        clear = row[5]
        if clear >= len(clear_name):
            continue
        map_info = dict()
        map_info['style'] = type_name[:2]
        map_info['type'] = full_type
        map_info['level'] = row[2]
        map_info['notes'] = row[3]
        map_info['base'] = '未定级' if row[4]=='' else row[4]
        map_info['clear'] = clear
        map_info['hidden'] = row[6]
        map = song.maps.get(type_name)
        if map is None:
            song.add_map(**map_info)
        else:
            map.update(**map_info)

def new_clear_status_combo(parent) -> QComboBox:
    combo = ColoredComboBox(parent)
    for i in range(len(clear_name)):
        combo.addColoredItem(clear_name[i], clear_font_color[i])
    return combo

# class WidgetSongInfo(QWidget):

class WidgetMapInfo(QWidget):
    def __init__(self, info: MapInfo):
        super().__init__()
        self.info = info

        layout_main = QHBoxLayout()
        self.setLayout(layout_main)

        self.combo_clear = new_clear_status_combo(self)
        self.combo_clear.adjustSize()
        self.combo_clear.setMaximumWidth(self.combo_clear.width())
        layout_main.addWidget(self.combo_clear)

        layout_title = QVBoxLayout()
        self.label_title = new_label(font_size=12, fixed=False)
        self.label_title.setStyleSheet('font-weight: bold')
        layout_title.addWidget(self.label_title)
        self.label_sub_title = new_label(fixed=False, font_size=7)
        layout_title.addWidget(self.label_sub_title)
        self.label_artist = new_label(fixed=False)
        self.label_artist.setStyleSheet('font-weight: bold')
        layout_title.addWidget(self.label_artist)
        self.label_genre = new_label(fixed=False, font_size=7)
        layout_title.addWidget(self.label_genre)
        self.label_other_info = new_label(fixed=False, font_size=8)
        layout_title.addWidget(self.label_other_info)
        layout_main.addLayout(layout_title)

        wgt_level_btn = QWidget()
        layout_level_btn = QHBoxLayout()
        wgt_level_btn.setLayout(layout_level_btn)

        layout_level = QVBoxLayout()
        layout_level.setAlignment(Qt.AlignCenter)
        self.label_level = new_label(fixed=False, font_size=12)
        layout_level.addWidget(self.label_level)
        self.combo_base = MaskWheelComboBox()
        self.combo_base.setEditable(True)
        self.combo_base.completer().setCompletionMode(0)
        self.combo_base.completer().setFilterMode(Qt.MatchContains)
        layout_level.addWidget(self.combo_base)
        self.label_hidden = new_label(fixed=False, font_size=8)
        self.label_hidden.setStyleSheet('color: red')
        layout_level.addWidget(self.label_hidden)
        layout_level_btn.addLayout(layout_level)

        self.btn_select = QPushButton('placehold')
        self.btn_select.adjustSize()
        self.btn_select.setFixedWidth(self.btn_select.width())
        layout_level_btn.addWidget(self.btn_select)
        wgt_level_btn.adjustSize()
        layout_main.addWidget(wgt_level_btn)

        if info is not None:
            self.update()
    def set_clear_changed_action(self, action: Callable[['WidgetMapInfo'], None]):
        if action is None:
            return
        self.combo_clear.currentIndexChanged.connect(lambda: action(self))
    def set_base_changed_action(self, action: Callable[['WidgetMapInfo'], None]):
        if action is None:
            return
        self.combo_base.currentTextChanged.connect(lambda: action(self))
    def set_selected_action(self, action: Callable[['WidgetMapInfo'], None]):
        if action is None:
            return
        self.btn_select.clicked.connect(lambda: action(self))
    def update(self):
        self.combo_clear.setCurrentIndex(self.info.clear)
        self.label_title.setText(self.info.song.title)
        self.label_sub_title.setText(self.info.song.sub_title)
        self.label_artist.setText(self.info.song.artist)
        self.label_genre.setText(self.info.song.genre)
        self.label_other_info.setText(f'{self.info.song.bpm} BPM    {self.info.notes} NOTES    {self.info.song.version}')
        self.label_level.setText(f'{self.info.get_full_type()} {self.info.level}')
        self.combo_base.setCurrentText(self.info.base)
        self.label_hidden.setText('已隐藏' if self.info.hidden!=0 else '')

class WidgetSongFilter(QGroupBox):
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
        layout_line3.setStretch(0, 2)
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
        layout, self.combo_type = new_layout_labeled_combo('难度：')
        layout_line1.addLayout(layout)
        layout, self.combo_level = new_layout_labeled_combo('等级：')
        layout_line1.addLayout(layout)
        layout, self.combo_base = new_layout_labeled_combo('定数：')
        layout_line1.addLayout(layout)
        layout, self.combo_clear = new_layout_labeled_combo('通关状态：', ColoredComboBox(), editable=False)
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

class WidgetMapSearch(QWidget):
    def __init__(self, init_map_widget: Callable[[WidgetMapInfo], None] = None, on_map_clicked: Callable[[WidgetMapInfo], None] = None, parent = None):
        super().__init__(parent)

        self.list_maps: List[MapInfo] = []
        self.init_map_widget = init_map_widget
        self.on_map_select = on_map_clicked

        layout_main = QVBoxLayout()
        self.setLayout(layout_main)

        self.wgt_filter = WidgetMapFilter(self)
        layout_main.addWidget(self.wgt_filter)

        layout_line2 = QHBoxLayout()

        self.check_show_hidden = QCheckBox('显示隐藏谱面')
        self.check_show_hidden.adjustSize()
        self.check_show_hidden.setFixedWidth(self.check_show_hidden.width())
        self.check_show_hidden.stateChanged.connect(self.do_search)
        layout_line2.addWidget(self.check_show_hidden)
        
        self.btn_clear_text = QPushButton('重置')
        self.btn_clear_text.adjustSize()
        self.btn_clear_text.setFixedWidth(self.btn_clear_text.width())
        self.btn_clear_text.clicked.connect(self.reset)
        layout_line2.addWidget(self.btn_clear_text)

        self.btn_search = QPushButton('检索')
        self.btn_search.adjustSize()
        self.btn_search.setFixedWidth(self.btn_search.width())
        self.btn_search.clicked.connect(self.do_search)
        layout_line2.addWidget(self.btn_search)

        self.btn_sort_clear = QPushButton('检索并按通关状态排序')
        self.btn_sort_clear.adjustSize()
        self.btn_sort_clear.setFixedWidth(self.btn_sort_clear.width())
        self.btn_sort_clear.clicked.connect(self.sort_by_clear)
        layout_line2.addWidget(self.btn_sort_clear)
        layout_main.addLayout(layout_line2)
        
        scroll_area = QScrollArea(self)
        scroll_area.setMinimumHeight(WidgetMapInfo(None).height())
        scroll_area.setWidgetResizable(True)
        self.wgt_map_list = QListWidget(scroll_area)
        scroll_area.setWidget(self.wgt_map_list)
        layout_main.addWidget(scroll_area)

    def on_clear_change(self, widget: WidgetMapInfo):
        global db_conn, db_cursor
        widget.info.clear = widget.combo_clear.currentIndex()
        widget.info.save(db_conn, db_cursor)
        self.fetch_combo_options()
    def on_base_change(self, widget: WidgetMapInfo):
        global db_conn, db_cursor
        if widget.combo_base.currentText()!='':
            widget.info.base = widget.combo_base.currentText()
            widget.info.save(db_conn, db_cursor)
        self.fetch_combo_options()
    def reset(self):
        self.fetch_combo_options()
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
                opt_level.add(map.level)
                opt_base.add(map.base)
                opt_clear.add(map.clear)
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
        self.wgt_filter.combo_type.addItems(set_to_sorted_list(opt_type, lambda x: list(full_type_name.values()).index(x)))
        self.sorted_base = set_to_sorted_list(opt_base)
        self.wgt_filter.combo_base.addItems(self.sorted_base)
        self.wgt_filter.combo_style.addItems(set_to_sorted_list(opt_style, lambda x: 0 if x=='SP' else 1))
        self.wgt_filter.combo_level.addItems([str(x) for x in set_to_sorted_list(opt_level)])
        self.wgt_filter.combo_clear.addColoredItem('')
        for i in set_to_sorted_list(opt_clear):
            self.wgt_filter.combo_clear.addColoredItem(clear_name[i], clear_font_color[i])
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
        filter_show_hidden = self.check_show_hidden.checkState()
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
                if filter_show_hidden==0 and map.hidden!=0 or \
                        filter_style!='' and map.style!=filter_style or \
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
        cur_len = self.wgt_map_list.count()
        if cur_len > 0:
            self.wgt_map_list.takeItem(cur_len-1)
        if len(self.list_maps) == 0:
            add_widget_to_list(new_label('未找到谱面，请调整过滤条件或从textage.cc导入谱面数据', font_size=15), self.wgt_map_list)
            return
        endIdx = min(beginIdx+count, len(self.list_maps))
        for i in range(beginIdx, endIdx):
            widget_map_info = WidgetMapInfo(self.list_maps[i])
            widget_map_info.combo_base.addItems(self.sorted_base)
            if self.init_map_widget is not None:
                self.init_map_widget(widget_map_info)
            widget_map_info.update()
            widget_map_info.set_clear_changed_action(self.on_clear_change)
            widget_map_info.set_selected_action(self.on_map_select)
            widget_map_info.set_base_changed_action(self.on_base_change)
            add_widget_to_list(widget_map_info, self.wgt_map_list)
        next_load = min(count, len(self.list_maps)-endIdx)
        if next_load > 0:
            widget = QWidget()
            layout = QHBoxLayout()
            widget.setLayout(layout)
            btn_load = QPushButton(f'加载后{next_load}张谱面')
            btn_load.setMaximumWidth(300)
            btn_load.clicked.connect(lambda: self.load_songs(endIdx, next_load))
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

class PageMapManage(QWidget):
    def __init__(self, parent = None):
        super().__init__(parent)

        layout_main = QVBoxLayout()
        self.setLayout(layout_main)

        self.wgt_map_search = WidgetMapSearch(init_map_widget=self.init_widget_map_info, on_map_clicked=self.on_widget_map_clicked)
        layout_main.addWidget(self.wgt_map_search)

        layout_tools = QHBoxLayout()
        self.btn_update_songs = QPushButton('从textage.cc获取谱面数据（需要一定时间）')
        self.btn_update_songs.adjustSize()
        self.btn_update_songs.setFixedWidth(self.btn_update_songs.width())
        self.btn_update_songs.clicked.connect(self.on_click_update_songs)
        layout_tools.addWidget(self.btn_update_songs)
        self.btn_gen_pie_pic = QPushButton('生成当前过滤条件（除模糊搜索、通关状态）的完成度图')
        self.btn_gen_pie_pic.adjustSize()
        self.btn_gen_pie_pic.setFixedWidth(self.btn_gen_pie_pic.width())
        self.btn_gen_pie_pic.clicked.connect(self.on_click_gen_pie_pic)
        layout_tools.addWidget(self.btn_gen_pie_pic)
        layout_main.addLayout(layout_tools)
    def init_widget_map_info(self, widget: WidgetMapInfo):
        widget.btn_select.setText('显示' if widget.info.hidden!=0 else '隐藏')
    def on_widget_map_clicked(self, widget: WidgetMapInfo):
        global db_conn, db_cursor
        widget.info.hidden = 1 if widget.info.hidden==0 else 0
        widget.info.save(db_conn, db_cursor)
        widget.update()
        widget.btn_select.setText('显示' if widget.info.hidden!=0 else '隐藏')
    def on_click_update_songs(self):
        fetch_remote_map_info()
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
        draw_color = []
        for i in range(len(cnt_clear)):
            if cnt_clear[i]!=0:
                draw_num.append(cnt_clear[i])
                draw_label.append(f'{clear_name[i]}:{cnt_clear[i]}')
                draw_color.append(clear_font_color_plt[i])
        plt.pie(draw_num, labels=draw_label, autopct='%.2f%%', colors=draw_color)
        plt.legend(bbox_to_anchor=(1.35, 1.05), loc='upper right')
        plt.title(title)
        plt.show(block=False)

class DialogSelectMap(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.selected_map: MapInfo | None = None

        layout_main = QVBoxLayout()
        self.setLayout(layout_main)

        layout_hint = QHBoxLayout()
        self.label_hint = new_label(fixed=False)
        layout_hint.addWidget(self.label_hint)
        self.btn_pass = QPushButton('跳过')
        self.btn_pass.adjustSize()
        self.btn_pass.setFixedWidth(self.btn_pass.width())
        self.btn_pass.clicked.connect(lambda: self.accept())
        layout_hint.addWidget(self.btn_pass)
        layout_main.addLayout(layout_hint)

        self.wgt_map_search = WidgetMapSearch(parent=self, on_map_clicked=self.on_widget_map_clicked, init_map_widget=self.init_widget_map)
        layout_main.addWidget(self.wgt_map_search)
    def init_widget_map(self, widget: WidgetMapInfo):
        widget.combo_base.setDisabled(True)
        widget.combo_clear.setDisabled(True)
        widget.btn_select.setText('确定')
    def on_widget_map_clicked(self, widget: WidgetMapInfo):
        self.selected_map = widget.info
        self.accept()

class PageBatchImportBase(QWidget):
    def __init__(self, parent = None):
        super().__init__(parent)

        layout_main = QVBoxLayout()
        self.setLayout(layout_main)

        layout_level = QHBoxLayout()
        layout, self.combo_style = new_layout_labeled_combo('游玩风格：')
        layout_level.addLayout(layout)
        layout, self.combo_level = new_layout_labeled_combo('等级：')
        layout_level.addLayout(layout)
        layout, self.combo_base = new_layout_labeled_combo('定数：')
        layout_level.addLayout(layout)

        self.button = QPushButton("导入")
        self.button.adjustSize()
        self.button.setFixedWidth(self.button.width())
        self.button.clicked.connect(self.on_button_clicked)
        layout_level.addWidget(self.button)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("要导入的曲名，一行一首")

        layout_main.addLayout(layout_level)
        layout_main.addWidget(self.text_edit)
    def init_combo_list(self):
        opt_style = set()
        opt_level = set()
        opt_base = set()
        for song in dict_songs.values():
            for map in song.maps.values():
                opt_style.add(map.style)
                opt_level.add(map.level)
                opt_base.add(map.base)
        filter_style = self.combo_style.currentText()
        filter_level = self.combo_level.currentText()
        target_base = self.combo_base.currentText()
        self.combo_style.clear()
        self.combo_base.clear()
        self.combo_level.clear()
        self.combo_style.addItems(set_to_sorted_list(opt_style, lambda x: 0 if x=='SP' else 1))
        self.combo_base.addItems(set_to_sorted_list(opt_base))
        self.combo_level.addItems([str(x) for x in set_to_sorted_list(opt_level)])
        self.combo_style.setCurrentText(filter_style)
        self.combo_level.setCurrentText(filter_level)
        self.combo_base.setCurrentText(target_base)
    def on_button_clicked(self):
        global db_conn, db_cursor
        filter_style = self.combo_style.currentText()
        filter_level = self.combo_level.currentText()
        target_base = self.combo_base.currentText()
        text_titles = self.text_edit.toPlainText()
        map_list = []
        for song in dict_songs.values():
            for map in song.maps.values():
                if filter_style!='' and map.style!=filter_style or \
                    filter_level!='' and str(map.level)!=filter_level:
                    continue
                map_list.append(map)

        for line in text_titles.split('\n'):
            title = line.strip()
            if title=='':
                continue
            res = []
            for map in map_list:
                if map.song.title.lower()==title.lower() or (map.song.title+' '+map.song.sub_title).lower()==title.lower():
                    res.append(map)
            target_map = None
            if len(res)==1:
                target_map = res[0]
            else:
                dialog = DialogSelectMap(self)
                dialog.setWindowTitle('手动选择谱面')
                dialog.label_hint.setText(f'【{title}】存在{len(res)}个完全匹配项，请手动选择谱面或跳过该谱面')
                dialog.wgt_map_search.fetch_combo_options()
                dialog.wgt_map_search.wgt_filter.wgt_song_filter.combo_title.setCurrentText(title)
                dialog.wgt_map_search.wgt_filter.combo_style.setCurrentText(filter_style)
                dialog.wgt_map_search.wgt_filter.combo_level.setCurrentText(filter_level)
                dialog.wgt_map_search.do_search()
                dialog.exec()
                target_map = dialog.selected_map
            if target_map is None:
                continue
            target_map.base = target_base
            target_map.save(db_conn, db_cursor)
        self.text_edit.clear()

def start_app():
    app = QApplication(sys.argv)
    
    main_window = DynamicWidgetDisplay()
    main_window.setWindowTitle('Beatmania IIDX点灯小帮手 by hjhk')

    page_map_manage = PageMapManage(main_window)
    btn_map_manage = main_window.add_button_and_widget('谱面管理', page_map_manage)
    btn_map_manage.clicked.connect(lambda: page_map_manage.wgt_map_search.fetch_combo_options())

    page_import_base = PageBatchImportBase(main_window)
    btn_import_base = main_window.add_button_and_widget('批量设置定数', page_import_base)
    btn_import_base.clicked.connect(lambda: page_import_base.init_combo_list())

    page_map_manage.wgt_map_search.reset()
    main_window.show_widget(0)

    main_window.show()
    app.exec()

if __name__ == '__main__':
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = dict(yaml.safe_load(f))
    dict_songs: Dict[str, 'SongInfo'] = dict()
    full_type_name: Dict[str, str] = config.get('type_name')
    clear_name: List[str] = config.get('clear_status')
    clear_font_color_rgb = config.get('clear_font_color')
    clear_font_color: List[QColor] = [QColor(color[0], color[1], color[2]) for color in clear_font_color_rgb]
    clear_font_color_plt = [[num/255 for num in color] for color in clear_font_color_rgb]
    db_conn, db_cursor = open_database(config.get('db_name'))

    plt.rcParams['font.sans-serif']=['SimHei']
    plt.rcParams['axes.unicode_minus'] = False

    read_song_map()
    start_app()