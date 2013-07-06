#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Mailbook - equivalent for 'Send to Kindle' feature. Script for local PC.

(C) 2012, 2013 Michał Słomkowski m.slomkowski@gmail.com

"""

import re
import unicodedata
import os
import os.path
import configparser
import time
import tempfile
import argparse
import sys
import shutil
import subprocess

__version__ = '1.1'
__author__ = 'Michał Słomkowski'
__copyright__ = 'GNU GPL v.3.0'

# CONFIG

remotePath = '#### INSERT URL TO YOUR LIBRARY ON SHELL ACCOUNT ####'
metadataFileName = "FILELIST"

# Configuration of the converter to .mobi format. Present setting is for ebook-convert from Calibre.
mobiConverter = {
		'command' : 'ebook-convert %%OLD_NAME%% %%NEW_NAME%%',
		# TODO check values_success
		'values_success' : (0, 1)
		}

# formats which will be added to the library. Other files are omitted. The boolean value indicates the need to convert it to .mobi format.
supportedFormats = {
		# convert
		'epub' : True,
		'txt' : True,
		'html' : True,
		'htm' : True,
		'rtf' : True,
		'doc' : True,
		# don't convert
		'mobi' : False,
		'azw' : False,
		'azw2' : False,
		'pdf' : False
		}
# for debug & development
disableSendingChanges = False

# CODE

def convertToFileName(original):
	"""Removes spaces and special characters from the input string to create a nice file name."""
	# changes languages-specific characters
	out = unicodedata.normalize('NFKD', original).encode('ascii', 'ignore').decode('ascii')
	# change spaces
	out = re.sub(" ", "_", out)
	out = re.sub(r'[^\.\w\d\-]', '', out)
	out = out.lower()
	return out


# filter files by extension
def getValidFileList(fileList, printInvalidFileError = True):
	"""Takes some file list. Checks if these files exists and have appropriate extension."""
	validFileList = []  # (performConvert, originalFilename, newFilename)
	for f in fileList:
		if not os.path.isfile(f):
			print("Error! File " + f + " doesn't exist.")
		found = False
		for ext in supportedFormats:
			if re.search(r'\.' + ext + r'$', f):
				found = True
				newFileName = convertToFileName(os.path.basename(f))
				if supportedFormats[ext]:  # when perform convert
					newFileName = re.sub(r'\.' + ext + '$', r'.mobi', newFileName)
					performConvert = True
				else:
					performConvert = False
				validFileList.append((performConvert, os.path.abspath(f), newFileName))
				break
		if printInvalidFileError and not found:
			print("Warning! File " + f + " has not valid extension. Omitting.")
	return validFileList


def convertFiles(fileList, outputDir):
	"""Takes the list of files and converts them to .mobi format."""
	outputDir = os.path.abspath(outputDir) + "/"
	updateList = []
	for (conversion, name, newName) in fileList:
		if not conversion:
			print('* ' + name)
			shutil.copy(name, os.path.join(outputDir, newName))
			updateList.append(newName)
		else:
			print('* ' + os.path.basename(name) + " > " + newName + "  || Conversion ...")  # no newline
			sys.stdout.flush()

			command = re.sub(r'%%OLD_NAME%%', name, mobiConverter['command'])
			command = re.sub(r'%%NEW_NAME%%', os.path.join(outputDir, newName), command)

			devNull = open("/dev/null", "w")
			ret = subprocess.call(command.split(), stdout = devNull, stderr = devNull)
			devNull.close()

			if ret in mobiConverter['values_success']:
				print("  OK.")
				updateList.append(newName)
			else:
				print("  failed.")

	return updateList

def updateMetadataFile(metadataFile, filesList, restartFlag, collection = None, collectionExact = False):
	"""Reads metadata file and applies metadata."""

	metadata = configparser.SafeConfigParser()
	metadata.read(metadataFile)

	timestamp = time.strftime("%Y-%m-%d_%H:%M:%S", time.gmtime())

	if collection:
		if not collectionExact:
			matches = [name for name in metadata.sections() if re.match(collection, name, re.I)]

			if len(matches) > 0:
				collection = min(matches, key = len)

		if collection in metadata.sections():
			print("Using collection name: " + collection)
		else:
			print("Creating collection: " + collection)

	else:
		collection = "___NO_COLLECTION___"

	if not metadata.has_section(collection):
		metadata.add_section(collection)

	if restartFlag:
		print("Applying restart flag.")
		metadata['___SPECIAL___'] = {}
		metadata['___SPECIAL___']['RestartTimeStamp'] = timestamp;

	for file in filesList:
		metadata.set(collection, file, timestamp)

	with open(metadataFile, 'w') as configfile:
	    metadata.write(configfile)

	# return proposed directory name for collection
	if collection == "___NO_COLLECTION___":
		return ''
	else:
		return convertToFileName(collection)

# get command line options

intro = "Mailbook " + __version__ + " " + __author__
description = intro + """. Script for local computer. It grabs local ebook files,
converts them to .mobi format using Calibre if needed and sends them to shell account using scp.
Usage: kindle.py [--options] [files]"""

parser = argparse.ArgumentParser(description = description)

parser.add_argument("-d", "--delete", action = 'store_true', help = "delete original files")
parser.add_argument("-r", "--restart", action = 'store_true', help = "restart Kindle after update. Needed to apply generated collections")

group = parser.add_mutually_exclusive_group()
group.add_argument("-c", "--collection", nargs = 1, help = """collection name. You can specify partial name which matches existing collection.
If the match doesn't exist, the new collection will be created. If more than one collection name match, the files will be added to one of them""")
group.add_argument("-C", "--collection-exact", nargs = 1, help = """exact collection name. Disables partial name checking. You should use it when creating collection.""")

