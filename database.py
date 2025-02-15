import sqlite3

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
                    clear   INTEGER,
                    hidden  INTEGER
                    )'''
sql_create_map_index = '''CREATE INDEX IF NOT EXISTS idx_id_type ON maps(id, type)'''
sql_select_song = '''SELECT id, genre, artist, title, sub, bpm, ver FROM songs WHERE id = \'{id}\''''
sql_select_all_song = '''SELECT id, genre, artist, title, sub, bpm, ver FROM songs'''
sql_insert_song = '''INSERT INTO songs(id, genre, artist, title, sub, bpm, ver) VALUES (\'{id}\', \'{genre}\', \'{artist}\', \'{title}\', \'{sub}\', \'{bpm}\', \'{ver}\')'''
sql_update_song = '''UPDATE songs SET genre=\'{genre}\', artist=\'{artist}\', title=\'{title}\', sub=\'{sub}\', bpm=\'{bpm}\', ver=\'{ver}\' WHERE id=\'{id}\''''
sql_select_map = '''SELECT id, type, level, note, base, clear, hidden FROM maps WHERE id=\'{id}\' AND type=\'{type}\''''
sql_select_all_map = '''SELECT id, type, level, note, base, clear, hidden FROM maps'''
sql_insert_map = '''INSERT INTO maps(id, type, level, note, base, clear, hidden) VALUES (\'{id}\', \'{type}\', {level}, {note}, \'{base}\', {clear}, {hidden})'''
sql_update_map_info = '''UPDATE maps SET level={level}, note={note} WHERE id=\'{id}\' AND type=\'{type}\''''
sql_update_full_map = '''UPDATE maps SET level={level}, note={note}, base=\'{base}\', clear={clear}, hidden={hidden} WHERE id=\'{id}\' AND type=\'{type}\''''

def open_database(db_name: str) -> tuple[sqlite3.Connection, sqlite3.Cursor]:
    db_conn = sqlite3.connect(db_name)
    db_cursor = db_conn.cursor()
    db_cursor.execute(sql_create_song)
    db_cursor.execute(sql_create_map)
    db_cursor.execute(sql_create_map_index)
    db_conn.commit()
    return db_conn, db_cursor