from flask import request, Response
import os
import re
import json
from urllib.parse import unquote
import logging
from config import *
from datetime import datetime

logging.basicConfig(filename=SERVER_LOG, filemode='a', level=logging.INFO)
log = logging.getLogger('werkzeug')
log.disabled = True

video_types = ['mp4', 'flv', 'mov', 'avi', '3gp', 'mpg', 'm4v', 'wmv', 'mkv']
audio_types = ['mp3', "wav", "ogg", "mpeg", "aac", "3gpp", "3gpp2", "aiff", "x-aiff", "amr", "mpga"]


IP_CACHE = {}
try:
    if os.path.exists("ip_cache.json"):
        with open("ip_cache.json") as f:
            IP_CACHE = json.load(f)
except:
    pass

def update_ip_cache():
    global IP_CACHE
    print("UPDATING IP CACHE", IP_CACHE)
    with open("ip_cache.json", "w") as f:
        json.dump(IP_CACHE, f)

def log(kind, ip, message = ""):
    URI = request.environ.get('REQUEST_URI')
    if not URI.startswith("/static/") and get_file_extension(URI) not in tp_dict["image"][0] and request.headers.get('Accept-Ranges') != "bytes" and URI not in ("/logs", "/favicon.ico"):
        location_json = IP_CACHE.get(ip)
        logline = f"[{kind}]," + "{},{},{},{},".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'), ip, location_json["city"], location_json["country_name"]) + unquote(URI) + "," + message
        print(logline)
        #SERVER_LOG.write(logline + "\n")
        logging.info(logline)

def get_chunk(start_byte=None, end_byte=None, full_path=None):
    file_size = os.stat(full_path).st_size
    if end_byte:
        length = end_byte + 1 - start_byte
    else:
        length = file_size - start_byte
    with open(full_path, 'rb') as f:
        f.seek(start_byte)
        chunk = f.read(length)
    return chunk, start_byte, length, file_size

def get_file(file_path, mimetype):
    range_header = request.headers.get('Range', None)
    start_byte, end_byte = 0, None
    if range_header:
        match = re.search(r'(\d+)-(\d*)', range_header)
        groups = match.groups()
        if groups[0]:
            start_byte = int(groups[0])
        if groups[1]:
            end_byte = int(groups[1])
       
    chunk, start, length, file_size = get_chunk(start_byte, end_byte, file_path)
    resp = Response(chunk, 206, mimetype=f'video/{mimetype}',
                      content_type=mimetype, direct_passthrough=True)
    print(length, start_byte, end_byte, file_size)
    resp.headers.add('Content-Range', 'bytes {0}-{1}/{2}'.format(start, start + length - 1, file_size))
    return resp


def get_video_chunk(filename, byte1=None, byte2=None):
    filesize = os.path.getsize(filename)
    yielded = 0
    yield_size = 1024 * 1024

    if byte1 is not None:
        if not byte2:
            byte2 = filesize
        yielded = byte1
        filesize = byte2

    with open(filename, 'rb') as f:
        content = f.read()

    while True:
        remaining = filesize - yielded
        if yielded == filesize:
            break
        if remaining >= yield_size:
            yield content[yielded:yielded+yield_size]
            yielded += yield_size
        else:
            yield content[yielded:yielded+remaining]
            yielded += remaining

def get_video_file(filename, mimetype):
    filesize = os.path.getsize(filename)
    range_header = request.headers.get('Range', None)
    print("RANGE HEADER", range_header)
    if range_header:
        byte1, byte2 = None, None
        match = re.search(r'(\d+)-(\d*)', range_header)
        groups = match.groups()

        if groups[0]:
            byte1 = int(groups[0])
        if groups[1]:
            byte2 = int(groups[1])

        if not byte2:
            byte2 = byte1 + 1024 * 1024
            if byte2 > filesize:
                byte2 = filesize

        length = byte2 + 1 - byte1

        resp = Response(
            get_chunk(filename, byte1, byte2),
            status=206, mimetype='video/mp4',
            content_type='video/mp4',
            direct_passthrough=True
        )

        resp.headers.add('Content-Range',
                         'bytes {0}-{1}/{2}'
                         .format(byte1,
                                 length,
                                 filesize))
        return resp

    return Response(
        get_video_chunk(filename),
        status=200, mimetype='video/mp4'
    )

def is_media(filepath):
    found_media = re.search("\.mp4$|\.mp3$", filepath, re.IGNORECASE)
    if found_media:
        extension = found_media[0].lower()[1:]
        if found_media in video_types:
            return f"video/{extension}"
        return f"audio/{extension}"
    return False

def is_movie(filepath):
    found_media = re.search("\.mkv$", filepath, re.IGNORECASE)
    if found_media:
        return f"video/mp4"
    return False

def get_file_extension(fname):
    found_extension = re.search("\.[A-Za-z0-9]*$", fname, re.IGNORECASE)
    if found_extension:
        return found_extension[0][1:].lower()