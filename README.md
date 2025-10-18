# Wa_Immich_Tagger
A simple script for extracting media info from WhatsApp and pushing that to an Immich instance

## Description
Reads msgstore.db and contact list to obtain chat name, sender name, description (if any) and the original timestamp.\
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
Database | Table   | Field     | Immich
---------|---------|-----------|-------
msgstore.db| message | timestamp |property dateTimeOriginal
msgstore.db| chat    | subject   |Tag WhatsApp/Chat/[Chat name]
msgstore.db| jid     | user      |Tag WhatsApp/Sender/[Contact name] <- phone number if could not find it in contacts
msgstore.db| message | text_data |Asset description

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
Connect your phone to USB and copy this file:
Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db.crypt15

Use wa-crypt-tools to decrypt
```console
wadecrypt your_key msgstore.db.crypt15 msgstore.db
```

## Download
Just run, in a new directory
```console
curl -O https://raw.githubusercontent.com/mac12m99/Wa_Immich_Tagger/refs/heads/main/Wa_Immich_Tagger.py
python -m pip install requests
# if you want this script to also decrypt
python -m pip install wa-crypt-tools
```

## Easy method #1, using ADB (Experimental)
Do an e2e local backup from Whatsapp, connect the phone using usb cable, enable ADB and be sure the device is authorized (run adb devices first).
When you are ready:
```console
python Wa_Immich_Tagger.py -i http://your_install:2283 -k your_api_key -mode adb -e2e your_e2e_key
```

## Easy method #2, using Termux (Experimental)
- Download termux and termux-api from F-Droid (from Play Store it will fail at gaining contacts)
- pkg install python
- See download section, copy paste entire code
- Do an e2e local backup from Whatsapp
- Run
```console
python Wa_Immich_Tagger.py -i http://your_install:2283 -k your_api_key -mode termux -e2e your_e2e_key
```
You will be asked access to contacts and storage, say yes.

## Standard Usage
Place msgstore.db in the same folder for convenience (or add -msg).

Obtain contacts via adb
```console
adb shell content query --uri content://com.android.contacts/data --projection display_name:data1   | grep @s.whatsapp.net > wa_contacts
```
Then:
```console
python Wa_Immich_Tagger.py -i http://your_install:2283 -k your_api_key -c wa_contacts
```
To update you just need to update the db's and re-run the script
