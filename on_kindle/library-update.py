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
import time
import hashlib
import json

__version__ = '1.1'
__author__ = 'Michał Słomkowski'
__copyright__ = 'GNU GPL v.3.0'

# CONFIG
userAgent = 'Mozilla/4.0 (compatible; Linux 2.6.22) NetFront/3.4 Kindle/2.5 (screen 824x1200; rotate)'  # for Kindle DX
validFileExtensions = ('.txt', '.mobi', '.azw', '.azw2', '.pdf')

userDirectory = '/shared/kindle'  # /mnt/us/'
localLibraryPath = os.path.join(userDirectory, 'documents')
jsonFilePath = os.path.join(userDirectory, "system/collections.json")
metadataFileName = 'FILELIST'
configFileName = 'library-update.ini'

# for development only
useProxy = False

# CODE

def convertToFileName(original):
	"""Removes spaces and special characters from the input string to create a nice file name."""
	# changes languages-specific characters
	uniString = unicode(original, 'utf-8', 'ignore')
	out = unicodedata.normalize('NFKD', uniString)
	# change spaces
	out = re.sub(" ", "_", out)
	out = re.sub(r'[^\.\w\d\-]', '', out)
	out = out.lower()
	return out.encode('ascii', 'ignore')

def getCollectionNameFromDirectory(directoryName):
	name = directoryName.replace("_", " ")
	name = name[0].upper() + name[1:]
	return name

def getConfiguration(configFile = None):
	"""Looks for configuration file and returns ConfigParser object."""
	CONFIG_PATH = [os.path.dirname(__file__), userDirectory, localLibraryPath, "."]
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
	url = CONF('remote_library') + "/" + relativePath

	request = urllib2.Request(url)
	request.add_header('x-fsn', xfsn)
	print("* Downloading: " + url)
	resp = urllib2.urlopen(request)
	return resp

# for collections


def computeHashEntry(fileName):
	"""
	Function calculates the document entry in JSON file. The entry is a SHA1 hash of the file path with '#' or '*' at the beginning.
	The special regex determines which one should be used. I don't quite understand myself how does it work.

	This function is copied (with modifications) from the script kindle-coll-gen.py
	available at http://kindle-coll-gen.sourceforge.net/
	"""

	AsinPattern = re.compile(r'[^-]+-asin_(?P<asin>[a-zA-Z\d\-]*)-type_(?P<type>\w{4})-v_(?P<index>\d+)')
	CalibreAsin = re.compile(r'\[http://calibre-ebook\.com\].*\x00\x00\x00\x71\x00\x00\x00\x2c([a-zA-Z0-9_-]+).*(PDOC|EBOK)')

	m = AsinPattern.match(os.path.basename(fileName))
	if m is not None:
		hashEntry = '#' + m.group('asin') + '^' + m.group('type')
	else:
		hashEntry = '*' + hashlib.sha1(fileName.encode('utf-8')).hexdigest()

	# try find asin in file
	if fileName.lower().endswith('.mobi'):
		analyzed = 0
		with open(fileName, 'rb') as fd:
			for x in fd:
				if x == None or len(x) == 0 or analyzed > 10000:
					break;

				analyzed = analyzed + len(x)
				m = CalibreAsin.search(x)
				if m != None:
					hashEntry = '#' + m.group(1) + '^' + m.group(2)
					break
	return hashEntry

def printCollections(collections, displayFiles = False):
	"Displays the content of directory tree and the number of documents in each collection."
	overallItems = 0
	for name, files in collections.items():
		overallItems += len(files)
		print("* '%s' - %d items." % (name, len(files)))
		if displayFiles:
			for file in files:
				print("  - %s" % file)
	print(str(overallItems) + " documents in the library.")

def loadJsonFile(collections):
	"Generates collections.json file. Loads the original collection if specified."
	global jsonFilePath

	js = {}
	for colName, colFiles in collections.items():
		colName = colName + "@en-US"
		js[colName] = {}
		js[colName]["lastAccess"] = int(time.time() * 1000)
		js[colName]["items"] = [computeHashEntry(fileName) for fileName in colFiles ]

	with open(jsonFilePath, "w") as fp:
		json.dump(js, fp)
		fp.write("\n")

def getCollections(metadataCollections):
	"""Iterates over directory tree in 'documents' directory and metadata file. Creates the collection list from directories.
	If the directory name matches one of the collections from the metadata, it is used. Otherwise the name is generated.
	"""
	global validFileExtensions
	# get directories
	directoryList = [name for name in os.listdir(localLibraryPath) if os.path.isdir(os.path.join(localLibraryPath, name))]

	metadataCollections = [(name, convertToFileName(name)) for name in metadataCollections]

	def makeCollName(dirName):
		for collName, collDir in metadataCollections:
			if collDir == dirName:
				return collName
		return getCollectionNameFromDirectory(dirName)

	collections = {}
	for directory, collName in [(os.path.join(localLibraryPath, dirName), makeCollName(dirName)) for dirName in directoryList]:
		fileList = []
		for root, dirs, files in os.walk(directory):
			for file in files:
				filePath = os.path.join(root, file)
				if os.path.splitext(filePath)[1].lower() in validFileExtensions:
					fileList.append(filePath)
		collections[collName] = fileList
	return collections

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

filesToDownloadCounter = 0
for collection in [sec for sec in newMetadata.sections() if sec != '___SPECIAL___']:
	fileList = []
	for file in newMetadata.options(collection):
		if not oldMetadata.has_option(collection, file):
			fileList.append(file)
		else:
			dateParse = lambda metadata: datetime.datetime.strptime(metadata.get(collection, file), "%Y-%m-%d_%H:%M:%S")
			if dateParse(newMetadata) > dateParse(oldMetadata):
				fileList.append(file)

	if len(fileList) > 0:
		filesToDownloadList.append((collection, convertToFileName(collection) if collection != '___NO_COLLECTION___' else '', fileList))
		filesToDownloadCounter += len(fileList)

if len(filesToDownloadList) > 0:
	print("Trying to download %d files..." % filesToDownloadCounter)
else:
	print("No files to download.")

# download files and create directories if needed
for collection, collDir, fileList in filesToDownloadList:
	if collDir != '' and not os.path.exists(os.path.join(localLibraryPath, collDir)):
		print("Creating directory for '" + collDir + "'")
		os.makedirs(os.path.join(localLibraryPath, collDir))
	for fileName in fileList:
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
	if len(newMetadata.options(collection)) == 0:
		newMetadata.remove_section(collection)

# save new metadata
try:
	with open(os.path.join(localLibraryPath, metadataFileName), 'w') as file:
		newMetadata.write(file)
except IOError as exp:
	print >> sys.stderr, ("Could not write updated metadata file: " + str(exp))
	sys.exit(1)

# generate collection - combine data from config file and directory tree
newCollections = getCollections([sec for sec in newMetadata.sections() if not re.match(r'___\w+___', sec)])

printCollections(newCollections)
# TODO parse restart, collection generating and refresh

try:
	loadJsonFile(newCollections)
except IOError:
	print("Error by writing 'collections.json' file. Aborting.")
	sys.exit(1)

print("")
print("Collections file saved.")