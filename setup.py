from flask import Flask, render_template, request, send_file, redirect, session, jsonify
from werkzeug.utils import secure_filename
from hurry.filesize import size
from datetime import datetime
from flask_fontawesome import FontAwesome
from flask_qrcode import QRcode
from pathlib import Path
import os
import mimetypes
import sys
import re
import json
import zipfile
from PIL import Image
import subprocess
import requests

from utils import get_file_extension, get_file, is_media, update_ip_cache, IP_CACHE, log
from config import *
from urllib.parse import unquote
import socket
hostname = socket.gethostname()
IPAddr = socket.gethostbyname(hostname)
print("Your Computer Name is: " + hostname)
print("Your Computer IP Address is: " + IPAddr)
maxNameLength = 15

STATIC_FOLDER = os.path.join(os.getcwd(), 'static')

app = Flask(__name__)
#app.config["SERVER_NAME"] = "wifile.com"
app.secret_key = 'my_secret_key'

# FoNT AWESOME
fa = FontAwesome(app)
# QRcode
qrcode = QRcode(app)
# Config file
config = os.path.abspath(os.path.join(os.path.dirname(__file__), "config.json"))
with open(config) as json_data_file:
    data = json.load(json_data_file)
hiddenList = data["Hidden"]
favList = data["Favorites"]
password = data["Password"]
adminpassword = data["AdminPassword"]

currentDirectory = data["rootDir"]
osWindows = False  # Not Windows
default_view = 0

if 'win32' in sys.platform or 'win64' in sys.platform:
    # import win32api
    osWindows = True
    # WINDOWS FEATURE
    # drives = win32api.GetLogicalDriveStrings()
    # drives=drives.replace('\\','')
    # drives = drives.split('\000')[:-1]
    # drives.extend(favList)
    # favList=drives

if(len(favList) > 10):
    favList = favList[0:10]
# print(favList)
# if(len(favList)>0):
#     for i in range(0,len(favList)):

#         favList[i]=favList[i].replace('\\','>') #CHANGE FOR MAC

# WINDOWS FEATURE
# drives = win32api.GetLogicalDriveStrings()
# drives=drives.replace('\\','')
# drives = drives.split('\000')[:-1]
# drives.extend(favList)
# favList=drives

def get_location(ip):
    global IP_CACHE
    if ip in IP_CACHE.keys():
        log("ACCESS", ip)
        return IP_CACHE[ip]
    
    url = "http://api.ipstack.com/{}?access_key={}&output=json&legacy=1".format(ip, data["IPSTACK_API_KEY"])
    r = requests.get(url)

    if r.text:
        location_json = r.json()
        IP_CACHE[ip] = location_json
        update_ip_cache()
        log("ACCESS", ip)
        return location_json

@app.before_request
def update_remote_addr():
    request.remote_addr = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    get_location(request.remote_addr)

def make_zipfile(output_filename, source_dir):
    relroot = os.path.abspath(os.path.join(source_dir, os.pardir))
    with zipfile.ZipFile(output_filename, "w", zipfile.ZIP_DEFLATED) as zip:
        for root, dirs, files in os.walk(source_dir):
            # add directory (needed for empty dirs)
            zip.write(root, os.path.relpath(root, relroot))
            for file in files:
                filename = os.path.join(root, file)
                if os.path.isfile(filename):  # regular files only
                    arcname = os.path.join(
                        os.path.relpath(root, relroot), file)
                    zip.write(filename, arcname)

@app.after_request
def after_request(response):
    response.headers.add('Accept-Ranges', 'bytes')
    return response

@app.route('/login/')
@app.route('/login/<path:var>')
def loginMethod(var=""):
    global password
    # print("LOGGING IN")
    # print(var)
    if(password == ''):
        session['login'] = True
    if('login' in session):
        return redirect('/'+var)
    else:
        return render_template('login.html')


@app.route('/login/', methods=['POST'])
@app.route('/login/<path:var>', methods=['POST'])
def loginPost(var=""):
    global password
    text = request.form['text']
    if(text == password):
        session['login'] = True
        session['admin'] = False
        return redirect('/'+var)
    elif(text == adminpassword):
        session['login'] = True
        session['admin'] = True
        return redirect('/'+var)
    else:
        return redirect('/login/'+var)


@app.route('/logout/')
def logoutMethod():
    if('login' in session):
        session.pop('login', None)
    return redirect('/login/')

# @app.route('/exit/')
# def exitMethod():
#    exit()

def hidden(path):
    if session['admin']:
        return False
    for i in hiddenList:
        if i != '' and i in path:
            return True
    return False


