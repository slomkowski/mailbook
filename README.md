mailbook - equivalent for *Send to Kindle* feature with collections support
===========================================================================

**(C) 2013 Michał Słomkowski**
**GNU GPL v.3 license**

If you use *Send to Kindle* feature from Amazon on Kindle DX via Whispernet, you have to pay some cents for each megabyte. So I've written myself a complete free equivalent in Python. Another advantage is that is supports collections. You can type the collection name and the files will be placed accordingly. The software consists of three scripts, which run on:
* Kindle 3 or DX,
* remote shell account with HTTP server and mailbox,
* local computer.

The script for Kindle is mandatory, the other two are optional, although you need at least one of them to send files to Kindle.

**Warning! Using Whispernet in the ways as this script does is against the rules. You might be banned from the further usage of this service. Your library is accessible for the whole world via public HTTP server. The files are not encrypted. You should at least use some random directory name like kindle.r3fesf4re**

Local script
------------

Local scripts gets files from the command line or all files with the valid extension from the current directory. Some formats like *.epub* are not supported by Kindle so conversion is needed. It's done by the script using external converter. You can use *Kindlegen* from Amazon or *ebook-convert* from Calibre. The script is configured to use *ebook-convert* by default. To use Kindlegen you have to edit the script.

The script sends the files to the remote shell account via SSH. You should configure SSH to store keys in order to disable annoying password prompts.

You can specify collection name or, if the collection exists, only partial name. The exact name will be matched. Because of the Kindle limitations, the collections are loaded only at boot time. In order to reload them, you have to reboot Kindle. If you use *-r* parameter, the Kindle will reboot after the update.

To check the exact usage, type:
<code>
$ kindle.py -h
</code>
The script needs Python 3 to run.

Shell account script
--------------------

This script looks for changes in the mailbox directory. When the mail arrives, the subject is checked. It has to have this form:
<code>
kindle[-reboot][: collection name]
</code>
The texts in brackets are optional. If you set reboot flag, the device will reboot after the next update. You can specify collection name too. The changes in the collection will be visible after the reboot. The sender is checked if the sender checking feature is enabled.

The configuration is stored in the file *extract.ini*. The output directory must be accessible via HTTP address.

The script needs Python 3 to run. If you don't want email feature, you don't have to set up this script. However, the shell account with HTTP server is mandatory.

Kindle script
-------------

This script requires Python 2.7 to run. The installation is described here:
http://www.mobileread.com/forums/showthread.php?t=153930

Configuration is stored in the file *libupdate.py*. Script uses Amazon Whispernet to download files. The files go through Amazon proxy. In order to do so, X-FSN key has to be added to each GET request. The X-FSN number is stored in the cookie in the Kindle framework directory. If you get a message of invalid file, you should run Kindle web browser so this file will be created. 

After every update the collections are regenerated to match the directory structure. You can skip update and only regenerate collections using *-g* parameter. The script has some other options, type
<code>
$ ./libupdate.py -h
</code>
to show them.

The most convenient way to run script is by keyboard shortcuts. The script comes with *mailbook.ini* config file with the following hotkeys:
* **Shift U U** - perform update and reboot if the reboot flag was set by the sender and collections have been changed.
* **Shift U G** - regenerate collections only and reboot if changed.
* **Shift U N** - perform update and regenerate collections but don't reboot.

You should copy it to *launchpad* directory in your Kindle dir. Launchpad is a small hotkeys daemon. You can download it here:
http://www.mobileread.com/forums/showthread.php?t=97636


