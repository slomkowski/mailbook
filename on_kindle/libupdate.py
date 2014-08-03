#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Mailbook - equivalent for 'Send to Kindle' feature. Script for Kindle 2, 3 and DX. You need Python 2.7 installed
to make it work. Installation is described here: http://www.mobileread.com/forums/showthread.php?t=153930

(C) 2013 Michał Słomkowski
https://github.com/slomkowski/mailbook

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
import subprocess

__version__ = '1.1'
__author__ = 'Michał Słomkowski'
__copyright__ = 'GNU GPL v.3.0'

# CONFIG
userAgent = 'Mozilla/4.0 (compatible; Linux 2.6.22) NetFront/3.4 Kindle/2.5 (screen 824x1200; rotate)'  # for Kindle DX
validFileExtensions = ('.txt', '.mobi', '.azw', '.azw2', '.pdf')

userDirectory = '/mnt/us/'
localLibraryPath = os.path.join(userDirectory, 'documents')
jsonFilePath = os.path.join(userDirectory, "system/collections.json")
metadataFileName = 'FILELIST'
configFileName = 'libupdate.ini'
useProxy = True

# for development only
DEVEL = False

if DEVEL:
	useProxy = False
	userDirectory = '/shared/kindle'

# CODE

def convertToFileName(original):
	"""Removes spaces and special characters from the input string to create a nice file name.
	"""
	# changes languages-specific characters
	# uniString = unicode(original, 'utf-8', 'ignore')
	if isinstance(original, str):
		out = original
	else:
		out = unicodedata.normalize('NFKD', original)
	# change spaces
	out = re.sub(" ", "_", out)
	out = re.sub(r'[^\.\w\d\-]', '', out)
	out = out.lower()
	return out.encode('ascii', 'ignore')

def getCollectionNameFromDirectory(directoryName):
	name = directoryName.replace("_", " ")
	name = name[0].upper() + name[1:]
	return unicode(name)

def getConfiguration(configFile = None):
	"""Looks for configuration file and returns ConfigParser object.
	"""
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
	"""Reads cookie file and returns XFSN string.
	"""
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
	"""Downloads file from remote HTTP server using defined proxy. Takes relative path as an argument.
	"""
	if useProxy:
		os.environ['http_proxy'] = CONF('http_proxy')
	url = CONF('remote_library') + "/" + relativePath

	request = urllib2.Request(url)
	request.add_header('x-fsn', xfsn)
	print("* Downloading: " + url)
	resp = urllib2.urlopen(request)
	return resp

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
		hashEntry = '*' + hashlib.sha1(fileName).hexdigest()

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
	"""Displays the content of directory tree and the number of documents in each collection.
	"""
	overallItems = 0
	for name, files in collections.items():
		overallItems += len(files)
		print("* '%s' - %d items." % (name, len(files)))
		if displayFiles:
			for file in files:
				print("  - %s" % file)
	print(str(overallItems) + " documents in the library.")

def saveToJsonFile(collections, preserveColls):
	"""Generates collections.json file. Loads the original collection if specified.
	"""
	global jsonFilePath

	changed = False

	oldJson = {}
	js = {}
	preserveColls = True
	with open(jsonFilePath, 'r') as fp:
		try:
			if preserveColls:
				js = json.load(fp)
				fp.seek(0, 0)
			oldJson = json.load(fp)
		except ValueError:
			pass

	for colName, colFiles in collections.items():
		colName = colName + "@en-US"
		try:
		 	_dummy = js[colName]["lastAccess"]
		except KeyError:
			changed = True
			js[colName] = {}
		 	js[colName]["lastAccess"] = int(time.time() * 1000)
		js[colName]["items"] = map(computeHashEntry, colFiles)

	with open(jsonFilePath, "w") as fp:
		json.dump(js, fp, sort_keys = True)
		fp.write("\n")

	return (js != oldJson) or changed

def parseDate(dateString):
	return datetime.datetime.strptime(dateString, "%Y-%m-%d_%H:%M:%S")

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
				return unicode(collName)
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

