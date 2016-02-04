#!/usr/bin/env python
# coding=utf-8
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
import webapp2
import jinja2

from google.appengine.api import memcache
from google.appengine.ext import db

import json
import datetime
import logging
import re

import utils
import users
from songs import Song
from songs import Recording

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape=True)

class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)
    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)
    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))
        
class MainPage(Handler):
    def get(self):
        self.render("main.html", songs = Song.all_songs())
        
class NewSong(Handler):
    def get(self):
        self.render("newsong.html")
        
    def post(self):
        title = self.request.get('title')
        audiolink = self.request.get('audiolink')
        performer = self.request.get('performer')
        if title:
            s = Song.new_song(title, audiolink, performer)
            self.redirect('/song/%s' % str(s.key().id()))
        else:
            error = u"Название не может быть пустым!"
            self.render("newsong.html", title = title, audiolink = audiolink, performer = performer, error = error)    
            
class SongPage(Handler):
    def get(self, song_id):
        if utils.is_number(song_id):
            song = Song.get_by_id(int(song_id))
        if song:
            self.render("song.html", song = song, recordings = song.get_recordings())
        else:
            self.error(404)

class AddRecording(Handler):
    def get(self, song_id):
        if utils.is_number(song_id):
            song = Song.get_by_id(int(song_id))
        if song:
            self.render("recording.html", song = song)
        else:
            self.error(404)
            
    def post(self, song_id):
        if utils.is_number(song_id):
            song = Song.get_by_id(int(song_id))
        if not song:
            self.error(404)
                
        audiolink = self.request.get('audiolink')
        performer = self.request.get('performer')
        if audiolink:
            song.add_recording(audiolink, performer)
            self.redirect('/song/%s' % str(song.key().id()))
        else:
            error = u"Линк не может быть пустым"
            self.render("recording.html", song = song, audiolink = audiolink, performer = performer, error = error)
            
class EditRecording(Handler):
    def get(self, song_id, rec_id):
        if utils.is_number(song_id):
            song = Song.get_by_id(int(song_id))
        if song and utils.is_number(rec_id):
            rec = Recording.get_by_id(int(rec_id), parent = song.key())
                        
        if song and rec:
            self.render("recording.html", song = song, audiolink = rec.audiolink, performer = rec.performer)
        else:
            self.error(404)
            
    def post(self, song_id, rec_id):
        if utils.is_number(song_id):
            song = Song.get_by_id(int(song_id))
        if song and utils.is_number(rec_id):
            rec = Recording.get_by_id(int(rec_id), parent = song.key())
            
        audiolink = self.request.get('audiolink')
        performer = self.request.get('performer')
        if audiolink:
            rec.update(audiolink, performer)
            self.redirect('/song/' + str(song.key().id()))
        else:
            error = u"Линк не может быть пустым"
            self.render("recording.html", song = song, audiolink = audiolink, performer = performer, error = error)
            
class DeleteRecording(Handler):            
    def post(self, song_id, rec_id):
        if utils.is_number(song_id):
            song = Song.get_by_id(int(song_id))
        if song and utils.is_number(rec_id):
            rec = Recording.get_by_id(int(rec_id), parent = song.key())
                        
        if song and rec:
            rec.delete_self()
            self.redirect(song.get_url())
        else:
            self.error(404)
            
class EditLyrics(Handler):
    def get(self, song_id):
        if utils.is_number(song_id):
            song = Song.get_by_id(int(song_id))
        if song:
            self.render("song.html", song = song, recordings = song.get_recordings(), edit_lyrics = True)
        else:
            self.error(404)
            
    def post(self, song_id):
        if utils.is_number(song_id):
            song = Song.get_by_id(int(song_id))
        if song:
            lyrics = self.request.get("lyrics")
            song.set_lyrics(lyrics)
            self.redirect(song.get_url())
        else:
            self.error(404)
            
class DeleteSong(Handler):
    def post(self, song_id):
        if utils.is_number(song_id):
            song = Song.get_by_id(int(song_id))
        if song:
            song.delete_self()
            self.redirect('/')
        else:
            self.error(404)
            
class ExportJson(Handler):
    def get(self):
        songs = Song.all_songs()
        self.response.out.write(json.dumps([s.as_dict() for s in songs]))
            
class Import(Handler):
    def get(self):
        self.render("import.html")
        
    def post(self):
        jsn = self.request.get('json')
        try:
            data = json.loads(jsn)
            Song.new_from_dict(data)
        except ValueError as err:
            self.render("import.html", error = str(err))
        self.redirect('/')
            

from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from google.appengine.ext.webapp import blobstore_handlers
import webapp2


# This datastore model keeps track of which users uploaded which photos.
class UserPhoto(ndb.Model):
    user = ndb.StringProperty()
    blob_key = ndb.BlobKeyProperty()


class PhotoUploadFormHandler(webapp2.RequestHandler):
    def get(self):
        upload_url = blobstore.create_upload_url('/upload_photo')
        print "upload_url = " + str(upload_url)
        # To upload files to the blobstore, the request method must be "POST"
        # and enctype must be set to "multipart/form-data".
        self.response.out.write("""
<html><body>
<form action="{0}" method="POST" enctype="multipart/form-data">
  Upload File: <input type="file" name="file"><br>
  <input type="submit" name="submit" value="Submit">
</form>
</body></html>""".format(upload_url))


class PhotoUploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        try:
            print "uploads: " + str(self.get_uploads())
            upload = self.get_uploads()[0]
            print "upload: " + str(upload)
            print "redirecting to " + '/view_photo/%s' % upload.key()
            self.redirect('/view_photo/%s' % upload.key())
        except:
            self.error(500)


class ViewPhotoHandler(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, photo_key):
        print "ViewPhotoHandler"
        
        
        
        if not blobstore.get(photo_key):
            self.error(404)
        else:
            self.send_blob(photo_key)

            
app = webapp2.WSGIApplication([('/', MainPage)
                               ,('/newsong/?', NewSong)
                               ,('/song/([0-9]+)/?', SongPage)
                               ,('/song/([0-9]+)/addrec/?', AddRecording)
                               ,('/song/([0-9]+)/rec/([0-9]+)/edit/?', EditRecording)
                               ,('/song/([0-9]+)/rec/([0-9]+)/delete/?', DeleteRecording)
                               ,('/song/([0-9]+)/edit/?', EditLyrics)
                               ,('/song/([0-9]+)/delete/?', DeleteSong)
                               ,('/export.json', ExportJson)
                               ,('/import/?', Import)
                               ,('/upload', PhotoUploadFormHandler)
                               ,('/upload_photo', PhotoUploadHandler)
                               ,('/view_photo/([^/]+)?', ViewPhotoHandler)
                               #,('/blog/([0-9]+)', Post)
                               #,('/blog/([0-9]+).json', PostJSON)
                               #,('/delete', Delete)
                               #,('/signup', Signup)
                               #,('/login', Login)
                               #,('/logout', Logout)
                               #,('/welcome', Welcome)
                               #,('/flush', Flush)
                              ], debug=True)
