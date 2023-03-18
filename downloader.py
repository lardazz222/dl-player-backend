import yt_dlp
import sys
import os
import time
import json
import sqlite3
import ffmpeg
import audio_metadata
import string
import logging
import requests
from utils import *
from database import *
import re
import pylast

logging.basicConfig(level=logging.WARNING)

LASTFM_API_KEY = "72b00958a0fe59e410e9434b42f2e8f6"  # this is a sample key
LASTFM_API_SECRET = "6742bd50733a5453f3c22b5f8e7d65c0"

# TEST ALBUM BANDCAMP: https://aphextwin.bandcamp.com/album/syro
# TEST TRACK YOUTUBE: https://www.youtube.com/watch?v=bE2RCOp5yoU



class LastFMMetadata:
    @staticmethod
    def get_track_metadata(track_name, artist_name):
        network = pylast.LastFMNetwork(api_key=LASTFM_API_KEY, api_secret=LASTFM_API_SECRET)
        try:
            track = network.get_track(artist_name, track_name)
        except pylast.WSError:
            # try flipping artist and track name
            try:
                track = network.get_track(track_name, artist_name)
            except pylast.WSError:
                # no metadata found
                return None
        title = None
        # try to get title
        if track.get_title() is not None:
            title = track.get_title()
        
        artist = None
        # try to get artist
        if track.get_artist() is not None:
            artist = track.get_artist().get_name()

        album = None
        # try to get album
        if track.get_album() is not None:
            album = track.get_album().get_name()

        cover = None
        # try to get cover
        if track.get_album() is not None:
            cover = track.get_album().get_cover_image()

        duration = None
        # try to get duration
        if track.get_duration() is not None:
            duration = track.get_duration()

        release_date = None
        # try to get release date
        if track.get_wiki_published_date() is not None:
            release_date = track.get_wiki_published_date()

        description = None
        # try to get description
        if track.get_wiki_summary() is not None:
            description = track.get_wiki_summary()



        data = {
            "title": title,
            "artist": artist,
            "album": album,
            "cover": cover,
            "duration": duration,
            "release_date": release_date,
            "description": description,
        }
        return data