def generateFilesToDownloadList(oldMetadata, newMetadata):
	"""Takes two ConfigParser objects: old and new metadata and returns the tuple of overall number of files
	and list containing (collection name, collection directory, list of files in collection to download).
	"""

	fileList = []

	counter = 0
	for collection in [sec for sec in newMetadata.sections() if sec != '___SPECIAL___']:
		list = []
		for file in newMetadata.options(collection):
			if not oldMetadata.has_option(collection, file):
				list.append(file)
			else:
				dateParse = lambda metadata: parseDate(metadata.get(collection, file))
				if dateParse(newMetadata) > dateParse(oldMetadata):
					list.append(file)

		if len(list) > 0:
			fileList.append((collection, convertToFileName(collection) if collection != '___NO_COLLECTION___' else '', list))
			counter += len(list)

	return (counter, fileList)

def parseCommandLineArgs():
	"""Constructs help message, parses commandline arguments and returns the object containing them.
	"""

	description = "Script for Kindle."

	parser = argparse.ArgumentParser(description = description)

	parser.add_argument("-n", "--no-reboot", action = 'store_true', help = "prevent Kindle from rebooting after update")
	parser.add_argument("-g", "--generate", action = 'store_true', help = """don't download updates, generate collections
	from the local directory tree then reboot""")
	parser.add_argument("-c", "--config", nargs = 1, help = "uses specified configuration file")

	return parser.parse_args()

# check if reboot was selected
def checkRebootFlag(oldMetadata, newMetadata):
	"""Takes two ConfigParser objects: old and new metadata and returns True if reboot was sheduled.
	"""

	try:
		newDate = parseDate(newMetadata.get("___SPECIAL___", "RestartTimeStamp"))
	except:
		return False
	try:
		oldDate = parseDate(oldMetadata.get("___SPECIAL___", "RestartTimeStamp"))
	except:
		return True
	return newDate > oldDate

# MAIN

intro = "Mailbook " + __version__ + " " + __author__
print(intro)

args = parseCommandLineArgs()

config = getConfiguration(args.config)

CONF = lambda key: config.get('DEFAULT', key)

# read actual local metadata
oldMetadata = ConfigParser.SafeConfigParser()
newMetadata = ConfigParser.SafeConfigParser()

oldMetadata.read(os.path.join(localLibraryPath, metadataFileName))

if not args.generate:
	xfsn = getXfsn(CONF('cookie_file'))

	# get new metadata from remote location
	try:
		newMetadata.readfp(getRemoteFile(metadataFileName))
	except Exception as exp:
		print >> sys.stderr, ("Could not download metadata file: " + str(exp))
		sys.exit(1)

	# compare old and new metadata and find files to download
	filesToDownloadCounter, filesToDownloadList = generateFilesToDownloadList(oldMetadata, newMetadata)

	if filesToDownloadCounter > 0:
		print("Trying to download %d files..." % filesToDownloadCounter)
	else:
		print("No files to download.")

	# Download files and create directories if needed.
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

	# replace local metadata with new one
	try:
		with open(os.path.join(localLibraryPath, metadataFileName), 'w') as file:
			newMetadata.write(file)
	except IOError as exp:
		print >> sys.stderr, ("Could not write updated metadata file: " + str(exp))
		sys.exit(1)

# generate collection - combine data from config file and directory tree
collectionsList = lambda metadata: [sec.decode('utf-8') for sec in metadata.sections() if not re.match(r'___\w+___', sec)]

if not args.generate:
	newCollections = getCollections(collectionsList(newMetadata))
else:
	newCollections = getCollections(collectionsList(oldMetadata))

print("Collections from directory structure:")
printCollections(newCollections)

preserveExistingCollections = CONF('preserve_existing_collections')
if preserveExistingCollections:
	print("Preserving existing collections.")

try:
	jsonChanged = saveToJsonFile(newCollections, preserveExistingCollections)
except IOError:
	print("Error by writing 'collections.json' file. Aborting.")
	sys.exit(1)

print("")
if jsonChanged:
	print("Collections file saved.")
else:
	print("No changes in collections.")

# don't reboot if collections don't changed
if (checkRebootFlag(oldMetadata, newMetadata) or args.generate) and not args.no_reboot and jsonChanged:
	print("Rebooting system...")
	if not DEVEL:
		subprocess.call(("reboot"))
else:
	# call library refreshing
	print("Refreshing library.")
	subprocess.call("dbus-send --system /default com.lab126.powerd.resuming int32:1".split())
