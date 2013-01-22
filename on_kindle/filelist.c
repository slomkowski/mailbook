/*
 * filelist
 * This small program gets the content of two lists, compares them and returns the items to download.
 * (C) 2012 Michał Słomkowski m.slomkowski@gmail.com
 */

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <string.h>

typedef struct
{
	char filename[300];
	long datestamp;
} ENTRY;

typedef struct
{
	int noFiles;
	ENTRY *entries;
} FILELIST;

#define LINELEN 500
FILELIST *getFiles(FILE *stream)
{
	char line[LINELEN], tempDate[100];
	int filesCounter = 0, i, j;
	ENTRY currEntry;
	FILELIST *out = calloc(1, sizeof(FILELIST));
	fpos_t startPos;
	int dateTab[6];

	// take first line, which should be '[Files]'
	fgets(line, LINELEN, stream);
	fgetpos(stream, &startPos);
	
	if(!strcmp(line, "[Files]"))
	{
		out->noFiles = 0;
		out->entries = NULL;
		return out;
	}

	while(!feof(stream))
	{
		fgets(line, LINELEN, stream);
		if(strchr(line, '=') == NULL) break;
		filesCounter++;
	}

	out->noFiles = filesCounter;
	out->entries = calloc(filesCounter, sizeof(ENTRY)); // space for n files

	fsetpos(stream, &startPos);	

	for(i = 0; i < filesCounter; i++)
	{
		fscanf(stream, "%s = %s", currEntry.filename, tempDate);
		
		sscanf(tempDate, "%d-%d-%d_%d:%d:%d", &dateTab[0], &dateTab[1], &dateTab[2], &dateTab[3], &dateTab[4], &dateTab[5]);
		currEntry.datestamp = 0;
		for(j = 0; j < 6; j++) currEntry.datestamp = 100 * currEntry.datestamp + dateTab[j];

		memcpy(&(out->entries[i]), &currEntry, sizeof(ENTRY));
	}

	return out;
}

int main(int argc, char *argv[])
{
	FILE *newFile, *oldFile;
	FILELIST *new, *old;
	int i, j;
	int found, updated;

	if(argc < 2)
	{
		fprintf(stderr, "Usage: \n%s new_filelist old_filelist\n", argv[0]);
		return 1;
	}

	newFile = fopen(argv[1], "r");
	oldFile = fopen(argv[2], "r");

	if((newFile == NULL) || (oldFile == NULL))
	{
		fprintf(stderr, "Could not open at least one of the input files!\n");
		return 1;
	}
	
	new = getFiles(newFile);
	old = getFiles(oldFile);

	fclose(newFile);
	fclose(oldFile);

	// compare lists
	//for(i = 0; i < new->noFiles; i++) printf("%s %u\n", new->entries[i].filename, new->entries[i].datestamp);
	//printf("old:\n");
	//for(i = 0; i < old->noFiles; i++) printf("%s %u\n", old->entries[i].filename, old->entries[i].datestamp);
	// compare
	for(i = 0; i < new->noFiles; i++)
	{
		found = 0;
		updated = 0;

		for(j = 0; j < old->noFiles; j++)
		{
			if(!strcmp(old->entries[j].filename, new->entries[i].filename)) // if the file is already in the library, check the date
			{
				found = 1;

				// check date
				if(old->entries[j].datestamp == new->entries[i].datestamp) // the file wasn't updated
					updated = 0;
				else updated = 1;

				break;
			}
		}

		if(found && !updated) strcpy(new->entries[i].filename, ""); // remove them from the list to download
	}
	for(i = 0; i < new->noFiles; i++) if(strlen(new->entries[i].filename) > 0) printf("%s ", new->entries[i].filename);

	free(new);
	free(old);

	return 0;
}
