#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Script which monitors the Unix mailbox, extracts the messagess with ebook attachements and converts them to .mobi format.

(C) 2012 Michał Słomkowski m.slomkowski@gmail.com

"""
# CONFIG

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

metadataFileName = "FILELIST"
configFileName = "extract.ini"

# for debug & development
disableConversion = False
disableMailboxClearing = False

__version__ = '1.1'
__author__ = 'Michał Słomkowski'
__copyright__ = 'GNU GPL v.3.0'

# CODE
import mailbox, re, unicodedata, os, configparser, time, subprocess, shutil, tempfile, fcntl, signal, sys, base64

def convertToFileName(originalFileName):
	"""Removes spaces and special characters from the file name."""
	# changes languages-specific characters
	out = unicodedata.normalize('NFKD', originalFileName).encode('ascii', 'ignore').decode('ascii')
	# change spaces
	out = re.sub(" ", "_", out)
	out = re.sub(r'[^\.\w\d\-]', '', out)
	out = out.lower()
	return out

def getConfiguration(configFile = None):
	"""Looks for configuration file and returns ConfigParser object.
	"""
	CONFIG_PATH = [".", os.path.dirname(__file__)]
	CONFIG_PATH = [os.path.realpath(os.path.join(directory, configFileName)) for directory in CONFIG_PATH]
	if configFile:
		CONFIG_PATH.insert(0, configFile)

	conf = configparser.SafeConfigParser()
	for filePath in CONFIG_PATH:
		try:
			print("Reading configuration from " + filePath)
			conf.readfp(open(filePath))
			configurationLoaded = True
			break
		except IOError:
			configurationLoaded = False

	if not configurationLoaded:
		print >> sys.stderr, ("Error at loading configuration file.")
		sys.exit(1)

	return conf

def extractAttachments(message):
	"""Takes Message instance and returns the list of tuples (fileName, newName, fileData, performConversion)
	"""
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
			# file name can be made of several parts, each limited to 40 characters (Opera mail client behavior)
			if re.search("name", name, re.I):
				fileName += value

		# if failed to find a file name
		if fileName is None:
			print("Warning! Failed to find a file name for attachment!")
			continue

		fileName = convertToFileName(fileName)
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
			attachments.append((fileName, newName, fileData, performConversion))
		else:
			print("Warning! File " + fileName + " not added.")

	return attachments


def checkAndGetAttachments(mailboxPath, validSenders = None):
	"""Checks the mailbox for new deliveries and returns the collWithAttachments. Each email message is checked for proper subject
	and if matches, the collWithAttachments are returned."""

	rebootFlag = False

	# initialize mailbox
	mb = mailbox.Maildir(mailboxPath)

	validSubject = re.compile(r'^\s*(kindle)(?P<reboot_flag>-reboot)?(:\s*(?P<collection>\w+))?\s*$', re.I)
	messages = mb.keys()

	# get the messages with valid subject
	# messages = [ (msg, mb.get(msg)) for msg in mb.keys() if validSubject.match(mb.get(msg)['Subject']) ]
	#messages = filter(lambda msg: validSubject.match(mb.get(msg)['Subject']), mb.keys())
	collWithAttachments = []
	for key in messages:
		msg = mb.get(key)
		sender = re.search(r'<([\w\d\-\.]+@[\w\d\-\.]+)>', msg['From'], re.I).group(1)
		print("Mail from: " + sender)
		match = re.match(r'=\?utf-8\?B\?([\w\d]+)=\?=', msg['Subject'], re.I)
		if match:
		     print(match.group(0))
		     subject = base64.b64decode(match.group(0).encode('ascii'))
		else:
		    subject = msg['Subject']
		print("Subject: " + str(subject))
		if not sender in validSenders:
		     continue
		names = validSubject.search(msg['Subject']).groupdict()

		if names['reboot_flag']:
			rebootFlag = True

		print("Received message from " + sender + "reboot flag: " + str(names['reboot_flag']), end = "")
		if names['collection']:
			collectionName = names['collection']
			print(", collection: " + collectionName)
		else:
			collectionName = ""
			print()

		attachments = extractAttachments(msg)
		if len(attachments) > 0:
			collWithAttachments.append(collectionName, attachments)
		# remove the message from the mailbox
		if not disableMailboxClearing:
			mb.remove(key)

	mb.close()

	return (rebootFlag, collWithAttachments)


def convertAttachments(collectionDirectory, attachments):
	"""Takes the list of attachments, converts them and put in a collection directory."""
	filesChanged = []

	withColl = lambda fileName: collectionDirectory + "_" + fileName
	outputDir = os.path.join(config['DEFAULT']['output_directory'], collectionDirectory)

	temporaryDir = tempfile.mkdtemp()

	# create collection directory if needed
	if not os.path.exists(outputDir):
		os.mkdir(outputDir)

	# 'newName' is the name of the .mobi file
	for (name, newName, data, conversion) in attachments:
		if not conversion:
			print('* ' + name)
			with open(os.path.join(outputDir, name), 'wb') as f:
				f.write(data)

			filesChanged.append(name)
		else:
			print('* ' + name + " > " + newName + "  || Conversion ...", end = "")  # no newline
			tempFilePath = os.path.join(temporaryDir, withColl(name))
			with open(tempFilePath, 'wb') as f:
				f.write(data)

			# perform conversion
			if not disableConversion:
				changeNewName = eval(config['mobi_converter']['output_file'])
				command = re.sub(r'%%OLD_NAME%%', name, config['mobi_converter']['command'])
				command = re.sub(r'%%NEW_NAME%%', changeNewName(os.path.join(outputDir, newName)), command)
				print(command)

				with open("/dev/null", "w") as devNull:
					ret = subprocess.call(command.split(), stdout = devNull, stderr = devNull)

				if ret in map(lambda val: int(val.strip()), config['mobi_converter']['values_success'].split(';')):
					print("OK.")
					shutil.move(os.path.join(temporaryDir, withColl(newName)), os.path.join(outputDir, newName))
					filesChanged.append(newName)
				else:
					print("failed.")

			# remove original file
			os.remove(tempFilePath)

	os.rmdir(temporaryDir)
	return filesChanged

def updateFilelist(collectionName, filesList, updateRebootFlag = False):
	# TODO TODO TODO tylko to zostało
	# update the changes list
	global config

	changes = configparser.SafeConfigParser()
	changes.read(os.path.join(config['DEFAULT']['mailbox_path'], metadataFileName))

	if not changes.has_section(collectionName):
		changes.add_section(collectionName)

	timestamp = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())

	for f in filesList:
		changes.set(sectionName, f, timestamp)

	if updateRebootFlag:
		changes['___SPECIAL___'] = {}
		changes['___SPECIAL___']['RestartTimeStamp'] = timestamp;

	with open(os.path.join(config['DEFAULT']['mailbox_path'], metadataFileName), 'w') as configfile:
	    changes.write(configfile)

def handler(signum, frame):
	"""The handler is called after each change in the mailbox directory. Checks the 
	"""
	global config
	global validSenders

	rebootFlag, collWithAttachments = checkAndGetAttachments(config['DEFAULT']['mailbox_path'], validSenders)
	if len(collWithAttachments) == 0:
		print("No new files.")
		return
	print(str(len(collWithAttachments)) + " new files.")

	for collectionName, attachments in collWithAttachments:
		changeList = convertAttachments(convertToFileName(collectionName), attachments)
		if len(changeList) > 0:
			updateFilelist(collectionName, changeList, rebootFlag)

	if rebootFlag:
		print("Updating reboot flag.")

	fcntl.fcntl(fd, fcntl.F_NOTIFY, fcntl.DN_ACCESS | fcntl.DN_MODIFY | fcntl.DN_CREATE)

# MAIN CODE
print("Mailbook " + __version__ + " " + __author__ + " - mailbox daemon script.")

# read configuration file
config = getConfiguration(sys.argv[1] if len(sys.argv) > 1 else None)

validSenders = None
if config['DEFAULT']['check_senders']:
	 validSenders = map(lambda s: s.strip(), config['DEFAULT']['valid_senders'].split(';'))

fd = os.open(os.path.join(config['DEFAULT']['mailbox_path'], 'new'), os.O_RDONLY)

fcntl.fcntl(fd, fcntl.F_NOTIFY, fcntl.DN_ACCESS | fcntl.DN_MODIFY | fcntl.DN_CREATE)
signal.signal(signal.SIGIO, handler)

while True:
	signal.pause()

