#!/bin/sh

# Code run on Kindle to update the library from remote server.
# (C) Michał Słomkowski 2012 m.slomkowski@gmail.com

TEST=0

if [ $TEST -eq 0 ]
then
	COMPARER="filelist-arm"
	SCRIPTDIR='/mnt/us/mailbook'
else
	COMPARER="filelist"
	SCRIPTDIR=.
fi

#XFSN=`cat $SCRIPTDIR/x-fsn.txt`
XFSN=`cat '/var/local/java/prefs/cookies/Cookie__x-fsn_WITH_DOMAIN__$$cookie.store.domains.cookie' | head -n 1 | cut -d '=' -f 2`
USER_AGENT='Mozilla/4.0 (compatible; Linux 2.6.22) NetFront/3.4 Kindle/2.5 (screen 824x1200; rotate)'

export http_proxy='fints-g7g.amazon.com:80'

LOCAL_LIBRARY='/mnt/us/documents/mailbook'
REMOTE_LIBRARY=`cat $SCRIPTDIR/remote_library_address`

NEW_FILELIST=`mktemp /tmp/mailbook-list_of_files.XXXXXX`
OLD_FILELIST="$LOCAL_LIBRARY/list_of_files"

echo "Kindle MailBook - replacement for Amazon Send to Kindle"
echo "(C) 2012 Michal Slomkowski m.slomkowski@gmail.com"
echo

# creates the local filelist if it's not present, it doesn't hurt otherwise
touch $OLD_FILELIST

# get current filelist 
$SCRIPTDIR/wget-arm --header="x-fsn: $XFSN" --user-agent="$USER_AGENT" --proxy=on "$REMOTE_LIBRARY/FILELIST" -O "$NEW_FILELIST"

# check if success
if [ $? -ne 0 ]
then
	echo "Error with connection!"
	rm $NEW_FILELIST
	exit 1
fi

FILES_TO_DOWNLOAD=`$SCRIPTDIR/$COMPARER $NEW_FILELIST $OLD_FILELIST`

rm $OLD_FILELIST
mv $NEW_FILELIST $OLD_FILELIST

if [ $? -ne 0 ]
then
	echo "Error with filelist comparing!"
	exit 1
fi

COUNT=`echo $FILES_TO_DOWNLOAD | wc -w`
if [ $COUNT -ne 0 ]
then
	echo "Downloading $COUNT files..."
fi

for file in $FILES_TO_DOWNLOAD
do
	$SCRIPTDIR/wget-arm --header="x-fsn: $XFSN" --user-agent="$USER_AGENT" --proxy=on "$REMOTE_LIBRARY/$file" -O "$LOCAL_LIBRARY/$file"
done

# refresh documents index
#if [ "$TEST" -eq "0" ]
#then
#	if [ "$COUNT" -ne "0" ]
#	then
#		dbus-send --system /default com.lab126.powerd.resuming int32:1
#	else
#		echo "No new documents."
#	fi
#fi

dbus-send --system /default com.lab126.powerd.resuming int32:1