def changeDirectory(path):
    global currentDirectory, osWindows
    pathC = path.split('/')
    # print(path)
    if(osWindows):
        myPath = '//'.join(pathC)+'//'
    else:
        myPath = '/'+'/'.join(pathC)
    # print(myPath)
    myPath = unquote(myPath)
    # print("HELLO")
    # print(myPath)
    try:
        os.chdir(myPath)
        ans = True
        # if (osWindows):
        #     if(currentDirectory.replace('/', '\\') not in os.getcwd()):
        #         ans = False
        # else:
        #     if(currentDirectory not in os.getcwd()):
        #         ans = False
    except:
        ans = False
    return ans

# def getDirList():
#     dList= list(filter(lambda x: os.path.isdir(x), os.listdir('.')))
#     finalList = []
#     curDir=os.getcwd()

#     for i in dList:
#         if(hidden(curDir+'/'+i)==False):
#             finalList.append(i)

#     return(finalList)

def create_video_thumbnail(in_path, out_path):
    video_input_path = in_path
    img_output_path = out_path
    subprocess.call(['ffmpeg', '-hwaccel_device', '0', '-hwaccel', 'opencl', '-i', video_input_path, '-ss', '00:00:05.000', '-vframes', '1', img_output_path])


def create_thumbnail(dir, path):
    thumbs_path = os.path.join(STATIC_FOLDER, "thumbs")
    thumbfile_path = dir.split(":")[-1].strip("\\").replace("/", "_").replace("\\", "_") + "_" + path + ".png"
    out_path = os.path.join(thumbs_path, thumbfile_path)
    if os.path.exists(out_path):
        return "thumbs/" + thumbfile_path
    
    # with open(dir + "/" + path, 'r+b') as f:
    #     with Image.open(f) as image:
    #         image.save(os.path.join(thumbs_path, path), image.format)
    create_video_thumbnail(os.path.join(dir, path), out_path)
    return "thumbs/" + thumbfile_path

@app.route('/changeView')
def changeView():
    global default_view
    # print('view received')
    v = int(request.args.get('view', 0))
    if v in [0, 1]:
        default_view = v
    else:
        default_view = 0

    return jsonify({
        "txt": default_view,
    })