class Bandcamp:
    @staticmethod
    def get_album_metadata(url):
        with yt_dlp.YoutubeDL({"dump-json": True, "quiet": True}) as ydl:
            album_info = ydl.extract_info(url, download=False)
        # return relevant info
        # title, artist, album, tracks (urls), cover
        album_name = album_info["entries"][0]["album"]
        artist_name = album_info["entries"][0]["album_artist"]
        # all entry have url "webpage_url"
        tracks = [entry["webpage_url"] for entry in album_info["entries"]]
        cover = album_info["entries"][0]["thumbnail"]
        release_date = album_info["epoch"]
        description = album_info["description"]
        return {
            "title": album_name,
            "artist": artist_name,
            "tracks_count": len(tracks),
            "tracks": tracks,
            "cover": cover,
            "release_date": release_date,
            "description": description,
        }
    
    @staticmethod
    def download_album(url) -> Album:
        download_logs = []
        required_metadata = {

        } # gets merged with file metadata when missing some metadata, the user fills it in manually or a sweep scan does it through lastFM

        db = Database()
        
        data_folder = db.config_data["data_folder"]
        if os.path.exists("./data"):
            if os.path.abspath("./data") == os.path.abspath(data_folder):
                data_folder = "data"

        album_metadata = Bandcamp.get_album_metadata(url)
        # save album cover
        if album_metadata["cover"] is not None:
            album = db.add_album(
                album_metadata,
                cover=album_metadata["cover"],
            )
        else:
            album = db.add_album(album_metadata)
            Logger.warning("bandcamp/download_album", "No cover found for album")
            download_logs.append("Could not find album cover!")
            required_metadata['cover'] = True
        # same for album name, we are creating a folder for the album
        album_name = clean_filename(album_metadata["title"])
        
        
        artist_name = clean_filename(album_metadata["artist"])

        # create folder in data/downloads
        album_folder = os.path.join(data_folder, "downloads", artist_name+"_-_"+album_name)
        # create folder if it does not exist
        if not os.path.exists(album_folder):
            os.makedirs(album_folder)
            download_logs.append(f"created album folder in data/downloads: {album_folder}")
            
        Logger.debug("bandcamp/download_album", f"created album folder in data/tracks: {album_folder}")

        # download tracks
        for track_url in album_metadata["tracks"]:
            # print
            Logger.log("bandcamp/download_album", f"Downloading track {track_url}")
            
            # download high quality audio file found
            with yt_dlp.YoutubeDL({"quiet": True, "format": "bestaudio/best"}) as ydl:
                track_info = ydl.extract_info(track_url, download=False)
            file_name = ydl.prepare_filename(track_info)

            start_time = time.time()
            with yt_dlp.YoutubeDL({
                "quiet": True, 
                "format": "bestaudio/best", 
                'postprocessors': [
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True
                    }
                ]
            }) as ydl: # TODO: use configuration to determine quality
                ydl.download([track_url])
            end_time = time.time()
            download_logs.append(f"Downloaded {file_name} in {end_time-start_time:.2f} seconds")
            # get file name
            try:
                metadata = audio_metadata.load(file_name)
                metadata = {
                    "title": metadata["tags"]["title"][0],
                    "artist": ", ".join(metadata["tags"]["artist"]),
                    "track_number": int(metadata["tags"]["tracknumber"][0]),
                    "album": metadata["tags"]["album"][0],
                    "duration": metadata["streaminfo"]["duration"],
                    "release_date": metadata["tags"]["date"][0],
                    "sample_rate": metadata["streaminfo"]["sample_rate"],
                    "bitrate": metadata["streaminfo"]["bitrate"],
                }
                download_logs.append(f"Retrieved metadata for {file_name}")

            except:
                download_logs.append(f"File {file_name} will have reduced metadata accuracy")

                metadata = {
                    "title": track_info["title"],
                    "artist": track_info["artist"],
                    "album": track_info["album"] if "album" in track_info else None,
                    "duration": track_info["duration"] if "duration" in track_info else None,
                    "release_date": track_info["release_date"] if "release_date" in track_info else None,
                    "sample_rate": track_info["asr"] if "asr" in track_info else None,
                    "bitrate": track_info["abr"] if "abr" in track_info else None,
                    "track_number": track_info["track_number"] if "track_number" in track_info else None,
                }

                for key, value in metadata.items():
                    if value is None:
                        required_metadata[key] = True
                        download_logs.append(f"Missing metadata for {file_name}: {key}")
            
            # get file extension
            file_extension = file_name.split(".")[-1]
            
            # name according to metadata, replace any invalid characters with _. Allow other languages because thats nice
            # just not anything that interferes with the file system
            track_name = clean_filename(metadata["title"])
            

            # create new file name
            new_file_name = f"{metadata['track_number']:02d} - {track_name}.{file_extension}"
            # move file to album folder
            os.rename(file_name, os.path.join(album_folder, new_file_name))
            # add track to database
            track = db.add_track_relative_to_data_folder(
                os.path.join(album_folder, new_file_name),
                metadata,
                album_id=album.id,
            )

            # merge metadata with required metadata
            metadata['required_metadata'] = required_metadata

        # Freeze the cover
        if not db.freeze_album_cover(album.id):
            download_logs.append("Could not freeze album cover!")
            Logger.warning("bandcamp/download_album", "Could not freeze album cover!")
        else:
            download_logs.append("Album cover frozen")
            Logger.debug("bandcamp/download_album", "Album cover frozen")
        return album

