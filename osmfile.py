#
# Copyright (C) 2020, Humanitarian OpenstreetMap Team
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#

import logging
import string
import epdb
from datetime import datetime
import ODKInstance
from shapely.geometry import Point, LineString, Polygon, GeometryCollection


class OsmFile(object):
    """OSM File output"""
    def __init__(self, options=dict(), filespec=None, outdir=None):
        self.options = options
        # Read the config file to get our OSM credentials, if we have any
        # self.config = config.config(self.options)
        self.version = 3
        self.visible = 'true'
        self.osmid = -1
        # Open the OSM output file
        if filespec is None:
            if 'outdir' in self.options:
                self.file = self.options.get('outdir') + "foobar.osm"
        else:
            self.file = open(filespec, 'w')
            # self.file = open(filespec + ".osm", 'w')
        logging.info("Opened output file: " + filespec )
        #logging.error("Couldn't open %s for writing!" % filespec)

        # This is the file that contains all the filtering data
        # self.ctable = convfile(self.options.get('convfile'))
        # self.options['convfile'] = None
        # These are for importing the CO addresses
        self.full = None
        self.addr = None
        # decrement the ID
        self.start = -1

    def isclosed(self):
        return self.file.closed

    def header(self):
        if self.file is not False:
            self.file.write('<?xml version=\'1.0\' encoding=\'UTF-8\'?>\n')
            #self.file.write('<osm version="0.6" generator="gosm 0.1" timestamp="2017-03-13T21:43:02Z">\n')
            self.file.write('<osm version="0.6" generator="gosm 0.1">\n')
            self.file.flush()

    def footer(self):
        #logging.debug("FIXME: %r" % self.file)
        self.file.write("</osm>\n")
        self.file.flush()
        if self.file is False:
            self.file.close()

    def write(self, data=None):
        if type(data) == list:
            if data is not None:
                for line in data:
                    self.file.write("%s\n" % line)
        else:
            self.file.write("%s\n" % data)            

    def createWay(self, way, modified=False):
        """This creates a string that is the OSM representation of a node"""
        attrs = dict()
        osm = ""

        # Add default attributes
        if modified:
            attrs['action'] = 'modify'
        if 'osm_way_id' in way:
            attrs['id'] = int(way['osm_way_id'])
        elif 'osm_id' in way:
            attrs['id'] = int(way['osm_id'])
        elif 'id' in way:
            attrs['id'] = int(way['id'])
        else:
            attrs['id'] = self.start
            self.start -= 1
        if 'version' not in way:
            attrs['version'] = 1
        else:
            attrs['version'] = way['version'] + 1
        attrs['timestamp'] = datetime.now().strftime("%Y-%m-%dT%TZ")
        # If the resulting file is publicly accessible without authentication, THE GDPR applies
        # and the identifying fields should not be included
        attrs['uid'] = way['uid']
        attrs['user'] = way['user']

        # Make all the nodes first. The data in the track has 4 fields. The first two
        # are the lat/lon, then the altitude, and finally the GPS accuracy.
        i = 0
        newrefs = list()
        node = dict()
        for ref in way['refs']:
            node['timestamp'] = attrs['timestamp']
            if 'user' in attrs:
                node['user'] = attrs['user']
            if 'uid' in attrs:
                node['uid'] = attrs['uid']
            node['version'] = 0
            colon = ref.find(';')
            if colon > 0:
                newrefs.append(self.start)
                osm += self.createNode(node) + '\n'
                #node['accuracy'] = ref[:colon]
                ref = ref[colon+1:]
                i = 0
            if i == 0:
                node['lat'] = ref
            if i == 1:
                node['lon'] = ref
            # if i == 2:
            #     node[altitude] = ref
            i += 1

        # Processs atrributes
        line = ""
        for ref, value in attrs.items():
            line += '%s=%r ' % (ref, str(value))
        osm += "  <way " + line + ">"

        for ref in newrefs:
            if ref != 'osm_id':
                osm += '\n    <nd ref="%s"/>' % ref

        if 'tags' in way:
            for key, value in way['tags'].items():
                if key == 'track':
                    continue
                if key not in attrs:
                    osm += "\n    <tag k='%s' v=%r/>" % (key, value)
                if modified:
                    osm += '\n    <tag k="fixme" v="Do not upload this without validation!"/>'
            osm += '\n'

        osm += "  </way>"

        return osm

    def createNode(self, node, modified=False):
        """This creates a string that is the OSM representation of a node"""
        # print(node)
        attrs = dict()
        # Add default attributes
        if modified:
            attrs['action'] = 'modify'

        if 'id' in node:
            attrs['id'] = int(node['id'])
        else:
            attrs['id'] = self.start
            self.start -= 1
        if 'version' not in node:
            attrs['version'] = "1"
        else:
            attrs['version'] = int(node['version']) + 1
        attrs['lat'] = node['lat']
        attrs['lon'] = node['lon']
        attrs['timestamp'] = datetime.now().strftime("%Y-%m-%dT%TZ")
        # If the resulting file is publicly accessible without authentication, THE GDPR applies
        # and the identifying fields should not be included
        attrs['uid'] = node['uid']
        attrs['user'] = node['user']

        # Processs atrributes
        line = ""
        osm = ""
        for ref, value in attrs.items():
            line += '%s=%r ' % (ref, str(value))
        osm += "  <node " + line

        if 'tags' in node:
            for key, value in node['tags'].items():
                if key not in attrs:
                    osm += "\n    <tag k='%s' v=%r/>" % (key, value)
                if modified:
                    osm += '\n    <tag k="fixme" v="Do not upload this without validation!"/>'
            osm += "\n  </node>"
        else:
            osm += "/>"

        return osm

    def createTag(self, field, value):
        """Create a data structure for an OSM feature tag"""
        newval = str(value)
        newval = newval.replace('&', 'and')
        newval = newval.replace('"', '')
        tag = dict()
        # logging.debug("OSM:makeTag(field=%r, value=%r)" % (field, newval))

        newtag = field
        change = newval.split('=')
        if len(change) > 1:
            newtag = change[0]
            newval = change[1]

        tag[newtag] = newval
        return tag
