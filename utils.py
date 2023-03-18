from termcolor import colored
from colorama import init
import string
import re
import audio_metadata
import os
import ffmpeg
import random
import requests
import json
init()


def clean_filename(filename):
    dissallowed_chars = string.punctuation.replace("-", "").replace("_", "") + " "
    for char in dissallowed_chars:
        filename = filename.replace(char, "_")
    return filename


def random_string(charset: str="abcdefABCDEF0123456789", length: int=8):
    return ''.join(random.choice(charset) for i in range(length))

def get_required_metadata_from_file(file_path):
    # returns a dict of metadata
    # must contain:
    # {
    #   "title": "title",
    #   "artist": "artist",
    #   "album": ??? // CAN BE NONE, THIS IS HANDLED BY DATABASE LINKER
    # }



    if not os.path.exists(file_path):
        assert False, "File does not exist"

    metadata = audio_metadata.load(file_path)
    if metadata is None:
        assert False, "File is not a valid audio file"

    # get the title
    if not metadata.tags.title:
        assert False, "File does not have a title. Please tag this file"

    # get the artist
    if not metadata.tags.artist:
        assert False, "File does not have an artist. Please tag this file"

    # get the album
    if not metadata.tags.album:
        album = None
    else:
        album = metadata.tags.album

    return {
        "title": metadata.tags.title,
        "artist": metadata.tags.artist,
        "album": album,
    }

def is_valid_url(url):
    # https://stackoverflow.com/questions/7160737/python-how-to-validate-a-url-in-python-malformed-or-not
    regex = re.compile(
        r'^(?:http|ftp)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
        r'localhost|' #localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    return re.match(regex, url) is not None

def convert_any_to_compatible_audio_format(file_path, output_path):
    # use ffmpeg to convert the file to a compatible audio format.
    # if the file is already compatible, it will just copy the file
    compatible_web_types = ["mp3", "ogg", "wav", "flac", "aac", "m4a", "wma", "webm", "opus"] # formats that are supported by the web
    file_extension = file_path.split(".")[-1]
    if file_extension not in compatible_web_types:
        # convert to mp3 Highest quality
        stream = ffmpeg.input(file_path)
        # abr
        stream = ffmpeg.output(stream, output_path, abr="320k")
        ffmpeg.run(stream)
    else:
        # copy the file
        os.system(f"cp {file_path} {output_path}")



class Logger:

    @staticmethod
    def format(input):
        """
        # Replace stuff like -> with unicode counterpart (long arrow): ⟶
        # replace color codes with ansi escape sequences 
        """
        ligatures = [
            ("==", "≡"),
            ("!=", "≠"),
            ("~=", "≈"),
            ("+=", "⊕"),
        ]

        # find any ligatures that havent been escaped with a \\
        for ligature in ligatures:
            input = re.sub(r"(?<!\\)"+ligature[0], ligature[1], input)

        colors = {
            "red": "31",
            "green": "32",
            "yellow": "33",
            "blue": "34",
            "magenta": "35",
            "cyan": "36",
            "white": "37",
            "grey": "90",
            "black": "30",

            "red_bg": "41",
            "green_bg": "42",
            "yellow_bg": "43",
            "blue_bg": "44",
            "magenta_bg": "45",
            "cyan_bg": "46",
            "white_bg": "47",   
            "grey_bg": "100",
            "black_bg": "40",

            "bold": "1",
            "underline": "4",
            "reverse": "7",
            "reset": "0",
        }

        # find any color codes that havent been escaped with a \\
        for color in colors:
            input = re.sub(r"(?<!\\)\["+color+"\]", "\033["+colors[color]+"m", input)

        # remove any escape sequences that havent been escaped with a \\
        input = re.sub(r"(?<!\\)\\\[", "[", input)
        input = re.sub(r"(?<!\\)\\\]", "]", input)

        return input
    

    @staticmethod
    def log(prefix, *args):
        # color[prefix]reset args by space
        # log is blue

        # ERROR // TUPLE OBJECT DOES NOT SUPPORT ITEM ASSIGNMENT
        # for i, arg in enumerate(args):
        #     if isinstance(arg, str):
        #         args[i] = Logger.format(arg)

        # FIX:
        args = [Logger.format(arg) if isinstance(arg, str) else arg for arg in args]

        # always add reset to the end of the string
        print("INFO  |\t" + colored(f"[{prefix}]", 'blue'), *args)

    @staticmethod
    def error(prefix, *args):
        # color[prefix]reset args by space
        # error is red

        # ERROR // TUPLE OBJECT DOES NOT SUPPORT ITEM ASSIGNMENT
        # for i, arg in enumerate(args):
        #     if isinstance(arg, str):
        #         args[i] = Logger.format(arg)

        # FIX:
        args = [Logger.format(arg) if isinstance(arg, str) else arg for arg in args]

        print("ERROR |\t" + colored(f"[{prefix}]", 'red'), *args)

    @staticmethod
    def success(prefix, *args):
        # color[prefix]reset args by space
        # success is green

        # ERROR // TUPLE OBJECT DOES NOT SUPPORT ITEM ASSIGNMENT
        # for i, arg in enumerate(args):
        #     if isinstance(arg, str):
        #         args[i] = Logger.format(arg)

        # FIX:
        args = [Logger.format(arg) if isinstance(arg, str) else arg for arg in args]

        print("SUCCESS |\t" + colored(f"[{prefix}]", 'green'), *args)

    @staticmethod
    def warning(prefix, *args):
        # color[prefix]reset args by space
        # warning is yellow

        # ERROR // TUPLE OBJECT DOES NOT SUPPORT ITEM ASSIGNMENT
        # for i, arg in enumerate(args):
        #     if isinstance(arg, str):
        #         args[i] = Logger.format(arg)

        # FIX:
        args = [Logger.format(arg) if isinstance(arg, str) else arg for arg in args]

        print("WARN  |\t" + colored(f"[{prefix}]", 'yellow'), *args)

    @staticmethod
    def debug(prefix, *args):
        # color[prefix]reset args by space
        # debug is magenta

        # ERROR // TUPLE OBJECT DOES NOT SUPPORT ITEM ASSIGNMENT
        # for i, arg in enumerate(args):
        #     if isinstance(arg, str):
        #         args[i] = Logger.format(arg)

        # FIX:
        args = [Logger.format(arg) if isinstance(arg, str) else arg for arg in args]

        print("DEBUG |\t" + colored(f"[{prefix}]", 'magenta'), *args)