class Youtube:
    @staticmethod
    def download_track(url) -> Track:
        db = Database()
        data_folder = db.config_data["data_folder"]
        with yt_dlp.YoutubeDL({"quiet": True, "format": "bestaudio/best"}) as ydl:
            track_info = ydl.extract_info(url, download=False)

        # It is hard to always get the correct metadata, so we will try our best
        # DISTROKID FORMAT:
        # 1|Provided to YouTube by DistroKid
        # 2|
        # 3|{title-tag} (format: track - artist)
        # 4|
        # 5|{artist-tag}
        # 6|
        # 7|{released-on-tag} (format: Released on: {date})
        # 8|
        # 9|Auto-generated by YouTube.
        # try to match distrokid format
        distro_kid_format = "Provided to YouTube by" # there are several record labels, but they all start with this and contain the same format forwards
            
        if "track" not in track_info:
            Logger.warning("youtube/download_track", "Metadata wasnt found, maybe the video isnt uploaded properly? Checking for distrokid format")
            if track_info["description"] is not None and distro_kid_format in track_info["description"]:
                Logger.debug("youtube/download_track", "Found distrokid format, parsing metadata")

                start_index = track_info["description"].find(distro_kid_format) + len(distro_kid_format)
                end_index = track_info["description"].find("Auto-generated by YouTube.")
                track_description = track_info["description"][start_index:end_index]
                track_description = track_description.split("\n")
                track_description = [line for line in track_description if line != ""]
                track_title = track_description[0].split(" · ")[0]
                track_artist = track_description[1]
                track_release_date = track_description[2].split(": ")[1]
                # convert to epoch
                track_release_date = datetime.strptime(track_release_date, "%Y-%m-%d").timestamp()
            else:
                # if we cant find the metadata, we will just use the title and artist from the video
                Logger.warning("youtube/download_track", "Couldnt find distrokid format, using video title and artist")
                if "artist" not in track_info:
                    # if title contains - or : or | then we can assume that the first part is the title and the second part is the artist
                    # sometimes it is the other way around
                    if "-" in track_info["title"] or ":" in track_info["title"] or "|" in track_info["title"]:
                        split_by = ("-", ":", "|")
                        for split in split_by:
                            if split in track_info["title"]:
                                track_title, track_artist = track_info["title"].split(split)
                                track_title = track_title.strip()
                                track_artist = track_artist.strip()

                                # since we are using a last resort method, we will assume that the artist is the SHORTEST string
                                if len(track_title) < len(track_artist):
                                    track_title, track_artist = track_artist, track_title
                                break
                    else:
                        track_title = track_info["title"]
                        track_artist = "Unknown"
                else:
                    track_title = track_info["title"]
                    track_artist = track_info["artist"]
                track_release_date = datetime.now().timestamp()
        else:
            track_title = track_info["track"]
            track_artist = track_info["artist"]
            track_release_date = datetime.now().timestamp()

        track_metadata = {
            "title": track_title,
            "artist": track_artist,
            "track_number": 1,
            "release_date": track_release_date,
            "duration": track_info["duration"],
        }

        # download track
        with yt_dlp.YoutubeDL({"quiet": True, "format": "bestaudio/best"}) as ydl: # TODO: use configuration to determine quality
            ydl.download([url])
        # get file name
        file_name = ydl.prepare_filename(track_info)
        # get file extension
        file_extension = file_name.split(".")[-1]
        # rename the file with a safe name IN PLACE (Dont move to downloads)
        safe_file_name = clean_filename(track_title) + "." + file_extension
        os.rename(file_name, safe_file_name)
        # # name according to metadata, replace any invalid characters with _. Allow other languages because thats nice
        # # just not anything that interferes with the file system
        # track_name = clean_filename(track_metadata["title"])
        # new_file_name = track_name + "." + file_extension
        # # convert to compatible format
        # # convert_any_to_compatible_audio_format(frompath, output_dir)
        print(os.path.abspath(safe_file_name),
            os.path.join(data_folder, "downloads", safe_file_name))
        convert_any_to_compatible_audio_format(
            os.path.abspath(safe_file_name),
            os.path.join(data_folder, "downloads", safe_file_name.replace("." + file_extension, ".mp3"))
        )

        os.remove(safe_file_name)
        
        # add track to database
        Logger.debug("youtube/download_track", f"track metadata:")
        for key, value in track_metadata.items():
            Logger.debug("youtube/download_track", f"{key}: {value}")
        track = db.add_track_relative_to_data_folder(
            os.path.join("downloads", safe_file_name.replace("." + file_extension, ".mp3")),
            track_metadata,
        )
        return track
        

while True:
    url = input("Test Input >> ")
    if url.startswith('test:'):
        test_case = url.split(":")[1]
        match test_case:
            case "rd_tracks":
                db = Database()
                Logger.debug("System/Testing", f"Removed {db.remove_duplicate_tracks()} tracks")
                continue
                
    if "bandcamp.com" in url:
        track = Bandcamp.download_album(url)
        print(track)
    elif "youtube.com" in url:
        track = Youtube.download_track(
            url.split("&")[0]
        )
        print(track)
