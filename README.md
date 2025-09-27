# Wa_Immich_Tagger
A simple script for extracting media info from WhatsApp and pushing that to an Immich instance

## Description
Reads msgstore.db and wa.db to obtain chat name, sender name, description (if any) and the original timestamp.\
Then, it search if the media has been uploaded (by searching for filename -> if you renamed, you are out of luck) and if so, pushes that info to your Immich instance in the form of Tags, media description and dateTimeOriginal property.

## Prerequisites
- An undecrypted WhatsApp db
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

## Usage
Download this script
```console
curl -O https://raw.githubusercontent.com/mac12m99/Wa_Immich_Tagger/refs/heads/main/Wa_Immich_Tagger.py
```
Obtain an undecrypted db in some way (if you have root just take it from /data/data/com.whatsapp/databases/) and place in the same folder for convenience. 
Then:
```console
python Wa_Immich_Tagger.py -i http://your_install:2283 -k your_api_key
```
To update you just need to update the db's and re-run the script