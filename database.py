from io import BytesIO
import sqlite3
import os
import sys
from datetime import datetime
import json
import time
from utils import *
import time
from PIL import Image

# MUST READ # 
# This database is NOT secure
# There is no reason for any security because the application runs locally.


# USER DESIGN
# The intention of the application works similar to Winamp
# The user simply adds all of their music to the database
# by selecting a parent folder, which is recursively searched for music files

# the music is indexed by a standardized format and 
# the database manager will automatically download cover art and other missing stuff
# from a free music api

# Database objects

class Track:
    def __init__(self, cursor, id) -> None:
        self.id = id
        self.metadata = {}
        self.path = ""
        self.cursor = cursor
        self.get_data()

    def get_data(self):
        self.cursor.execute("SELECT * FROM tracks WHERE id = ?", (self.id,))
        data = self.cursor.fetchone()
        if data is None:
            assert False, "Track does not exist"
        self.metadata = json.loads(data[1])
        self.path = data[3]

    def save(self):
        self.cursor.execute("UPDATE tracks SET metadata = ?, path = ? WHERE id = ?", (json.dumps(self.metadata), self.path, self.id))

class Album:
    def __init__(self, cursor, id) -> None:
        self.id = id
        self.metadata = {}
        self.cover = ""
        self.tracks = []
        self.cursor = cursor

        # get data
        self.get_data()

    def get_data(self):
        # select the album id
        self.cursor.execute("SELECT * FROM albums WHERE id = ?", (self.id,))
        data = self.cursor.fetchone()
        if data is None:
            assert False, "Album does not exist"
        self.metadata = json.loads(data[1])
        self.cover = data[2]
        self.cursor.execute("SELECT * FROM tracks WHERE album_id = ?", (self.id,))
        data = self.cursor.fetchall()
        for track in data:
            track = Track(self.cursor, track[0])
            self.tracks.append(track)

    def save(self):
        self.cursor.execute("UPDATE albums SET metadata = ?, cover = ? WHERE id = ?", (json.dumps(self.metadata), self.cover, self.id))
        for track in self.tracks:
            track.save()

class Playlist:
    def __init__(self, cursor, id) -> None:
        self.id = id
        self.metadata = {}
        self.tracks = []
        self.cursor = cursor

    def get_data(self):
        self.cursor.execute("SELECT * FROM playlists WHERE id = ?", (self.id,))
        data = self.cursor.fetchone()
        if data is None:
            assert False, "Playlist does not exist"
        self.metadata = json.loads(data[1])
        self.tracks = json.loads(data[2])

    def save(self):
        self.cursor.execute("UPDATE playlists SET metadata = ?, tracks = ? WHERE id = ?", (json.dumps(self.metadata), json.dumps(self.tracks), self.id))


def get_utc_datestamp():
    date = datetime.utcnow()
    # return the integer representation of the date
    return int(time.mktime(date.timetuple()))