def getDirList():
    # print(default_view)
    global maxNameLength, tp_dict, hostname
    dList = list(os.listdir('.'))
    dList = list(filter(lambda x: os.path.isdir(x), os.listdir('.')))
    dir_list_dict = {}
    fList = list(filter(lambda x: not os.path.isdir(x), os.listdir('.')))
    file_list_dict = {}
    curDir = os.getcwd()
    # print(os.stat(os.getcwd()))
    filetype = None
    for i in dList:
        if(hidden(curDir+'/'+i) == False):
            image = 'folder5.png'
            if len(i) > maxNameLength:
                dots = "..."
            else:
                dots = ""
            dir_stats = os.stat(i)
            dir_list_dict[i] = {}
            dir_list_dict[i]['f'] = i[0:maxNameLength]+dots
            dir_list_dict[i]['f_url'] = re.sub("#", "|HASHTAG|", i)
            dir_list_dict[i]['currentDir'] = curDir
            dir_list_dict[i]['f_complete'] = i
            dir_list_dict[i]['image'] = image
            dir_list_dict[i]['dtc'] = datetime.utcfromtimestamp(dir_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
            dir_list_dict[i]['dtm'] = datetime.utcfromtimestamp(dir_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            dir_list_dict[i]['size'] = "---"

    for i in fList:
        filetype = None
        if(hidden(curDir+'/'+i) == False):
            image = None
            try:
                tp = get_file_extension(i)
                for type, file_type in tp_dict.items():
                    if tp in file_type[0]:
                        filetype = type
                        image = "files_icon/"+file_type[1]
                        break
                tp = "" if not tp else tp
            except:
                pass
            if not image:
                image = 'files_icon/unknown-icon.png'
            if len(i) > maxNameLength:
                dots = "..."
            else:
                dots = ""
            file_list_dict[i] = {}
            file_list_dict[i]['f'] = i[0:maxNameLength]+dots
            file_list_dict[i]['f_url'] = re.sub("#", "|HASHTAG|", i)
            file_list_dict[i]['currentDir'] = curDir
            file_list_dict[i]['f_complete'] = i
            file_list_dict[i]['image'] = image
            file_list_dict[i]['supported'] = True if tp.lower() in supported_formats else False
            if filetype == 'video':
                create_thumbnail(curDir, i)
                file_list_dict[i]['thumb'] = create_thumbnail(curDir, i)
            file_list_dict[i]['type'] = filetype
            try:
                dir_stats = os.stat(i)
                file_list_dict[i]['dtc'] = datetime.utcfromtimestamp(dir_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
                file_list_dict[i]['dtm'] = datetime.utcfromtimestamp(dir_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                file_list_dict[i]['size'] = size(dir_stats.st_size)
                file_list_dict[i]['size_b'] = dir_stats.st_size
            except:
                file_list_dict[i]['dtc'] = "---"
                file_list_dict[i]['dtm'] = "---"
                file_list_dict[i]['size'] = "---"
    return dir_list_dict, file_list_dict


def getFileList():
    dList = list(filter(lambda x: os.path.isfile(x), os.listdir('.')))
    finalList = []
    curDir = os.getcwd()
    for i in dList:
        if(hidden(curDir+'/'+i) == False):
            finalList.append(i)
    return(finalList)


@app.route('/files/', methods=['GET'])
@app.route('/files/<path:var>', methods=['GET'])
def filePage(var=""):
    global default_view
    if('login' not in session):
        return redirect('/login/files/'+var)
    # print(var)
    if(changeDirectory(var) == False):
        # Invalid Directory
        print("Directory Doesn't Exist")
        return render_template('404.html', errorCode=300, errorText='Invalid Directory Path', favList=favList)

    try:
        dir_dict, file_dict = getDirList()
        if default_view == 0:
            var1, var2 = "DISABLED", ""
            default_view_css_1, default_view_css_2 = '', 'style=display:none'
        else:
            var1, var2 = "", "DISABLED"
            default_view_css_1, default_view_css_2 = 'style=display:none', ''
    except:
        raise
        return render_template('404.html', errorCode=200, errorText='Permission Denied', favList=favList)
    if osWindows:
        cList = var.split('/')
        var_path = '<a style = "color:black;"href = "/files/' + \
            cList[0]+'">'+unquote(cList[0])+'</a>'
        for c in range(1, len(cList)):
            var_path += ' / <a style = "color:black;"href = "/files/' + \
                '/'.join(cList[0:c+1])+'">'+unquote(cList[c])+'</a>'
    else:
        cList = var.split('/')
        var_path = '<a href = "/files/"><img src = "/static/root.png" style = "height:25px;width: 25px;">&nbsp;</a>'
        for c in range(0, len(cList)):
            var_path += ' / <a style = "color:black;"href = "/files/' + \
                '/'.join(cList[0:c+1])+'">'+unquote(cList[c])+'</a>'
    return render_template('home.html', currentDir=var, favList=favList, default_view_css_1=default_view_css_1, default_view_css_2=default_view_css_2, view0_button=var1, view1_button=var2, currentDir_path=var_path, dir_dict=dir_dict, file_dict=file_dict)


@app.route('/', methods=['GET'])
def homePage():
    global currentDirectory, osWindows
    if('login' not in session):
        return redirect('/login/')
    if osWindows:
        if(currentDirectory == ""):
            return redirect('/files/C:')
        else:
            # cura = currentDirectory
            #cura = '>'.join(currentDirectory.split('\\'))
            return redirect('/files/'+currentDirectory)
    else:
        return redirect('/files/'+currentDirectory)
        # REDIRECT TO UNTITLED OR C DRIVE FOR WINDOWS OR / FOR MAC

@app.route('/logs', methods=['GET'])
def viewLogs():
    global currentDirectory, osWindows
    if('admin' not in session):
        return redirect('/login/')
    if osWindows:
        logs = {}
        with open(os.path.abspath(os.path.join(os.path.dirname(__file__), SERVER_LOG)), 'r') as f:
            logs = f.readlines()[-50:]
        return "<br>".join(logs)

@app.route('/browse/<path:var>', defaults={"browse":True})
@app.route('/download/<path:var>', defaults={"browse":False})
def browseFile(var, browse):
    var = var.replace("|HASHTAG|", "#")
    if('login' not in session):
        return redirect('/login/download/'+var)
    # os.chdir(currentDirectory)
    pathC = unquote(var).split('/')
    #print(var)
    if(pathC[0] == ''):
        pathC.remove(pathC[0])
    # if osWindows:
    #     fPath = currentDirectory+'//'.join(pathC)
    # else:
    #     fPath = '/'+currentDirectory+'//'.join(pathC)
    if osWindows:
        fPath = '//'.join(pathC)
    else:
        fPath = '/'+'//'.join(pathC)
    # print("HELLO")
    # print('//'.join(fPath.split("//")[0:-1]))
    # print(hidden('//'.join(fPath.split("//")[0:-1])))
    f_path_hidden = '//'.join(fPath.split("//")[0:-1])
    if(hidden(f_path_hidden) == True or changeDirectory(f_path_hidden) == False):
        # FILE HIDDEN
        return render_template('404.html', errorCode=100, errorText='File Hidden', favList=favList)
    fName = pathC[len(pathC)-1]
    #print(fPath)
    if browse:
        is_media_file = is_media(fPath)
        if is_media_file:
            return get_file(fPath, is_media_file)
    return send_file(fPath)
    try:
        return send_file(fPath, download_name=fName)
    except:
        return render_template('404.html', errorCode=200, errorText='Permission Denied', favList=favList)


@app.route('/downloadFolder/<path:var>')
def downloadFolder(var):
    if('login' not in session):
        return redirect('/login/downloadFolder/'+var)
    pathC = var.split('/')
    if(pathC[0] == ''):
        pathC.remove(pathC[0])
    if osWindows:
        fPath = '//'.join(pathC)
    else:
        fPath = '/'+'//'.join(pathC)
    f_path_hidden = '//'.join(fPath.split("//")[0:-1])
    if(hidden(f_path_hidden) == True or changeDirectory(f_path_hidden) == False):
        # FILE HIDDEN
        return render_template('404.html', errorCode=100, errorText='File Hidden', favList=favList)
    fName = pathC[len(pathC)-1]+'.zip'
    downloads_folder = str(Path.home() / "Downloads\\temp")
    if not os.path.exists(downloads_folder):
        os.mkdir(downloads_folder)
    try:
        make_zipfile(downloads_folder+'\\abc.zip', os.getcwd())
        return send_file(downloads_folder+'\\abc.zip', attachment_filename=fName)
    except Exception as e:
        print(e)
        return render_template('404.html', errorCode=200, errorText='Permission Denied', favList=favList)


@app.errorhandler(404)
def page_not_found(e):
    if('login' not in session):
        return redirect('/login/')
    # note that we set the 404 status explicitly
    return render_template('404.html', errorCode=404, errorText='Page Not Found', favList=favList), 404


@app.route('/upload/', methods=['GET', 'POST'])
@app.route('/upload/<path:var>', methods=['GET', 'POST'])
def uploadFile(var=""):
    if('login' not in session):
        return render_template('login.html')
    text = ""
    if request.method == 'POST':
        pathC = var.split('/')
        if(pathC[0] == ''):
            pathC.remove(pathC[0])
        # if osWindows:
        #     fPath = currentDirectory+'//'.join(pathC)
        # else:
        #     fPath = '/'+currentDirectory+'//'.join(pathC)
        if osWindows:
            fPath = '//'.join(pathC)
        else:
            fPath = '/'+'//'.join(pathC)
        f_path_hidden = fPath
        # print(f_path_hidden)
        # print(hidden(f_path_hidden))
        if(hidden(f_path_hidden) == True or changeDirectory(f_path_hidden) == False):
            # FILE HIDDEN
            return render_template('404.html', errorCode=100, errorText='File Hidden', favList=favList)
        files = request.files.getlist('files[]')
        fileNo = 0
        for file in files:
            fupload = os.path.join(fPath, file.filename)
            if secure_filename(file.filename) and not os.path.exists(fupload):
                try:
                    file.save(fupload)
                    print(file.filename + ' Uploaded')
                    text = text + file.filename + ' Uploaded<br>'

                    fileNo = fileNo + 1
                except Exception as e:
                    print(file.filename + ' Failed with Exception '+str(e))
                    text = text + file.filename + \
                        ' Failed with Exception '+str(e) + '<br>'
                    continue
            else:
                print(file.filename +
                      ' Failed because File Already Exists or File Type Issue')
                text = text + file.filename + \
                    ' Failed because File Already Exists or File Type not secure <br>'
    fileNo2 = len(files)-fileNo
    return render_template('uploadsuccess.html', text=text, fileNo=fileNo, fileNo2=fileNo2, favList=favList)


@app.route('/qr/<path:var>')
def qrFile(var):
    global hostname
    if('login' not in session):
        return redirect('/login/qr/'+var)
    # os.chdir(currentDirectory)
    pathC = unquote(var).split('/')
    if(pathC[0] == ''):
        pathC.remove(pathC[0])
    if osWindows:
        fPath = '//'.join(pathC)
    else:
        fPath = '/'+'//'.join(pathC)
    f_path_hidden = '//'.join(fPath.split("//")[0:-1])
    if(hidden(f_path_hidden) == True or changeDirectory(f_path_hidden) == False):
        # FILE HIDDEN
        return render_template('404.html', errorCode=100, errorText='File Hidden', favList=favList)
    fName = pathC[len(pathC)-1]
    qr_text = 'http://'+hostname+"//download//"+fPath
    return send_file(qrcode(qr_text, mode="raw"), mimetype="image/png")
    return send_file(fPath, attachment_filename=fName)


if __name__ == '__main__':
    local = "127.0.0.1"
    public = '0.0.0.0'
    app.run(host=public, debug=True, port=80, threaded=True)
