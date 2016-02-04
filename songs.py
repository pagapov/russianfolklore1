from google.appengine.ext import db
from google.appengine.api import memcache
import logging
import re
    
# https://drive.google.com/open?id=0B3NX21EKcTD7ZjFlNTd1T05LNGM    
# http://docs.google.com/uc?export=open&id=0B3NX21EKcTD7ZjFlNTd1T05LNGM
GOOGLEDRIVE_LINK_RE = re.compile(r"^(?:https?://)?drive.google.com/open\?id=([a-zA-Z0-9-]+)$")
def fix_googledrive_link(link):
    m = GOOGLEDRIVE_LINK_RE.match(link)
    if m:
        return r"http://docs.google.com/uc?export=open&id=%s" % m.group(1)
    else:
        return link
    
class Recording(db.Model):
    audiolink = db.StringProperty()
    performer = db.StringProperty()
    
    def get_audiolink(self):
        return fix_googledrive_link(self.audiolink)
    
    @classmethod
    def new_recording(cls, song, audiolink, performer):
        r = Recording(audiolink = audiolink, performer = performer, parent = song.key())
        r.put()
        Recording.get(r.key())
        return r
    
    def update(self, audiolink, performer):
        self.audiolink = audiolink
        self.performer = performer
        self.put()
        Recording.get(self.key())
        self.parent().get_recordings(True)
        
    def get_title(self):
        if self.performer:
            return self.parent().title + " - " + self.performer
        else:
            return self.parent().title
    
    def get_edit_url(self):
        return "/song/%d/rec/%d/edit" % (self.parent().key().id(), self.key().id())

    def get_delete_url(self):
        return "/song/%d/rec/%d/delete" % (self.parent().key().id(), self.key().id())
    
    def delete_self(self):
        song = self.parent()
        key = self.key()
        self.delete()
        Recording.get(key)
        song.get_recordings(True)
        
    def as_dict(self):
        return {
            'audiolink': unicode(self.audiolink),
            'performer': unicode(self.performer)
        }

class Song(db.Model):
    title = db.StringProperty(required = True)
    lyrics = db.TextProperty()
    
    @classmethod
    def new_song(cls, title, audiolink, performer):
        s = Song(title = title, lyrics = "")
        s.put()
        Song.get(s.key())
        if audiolink:
            s.add_recording(audiolink, performer)
        Song.all_songs(True)
        return s
    
    @classmethod
    def new_from_dict(cls, data):
        for d in data:
            s = Song(title = d['title'], lyrics = d['lyrics'])
            s.put()
            Song.get(s.key())
            for r in d['recordings']:
                Recording.new_recording(s, r['audiolink'], r['performer'])  
    
    def delete_self(self):
        key = self.key()
        self.delete()
        Song.get(key)
        Song.all_songs(True)
    
    def get_recordings(self, update = False):
        key = 'recordings-' + str(self.key().id())
        recordings = memcache.get(key)
        if recordings is None or update:
            logging.error("DB QUERY " + key)
            recordings = Recording.all().order('performer')
            if recordings:
                recordings.ancestor(self)
                recordings = list(recordings)
            memcache.set(key, recordings)
        return recordings
    
    def add_recording(self, audiolink, performer = ""):
        r = Recording.new_recording(self, audiolink, performer)
        self.get_recordings(True)
        return r
    
    def get_url(self):
        return "/song/%d" % self.key().id()
    
    def get_add_rec_url(self):
        return "/song/%d/addrec" % self.key().id()        

    def get_edit_lyrics_url(self):
        return "/song/%d/edit" % self.key().id()

    def get_delete_url(self):
        return "/song/%d/delete" % self.key().id()
    
    def render_lyrics(self):
        s = self.lyrics
        if s:
            return s.replace('\n', '<br>')
        else:
            return ""
        
    def set_lyrics(self, lyrics):
        self.lyrics = lyrics
        self.put()
        Song.get(self.key())
        
    @classmethod
    def all_songs(cls, update = False):
        key = 'all_songs'
        songs = memcache.get(key)
        if songs is None or update:
            logging.error("DB QUERY " + key)
            songs = db.GqlQuery("SELECT * FROM Song ORDER BY title")
            if songs:
                songs = list(songs)
            memcache.set(key, songs)
        return songs
    
    def as_dict(self):
        return {
            'title': unicode(self.title),
            'lyrics': unicode(self.lyrics),
            'recordings': [r.as_dict() for r in self.get_recordings()]
        }
        