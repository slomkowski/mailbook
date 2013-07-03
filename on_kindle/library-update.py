#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Mailbook - equivalent for 'Send to Kindle' feature. Script for Kindle 2, 3 and DX. You need Python 2.7 installed
to make it work.

(C) 2013 Michał Słomkowski m.slomkowski@gmail.com

"""

import re
import unicodedata
import os
import os.path
import ConfigParser
import argparse
import sys
import urllib2
import datetime

__version__ = '1.1'
__author__ = 'Michał Słomkowski'
__copyright__ = 'GNU GPL v.3.0'

# CONFIG
userAgent = 'Mozilla/4.0 (compatible; Linux 2.6.22) NetFront/3.4 Kindle/2.5 (screen 824x1200; rotate)'
localLibraryPath = '.'  # /mnt/us/documents/'
metadataFileName = 'FILELIST'
configFileName = 'library-update.ini'

# for development only
useProxy = False

# CODE

def convertToFileName(original):
	"""Removes spaces and special characters from the input string to create a nice file name."""
	# changes languages-specific characters
	out = unicodedata.normalize('NFKD', unicode(original)).encode('ascii', 'ignore').decode('ascii')
	# change spaces
	out = re.sub(" ", "_", out)
	out = re.sub(r'[^\.\w\d\-]', '', out)
	out = out.lower()
	return str(out)

def getConfiguration(configFile = None):
	"""Looks for configuration file and returns ConfigParser object."""
	CONFIG_PATH = [".", os.path.dirname(__file__), localLibraryPath]
	CONFIG_PATH = [os.path.realpath(os.path.join(directory, configFileName)) for directory in CONFIG_PATH]
	if configFile:
		CONFIG_PATH.append(configFile)

	conf = ConfigParser.SafeConfigParser()
	for filePath in CONFIG_PATH:
		try:
			conf.readfp(open(filePath))
			configurationLoaded = True
			break
		except IOError:
			configurationLoaded = False

	if not configurationLoaded:
		print >> sys.stderr, ("Error at loading configuration file.")
		sys.exit(1)

	return conf

def getXfsn(cookieFilePath):
	"""Reads cookie file and returns XFSN string."""
	try:
		with open(cookieFilePath) as file:
			xfsn = re.search(r'x-fsn\s*=\s*(.+)', file.read()).group(1)
	except IOError:
		print >> sys.stderr, ("Could not read cookie file: " + cookieFilePath)
		sys.exit(1)
	except AttributeError:
		print >> sys.stderr, ("Could not find X-FSN in cookie file!")
		sys.exit(1)

	return xfsn

def getRemoteFile(relativePath):
	if useProxy:
		os.environ['http_proxy'] = CONF('http_proxy')
	url = CONF('remote_library') + '/' + relativePath
	request = urllib2.Request(url)
	request.add_header('x-fsn', xfsn)
	print("* Downloading: " + url)
	resp = urllib2.urlopen(request)
	return resp

intro = "Mailbook " + __version__ + " " + __author__
description = intro + """. Script for Kindle."""

parser = argparse.ArgumentParser(description = description)

parser.add_argument("-n", "--no-reboot", action = 'store_true', help = "prevent Kindle from rebooting after update")
parser.add_argument("-g", "--generate", action = 'store_true', help = """don't download updates, generate collections
from the local directory tree then reboot""")
parser.add_argument("-c", "--config", nargs = 1, help = "uses specified configuration file")

args = parser.parse_args()

print(intro)

config = getConfiguration(args.config)

CONF = lambda key: config.get('DEFAULT', key)

xfsn = getXfsn(CONF('cookie_file'))

newMetadata = ConfigParser.SafeConfigParser()
oldMetadata = ConfigParser.SafeConfigParser()

try:
	newMetadata.readfp(getRemoteFile(metadataFileName))
except Exception as exp:
	print >> sys.stderr, ("Could not download metadata file: " + str(exp))
	sys.exit(1)

oldMetadata.read(os.path.join(localLibraryPath, metadataFileName))

# generate list of files to download
filesToDownloadList = []

for collection in [sec for sec in newMetadata.sections() if sec != '__SPECIAL__']:
	collectionDir = lambda: convertToFileName(collection) if collection != '___NO_COLLECTION___' else ''

	for file in newMetadata.options(collection):
		if not oldMetadata.has_option(collection, file):
			filesToDownloadList.append((collection, collectionDir(), file))
		else:
			dateParse = lambda metadata: datetime.datetime.strptime(metadata.get(collection, file), "%Y-%m-%d_%H:%M:%S")
			if dateParse(newMetadata) > dateParse(oldMetadata):
				filesToDownloadList.append((collection, collectionDir(), file))

if len(filesToDownloadList) > 0:
	print("Trying to download %d files..." % len(filesToDownloadList))
else:
	print("No files to download.")

# download files and create directories if needed
for collection, collDir, fileName in filesToDownloadList:
	if collDir != '' and not os.path.exists(collDir):
		print("Creating " + collDir)
		os.makedirs(collDir)
	try:
		partUrl = collDir + "/" + fileName
		downloaded = getRemoteFile(partUrl)
		with open(os.path.join(localLibraryPath, collDir, fileName), 'wb') as local_file:
			local_file.write(downloaded.read())
	except Exception as exp:
		print >> sys.stderr, ("Could download %s file: %s" % (partUrl, str(exp)))
		print >> sys.stderr, ("Omitting.")
		# remove entry about file in order to download it later
		newMetadata.remove_option(collection, fileName)

# save new metadata
try:
	with open(os.path.join(localLibraryPath, metadataFileName), 'w') as file:
		newMetadata.write(file)
except IOError as exp:
	print >> sys.stderr, ("Could not write updated metadata file: " + str(exp))
	sys.exit(1)

# TODO parse restart, collection generating and refresh