class Database:
    def __init__(self) -> None:

    
        if not os.path.exists("./config.json"):
            with open("./config.json", "w") as f:
                f.write(json.dumps({
                }))
            Logger.warning("database", "config.json not found. Creating default config.json")

        self.config_data = json.loads(open("./config.json", "r").read())
        if "data_folder" not in self.config_data:
            if not os.path.exists("./data"):
                Logger.warning("database", "data_folder key not found in config.json. The datafolder will be created locally (./)")
                try:
                    os.mkdir("./data")
                    os.mkdir("./data/covers")
                    os.mkdir("./data/downloads")
                    self.data_folder = os.path.abspath("./data")
                    # set config data
                    self.config_data["data_folder"] = self.data_folder
                    with open("./config.json", "w") as f:
                        f.write(json.dumps(self.config_data))
                except:
                    assert False, "Could not create data folder. Make sure ./data doesnt exist already!"
            else:
                Logger.success("database", "Found data folder!")
                self.data_folder = os.path.abspath("./data")
        else:
            self.data_folder = self.config_data["data_folder"]


        if not os.path.exists(self.data_folder):
            assert False, "Data folder does not exist"
        elif not os.path.isdir(self.data_folder):
            assert False, "Data folder is not a directory"
        self.conn = sqlite3.connect("./data/database.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
    
        # id is reference in database
        # metadata is json string that contains bulk of info
        # cover is path to cover image

        # MAKE SURE!!!
        # That paths are relative to the data folder. Otherwise refactoring would be a pain.
        self.cursor.execute("CREATE TABLE IF NOT EXISTS albums (id INTEGER PRIMARY KEY, metadata TEXT, cover TEXT)") # Cover is relative to data folder
        self.cursor.execute("CREATE TABLE IF NOT EXISTS tracks (id INTEGER PRIMARY KEY, metadata TEXT, album_id INTEGER, path TEXT)") # Path is relative to data folder, IMPORTANT: some tracks can be imported, but not downloaded. To check for this, metadata will have a bool key called "imported" to check if it is downloaded or not. If its imported, the path will be absolute. 
        self.cursor.execute("CREATE TABLE IF NOT EXISTS playlists (id INTEGER PRIMARY KEY, metadata TEXT, tracks TEXT)") # Tracks is a json string of a list of track ids
        # ensure id 0 is the Unknown Album
        self.cursor.execute("SELECT * FROM albums WHERE id = 0")
        if self.cursor.fetchone() is None:
            Logger.debug("database/albums", "created fallback album")
            metadata = {
                "title": "Unknown Album",
                "artist": "Unknown Artist",
                "year": 0,
                "genre": "Unknown Genre",
                "rating": 0,
                "date_added": get_utc_datestamp(),
            }
            self.cursor.execute("INSERT INTO albums VALUES (0, ?, ?)", (json.dumps(metadata), ""))
        self.conn.commit()



    #  ACCESSORS
    def get_album(self, id) -> Album:
        self.cursor.execute("SELECT * FROM albums WHERE id = ?", (id,))
        data = self.cursor.fetchone()
        if data is None:
            return None
        album = Album(self.cursor, id)
        album.metadata = json.loads(data[1])
        album.cover = data[2]
        self.cursor.execute("SELECT * FROM tracks WHERE album_id = ?", (id,))
        data = self.cursor.fetchall()
        for track in data:
            track = Track(self.cursor, track[0])
            album.tracks.append(track)
        return album

    def get_track(self, id) -> Track:
        self.cursor.execute("SELECT * FROM tracks WHERE id = ?", (id,))
        data = self.cursor.fetchone()
        if data is None:
            return None
        track = Track(id)
        track.metadata = json.loads(data[1])
        track.path = data[3]
        return track
    

    def get_playlist(self, id) -> Playlist:
        self.cursor.execute("SELECT * FROM playlists WHERE id = ?", (id,))
        data = self.cursor.fetchone()
        if data is None:
            return None
        playlist = Playlist(id)
    
    def add_track_from_file(self, path_to_file, metadata = None, album_id = None) -> Track:
        path_to_file = os.path.abspath(path_to_file) # imports MUST contain absolute paths
        if album_id == None:
            # set album id to 0, 0 is the default album
            album_id = 0
        
        if metadata == None:
            try:
                metadata = get_required_metadata_from_file(path_to_file)
            except Exception as e:
                # immediate access to metadata failed, set metadata to a dict containing the filename as the title, and unknown as the artist
                metadata = {
                    "title": os.path.basename(path_to_file),
                    "artist": "Unknown",
                    "album": self.get_album(0).metadata["title"],
                    "imported": True,
                    "requires_metadata": True,
                }
        else:
            metadata["imported"] = True
            metadata["requires_metadata"] = False
            


        self.cursor.execute("INSERT INTO tracks VALUES (NULL, ?, ?, ?)", (str(json.dumps(metadata)), album_id, str(path_to_file)))
        self.conn.commit()
        return Track(self.cursor, self.cursor.lastrowid)

    def add_track_relative_to_data_folder(self, path_to_file, metadata, album_id = None) -> Track:
        if album_id == None:
            # set album id to 0, 0 is the default album
            album_id = 0
        
        metadata["imported"] = False
        metadata["requires_metadata"] = False

        self.cursor.execute("INSERT INTO tracks VALUES (NULL, ?, ?, ?)", (str(json.dumps(metadata)), album_id, str(path_to_file)))
        self.conn.commit()
        return Track(self.cursor, self.cursor.lastrowid)
    

    def add_album(self, metadata, cover = None) -> Album:
        # to prevent duplicate albums, check if the album already exists. Check by name and artist
        # select every album where the title is the same as the title in metadata, and the artist is the same as the artist in metadata
        # must match exactly
        """
            ### add_album
            Add an album to the database.\n
            If the album already exists, return the existing album.\n
            If the album does not exist, create a new album and return it.\n
        """
        self.cursor.execute("SELECT * FROM albums WHERE metadata LIKE ?", (f"%{metadata['title']}%",))
        data = self.cursor.fetchall()
        for album in data:
            album_data = json.loads(album[1])
            if album_data["artist"] == metadata["artist"]:
                # album already exists
                return Album(self.cursor, album[0])
        if cover == None:
            cover = ""
        self.cursor.execute("INSERT INTO albums VALUES (NULL, ?, ?)", (json.dumps(metadata), cover)) # it is null because the id is autoincremented so we don't need to specify it
        self.conn.commit()
        return Album(self.cursor, self.cursor.lastrowid)


    def freeze_album_cover(self, album_id) -> bool:
        """
            ### freeze_album_cover
            "Freeze" the album cover of an album.\n
            Albums downloaded from bandcamp or youtube have a URL in the metadata, but this URL is not guaranteed to be valid forever.
        """
        # the album should have a URL in the metadata, so download the image and save it to the data folder
        album = self.get_album(album_id)
        if album == None:
            return False
        
        # check if album.cover is a VALID URL
        if not is_valid_url(album.cover):
            return False
        
        # download the image
        try:
            response = requests.get(album.cover)
        except Exception as e:
            return False
        
        # save the image to the data folder
        random_name = random_string(
            "01234567abcdef",
            8
        )

        # get raw data, feed to PIL, save to data folder
        image = Image.open(BytesIO(response.content))
        
        # save to data folder
        path = os.path.join("data", "covers", f"{random_name}.png")
        image.save(path)

        # update the database
        album.cover = path
        album.save()
        # commit changes
        self.conn.commit()
        return True
    

    def remove_duplicate_tracks(self) -> int:
        """
            ### remove_duplicate_tracks
            Removes duplicate tracks from the database

            Returns:
                int: The number of tracks removed
        """
        all_tracks = self.cursor.execute("SELECT * FROM tracks").fetchall()
        tracks_removed = 0
        for track in all_tracks:
            path = track[3]
            # every song has a unique path, so we can use that to check for duplicates
            self.cursor.execute("SELECT * FROM tracks WHERE path = ?", (path,))
            data = self.cursor.fetchall()
            if len(data) > 1:
                # there are duplicates, remove all but the first
                for i in range(1, len(data)):
                    self.cursor.execute("DELETE FROM tracks WHERE id = ?", (data[i][0],))
                    self.conn.commit()
                    tracks_removed += 1
        return tracks_removed
    
    def remove_duplicate_albums(self) -> int:
        """
            ### remove_duplicate_albums
            Removes duplicate albums from the database

            Returns:
                int: The number of albums removed
        """

        # first, index all duplicate albums
        duplicate_albums = []
        all_albums = self.cursor.execute("SELECT * FROM albums").fetchall()
        for album in all_albums:
            metadata = json.loads(album[1])
            self.cursor.execute("SELECT * FROM albums WHERE metadata LIKE ?", (f"%{metadata['title']}%",))
            data = self.cursor.fetchall()
            if len(data) > 1:
                # there are duplicates, add them to the list
                for i in range(1, len(data)):
                    duplicate_albums.append(data[i][0])
        Logger.debug("system/database", f"Found {len(duplicate_albums)} duplicate albums")