parser.add_argument("files", action = 'append', nargs = "*")
args = parser.parse_args()

print(intro)

if len(args.files[0]) == 0:
	# in this case the files are taken from current directory.
	fileList = getValidFileList([ f for f in os.listdir(".") if os.path.isfile(f) ], False)
else:
	# in this case files are explicitly specified in command line
	fileList = getValidFileList(args.files[0], True)

if len(fileList) == 0:
	print("No valid files to send.")
	exit()

tempDir = tempfile.mkdtemp('kindle')

# check if it's possible to download the .ini file with metadata
print("Trying to download actual file list...")
ret = subprocess.call(["scp", remotePath + "/" + metadataFileName, tempDir])  # , stdout = devNull, stderr = devNull)
if ret != 0:
	print("Cannot download " + metadataFileName)
	exit(1)

filesToUpdate = convertFiles(fileList, outputDir = tempDir)

up = lambda coll, exact: updateMetadataFile(os.path.join(tempDir, metadataFileName), filesToUpdate, args.restart, coll, exact)
if args.collection_exact:
	collectionDirectory = up(args.collection_exact[0], True)
elif args.collection:
	collectionDirectory = up(args.collection[0], False)
else:
	collectionDirectory = up(None, False)

# if collection is specified, copy all files to new folder within tempDir. It's needed to copy it via SSH later.
if collectionDirectory:
	collDir = os.path.join(tempDir, collectionDirectory)
	os.mkdir(collDir)
	for file in map(lambda f: os.path.join(tempDir, f), filesToUpdate):
		shutil.move(file, collDir)
	updateList = [collDir]
else:
	updateList = [ os.path.join(tempDir, f) for f in filesToUpdate ]

# send files to remote server
if not disableSendingChanges:
	print("Trying to send " + str(len(filesToUpdate)) + " files...")

	commandList = ["scp", "-rC"]

	commandList.extend(updateList)
	commandList.append(os.path.join(tempDir, metadataFileName))

	commandList.append(remotePath)
	ret = subprocess.call(commandList)  # , stdout = devNull, stderr = devNull)
	if ret == 0:
		print("OK.")
	else:
		print("Error. Preserving " + tempDir + " and original files.")
		exit(1)

	shutil.rmtree(tempDir)

if args.delete:
	for (c, originalFile, n) in fileList:
		print("Removing " + originalFile)
		os.remove(originalFile)
