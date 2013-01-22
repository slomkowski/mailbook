CC-ARM=/home/michal/Kindle/scratchbox/compilers/cs2007q3-glibc2.5-arm6/bin/arm-none-linux-gnueabi-gcc

all: filelist filelist-arm

filelist : filelist.c
	$(CC) filelist.c -o filelist

filelist-arm : filelist.c
	$(CC-ARM) filelist.c -o filelist-arm

