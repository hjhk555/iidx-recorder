from typing import Dict
from database import sql_update_full_map

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
    hidden: int
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
        self.hidden = kwargs.get('hidden')
    def get_full_type(self):
        return self.style+self.type[:1]
    def save(self, conn, cusor):
        cusor.execute(sql_update_full_map.format(id=self.song.id, type=self.get_full_type(), level=self.level, note=self.notes, base=self.base, clear=self.clear, hidden=self.hidden))
        conn.commit()
