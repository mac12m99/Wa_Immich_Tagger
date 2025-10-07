# Wa_Immich_Tagger
A simple script for extracting media info from WhatsApp and pushing that to an Immich instance

## Description
Reads msgstore.db and wa.db to obtain chat name, sender name, description (if any) and the original timestamp.\
Then, it search if the media has been uploaded (by searching for filename -> if you renamed, you are out of luck) and if so, pushes that info to your Immich instance in the form of Tags, media description and dateTimeOriginal property.

## Prerequisites
- An unecrypted WhatsApp db
- An Immich instance with an API key with at least this permissions:
  - asset.read
  - asset.update
  - tag.create
  - tag.asset
  - tag.read
- Python with requests module installed

## Mapping
Database | Table | Field | Immich
---------|-------|-------|-------
msgstore.db|message|timestamp|property dateTimeOriginal
msgstore.db|chat|subject|Tag WhatsApp/Chat/[Chat name]
wa.db|wa_contacts|display_name|Tag WhatsApp/Sender/[Contact name]
msgstore.db|message|text_data|Asset description

## Obtaining unecrypted WhatsApp db
if you have root just take it from /data/data/com.whatsapp/databases/.

If not, go to Settings -> Chat -> Backup -> end to end backup -> Criptographic key (NOT password)\
Copy the key and save it somewhere.
Download [wa-crypt-tools](https://github.com/ElDavoo/wa-crypt-tools) as it's needed after.
```console
python -m pip install wa-crypt-tools
```

\
Then, everytime you want to use this tool, do a backup and stop right after it started uploading on Drive (it's not needed).\
Connect your phone to USB and copy these files:
```
Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db.crypt15
Android/media/com.whatsapp/WhatsApp/Backups/wa.db.crypt15
```

Use wa-crypt-tools to decrypt the files
```console
wadecrypt your_key wa.db.crypt15 wa.db
wadecrypt your_key msgstore.db.crypt15 msgstore.db
```

## Usage
Download this script
```console
curl -O https://raw.githubusercontent.com/mac12m99/Wa_Immich_Tagger/refs/heads/main/Wa_Immich_Tagger.py
```
Place msgstore.db and wa.db in the same folder for convenience (or add -msg and -wa). 
Then:
```console
python Wa_Immich_Tagger.py -i http://your_install:2283 -k your_api_key
```
To update you just need to update the db's and re-run the script
