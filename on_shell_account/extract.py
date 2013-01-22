#!/usr/bin/python3.1
# -*- coding: utf-8 -*-
"""
Script which monitors the Unix mailbox, extracts the messagess with ebook attachements and converts them to .mobi format.

(C) 2012 Michał Słomkowski m.slomkowski@gmail.com

"""

# CONFIG
mailboxPath = '/home/michal/.Mail'
mailSubject = 'kindle'

# formats which will be added to the library. Other files are omitted. The boolean value indicates the need to convert it to the .mobi format.
supportedFormats = {
		# convert
		'epub' : True,
		'html' : True,
		'htm' : True,
		'opf' : True,
		'xhtml' : True,
		# don't convert
		'txt' : False,
		'mobi' : False,
		'azw' : False,
		'azw2' : False,
		'pdf' : False
		}

enableSenderChecking = True
validSenders = ('m.slomkowski@gmail.com', ) # tuple

outputFolder = "### PATH TO YOUR FOLDER WITH BOOKS ###"
changedFilesList = "FILELIST"

# for debug & development
disableConversion = False
disableMailboxClearing = False

# CODE
import mailbox, re, unicodedata, os, configparser, time, subprocess, shutil, tempfile, fcntl, signal

def convertFileName(originalFileName):
	"""Removes spaces and special characters from the file name."""
	# changes languages-specific characters
	out = unicodedata.normalize('NFKD', originalFileName).encode('ascii', 'ignore').decode('ascii')
	# change spaces
	out = re.sub(" ", "_", out) 
	out = re.sub(r'[^\.\w\d\-]', '', out)
	out = out.lower()
	return out


def extractAttachments(message):
	"""Takes Message instance and returns the list of tuples (fileName, fileData)"""
	attachments = []
	for msgPart in message.walk():
		cd = msgPart.get('Content-Disposition', None)
		if cd is None:
			continue

		disps = [elem.strip() for elem in cd.split(';')]
		if disps[0].lower() != 'attachment':
			continue
		
		# get file content
		fileData = msgPart.get_payload(decode = True)
		fileName = ""

		# acquire file name
		for param in disps[1:]:
			(name, value) = param.split("=")
			# file name can be made of several parts, each limited to 40 characters (behavior with Opera)
			if re.search("name", name, re.I): 
				fileName += value

		# if failed to find a file name
		if fileName is None:
			print("Warning! Failed to find a file name for attachment!")
			continue

		fileName = convertFileName(fileName)
		performConversion = False
		addFile = False
		newName = fileName
		
		for extension in supportedFormats:
			if re.search(r'\.' + extension + r'$', fileName):
				addFile = True
				performConversion = supportedFormats[extension]
				if performConversion:
					newName = re.sub(r'\.' + extension + r'$', '.mobi', fileName)
				break
	
		if addFile:
			attachments.append( (fileName, newName, fileData, performConversion) )			
		else:
			print("Warning! File " + fileName + " not added.")

	return attachments


def checkAndGetAttachments():
	"""Checks the mailbox for new deliveries and returns the attachments."""
	# init mailbox
	mb = mailbox.Maildir(mailboxPath)

	# get the messages with valid subject
	messages = [ (key, mb.get(key)) for key in mb.keys() if mb.get(key)['Subject'].strip().lower() == mailSubject.lower() ]
	# TODO add sender recognition

	attachments = []
	for (key, message) in messages:
		attachments.extend(extractAttachments(message))
		# remove the message from the mailbox
		if not disableMailboxClearing:
			mb.remove(key)

	mb.close()

	if len(attachments) == 0:
		return None
	else:
		return attachments


def convertAttachments(attachments):
	"""Takes the list of attachments, converts them and put in a proper directory."""
	filesChanged = []
	temporaryFolder = tempfile.mkdtemp()

	for (name, newName, data, conversion) in attachments:
		if not conversion:
			print('* ' + name)
			f = open(outputFolder + "/" + name, 'wb')
			f.write(data)
			f.close()

			filesChanged.append(name)
		else:
			print('* ' + name + " > " + newName + "  || Conversion ...", end="") # no newline
			tempFilePath = temporaryFolder + "/" + name
			f = open(tempFilePath, 'wb')
			f.write(data)
			f.close()

			# perform conversion
			if not disableConversion:
				# this is configured to use kindlegen provided by Amazon, output to /dev/null
				devNull = open("/dev/null", "w")
				ret = subprocess.call(["./kindlegen", tempFilePath, "-o", newName], stdout = devNull)
				devNull.close()

				if ret == 0 or ret == 1:
					print("OK.")
					shutil.move(temporaryFolder + "/" + newName,  outputFolder + "/" + newName)
					filesChanged.append(newName)
				else:
					print("failed.")

			# remove original file
			os.remove(tempFilePath)
	
	os.rmdir(temporaryFolder)
	if len(filesChanged) == 0:
		return None
	else:
		return filesChanged


def updateFilelist(filesList):		
	# update the changes list
	changes = configparser.RawConfigParser()
	changes.read(outputFolder + "/" + changedFilesList)
	sectionName = 'Files'
	if not changes.has_section(sectionName):
		changes.add_section(sectionName)

	changes.items(sectionName)

	timestamp = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())

	for i in filesList:
		changes.set(sectionName, i, timestamp)

	with open(outputFolder + "/" + changedFilesList, 'w') as configfile:
	    changes.write(configfile)


def updateProcedure():
	attachments = checkAndGetAttachments()
	if attachments is None:
		print("No new files.")
		return
	print(str(len(attachments)) + " new files.")

	changeList = convertAttachments(attachments)
	if changeList is not None:
		updateFilelist(changeList)

# main code
fd = os.open(mailboxPath, os.O_RDONLY)

def handler(signum, frame):
	"""Dummy handler, invokes updateProcedure."""
	updateProcedure()
	fcntl.fcntl(fd, fcntl.F_NOTIFY, fcntl.DN_ACCESS|fcntl.DN_MODIFY|fcntl.DN_CREATE)

fcntl.fcntl(fd, fcntl.F_NOTIFY, fcntl.DN_ACCESS|fcntl.DN_MODIFY|fcntl.DN_CREATE)
signal.signal(signal.SIGIO, handler)

while True:
	signal.pause()

