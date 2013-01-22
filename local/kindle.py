#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Script converts documents in current directory and sends them to Kindle. With no parameters, it converts the current directory. You can also specify files to convert in commandline.

(C) 2012 Michał Słomkowski m.slomkowski@gmail.com

"""

import re, unicodedata, os, configparser, time, tempfile, getopt, sys, shutil, subprocess

# CONFIG

# formats which will be added to the library. Other files are omitted. The boolean value indicates the need to convert it to the .mobi format.
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

remotePath = '#### PUT HERE THE PATH TO YOUR REMOTE FOLDER WITH BOOKS ###	'
changedFilesList = "FILELIST"

# for debug & development
disableSendingChanges = False

# CODE


def convertFileName(originalFileName):
	"""Removes spaces and special characters from the file name."""
	# changes languages-specific characters
	out = unicodedata.normalize('NFKD', originalFileName).encode('ascii', 'ignore').decode('ascii')
	# change spaces
	out = re.sub(" ", "_", out) 
	out = re.sub(r'[^\.\w\d\-]', '', out)
	out = out.lower()
	return out


# filter files by extension
def getValidFileList(fileList, printInvalidFileError = True):
	"""Takes some file list. Checks if these files exists and have appropriate extension."""
	validFileList = [] # (performConvert, originalFilename, newFilename)
	for f in fileList:
		if not os.path.isfile(f):
			print("Error! File " + f + " doesn't exist.")
		found = False
		for ext in supportedFormats:
			if re.search(r'\.' + ext + r'$', f):
				found = True
				newFileName = convertFileName(os.path.basename(f))
				if supportedFormats[ext]: # when perform convert
					newFileName = re.sub(r'\.' + ext + '$', r'.mobi', newFileName)
					performConvert = True
				else:
					performConvert = False
				validFileList.append( (performConvert, os.path.abspath(f), newFileName) )
				break
		if printInvalidFileError and not found:
			print("Warning! File " + f + " has not valid extension. Omitting.")
	return validFileList


def convertFiles(fileList, outputDir):
	"""Takes the list of files, converts them."""
	outputDir = os.path.abspath(outputDir) + "/"
	updateList = []
	for (conversion, name, newName) in fileList:
		if not conversion:
			print('* ' + name)
			shutil.copy(name, outputDir + newName)
			updateList.append(newName)
		else:
			print('* ' + os.path.basename(name) + " > " + newName + "  || Conversion ...") # no newline
			sys.stdout.flush()
			# perform conversion
			# this is configured to use kindlegen provided by Amazon, output to /dev/null
			devNull = open("/dev/null", "w")
			ret = subprocess.call(["ebook-convert", name, outputDir + newName], stdout = devNull, stderr = devNull)
			devNull.close()

			if ret == 0 or ret == 1:
				print("  OK.")
				updateList.append(newName)
			else:
				print("  failed.")
	
	return updateList

def updateFilelist(oldConfig, filesList):		
	# update the changes list
	changes = configparser.RawConfigParser()
	changes.read(oldConfig)
	sectionName = 'Files'
	if not changes.has_section(sectionName):
		changes.add_section(sectionName)

	changes.items(sectionName)

	timestamp = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())

	for i in filesList:
		changes.set(sectionName, i, timestamp)

	with open(oldConfig, 'w') as configfile:
	    changes.write(configfile)


# get command line options
try:
	(options, args) = getopt.gnu_getopt(sys.argv[1:], "pr", ["preserve", "remove"])
except getopt.GetoptError as err:
	print("Error! " + str(err) + ".")
	exit(2)

if len(args) == 0:
	# in this case the files are taken from current directory. 
	fileList = getValidFileList([ f for f in os.listdir(".") if os.path.isfile(f) ], False)
else:
	# in this case files are explicitly specified in command line
	fileList = getValidFileList(args, True)

removeOriginalFiles = False
# check for preserving
for (opt, val) in options:
	if opt in ("-p", "--preserve"):
		removeOriginalFiles = False
		break
	elif opt in ("-r", "--remove"):
		removeOriginalFiles = True
		break

if len(fileList) == 0:
	print("No correct files to send.")
	exit()

tempDir = tempfile.mkdtemp('kindle')

# check if it's possible to download list of changed files
print("Trying to download list of changes...")
ret = subprocess.call(["scp", remotePath + changedFilesList, tempDir])#, stdout = devNull, stderr = devNull)
if ret != 0:
	print("Cannot download " + changedFilesList)
	exit(1)

filesToUpdate = convertFiles(fileList, outputDir = tempDir)

updateFilelist(tempDir + "/" + changedFilesList, filesToUpdate)

filesToUpdate.append(changedFilesList)
filesToUpdate = [ tempDir + "/" + f for f in filesToUpdate ]

# send files to remote server
if not disableSendingChanges:
	print("Trying to send " + str(len(filesToUpdate)) + " files...")
	commandList = ["scp"]
	commandList.extend(filesToUpdate)
	commandList.append(remotePath)
	ret = subprocess.call(commandList)#, stdout = devNull, stderr = devNull)
	if ret == 0:
		print("OK.")
	else:
		print("Error. Preserving " + tempDir + " and original files.")
		exit(1)

shutil.rmtree(tempDir)

if removeOriginalFiles:
	for (c, originalFile, n) in fileList:
		print("Removing " + originalFile)
		os.remove(originalFile)
