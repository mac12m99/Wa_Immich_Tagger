import argparse
import json
import os.path
import sqlite3
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import requests
import re

msgstore_backup_location = '/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db.crypt15'

def job(headers, immich_url, im_tags, timestamp, file_path, chat_name, sender_name, text):
    # searching if whatsapp media exists and obtain id
    payload = json.dumps({
        "originalFileName": os.path.basename(file_path)
    })
    ret = requests.request("POST", immich_url + '/api/search/metadata', headers=headers, data=payload).json()
    items = ret.get('assets', {}).get('items', [])
    if len(items) > 0:
        asset_id = items[0].get('id')

        # check if it's already processed (has WhatsApp tags)
        ret = requests.request("GET", immich_url + '/api/assets/' + asset_id, headers=headers).json()
        for t in ret.get('tags', []):
            if t.get('value').startswith('WhatsApp'):
                # already processed
                return False

        # tags creation/selection
        tag_name = "WhatsApp/Chat/" + chat_name.replace('/', ' ')
        for t in im_tags:
            if t.get('value') == tag_name:  # already there
                tag_chat = t.get('id')
                break
        else:
            payload = json.dumps({
                "color": "#59CE72",
                "name": tag_name
            })
            tag_chat = requests.request("POST", immich_url + '/api/tags', headers=headers, data=payload).json().get(
                'id')

        if not sender_name: # if empty it's you
            sender_name = 'Me'
        tag_name = "WhatsApp/Sender/" + sender_name.replace('/', ' ')
        for t in im_tags:
            if t.get('value') == tag_name:  # already there
                tag_sender = t.get('id')
                break
        else:
            payload = json.dumps({
                "color": "#59CE72",
                "name": tag_name
            })
            tag_sender = requests.request("POST", immich_url + '/api/tags', headers=headers, data=payload).json().get(
                'id')

        # tag assignment
        payload = json.dumps({
            "assetIds": [
                asset_id
            ],
            "tagIds": [
                tag_chat, tag_sender
            ]
        })
        requests.request("PUT", immich_url + '/api/tags/assets', headers=headers, data=payload)

        # real datetime and description
        payload = {
            "dateTimeOriginal": datetime.fromtimestamp(timestamp / 1000).astimezone().isoformat(),
            "ids": [
                asset_id
            ]
        }
        if text:
            payload["description"] = text
        requests.request("PUT", immich_url + '/api/assets', headers=headers, data=json.dumps(payload))
        # Tagged successfully
        return True
    else:
        # not found
        return None

def main(args):
    contacts = {}

    if args.mode == 'adb':
        print('Pulling msgstore backup from adb..')
        subprocess.run(
            ['adb', 'pull', msgstore_backup_location, 'msgstore.db.crypt15'])
        args.msgstore = 'msgstore.db.crypt15'

        contacts = subprocess.run(['adb', 'shell', 'content', 'query', '--uri', 'content://com.android.contacts/data', '--projection', 'display_name:data1',
                       '|', 'grep', '@s.whatsapp.net'], stdout=subprocess.PIPE)
        args.contacts = 'wa_contacts'
        open(args.contacts, 'wb').write(contacts.stdout)

    if args.mode == 'termux':
        import json
        args.msgstore = msgstore_backup_location
        subprocess.run(['pkg', 'install', 'termux-api'])
        termux_contacts = json.loads(subprocess.run(['termux-contacts-list'], stdout=subprocess.PIPE).stdout)
        contacts = {c['number'][1:]: c['name'] for c in termux_contacts}

    # handle encrypted msgstore backup (with e2e)
    if args.msgstore.endswith('.crypt15'):
        if not args.e2e_key:
            print('Detected crypted msgstore, e2e parameter needed')
            exit()
        from wa_crypt_tools.lib.db.dbfactory import DatabaseFactory
        from wa_crypt_tools.lib.key.keyfactory import KeyFactory
        import zlib

        msg = open(args.msgstore, 'rb')
        db = DatabaseFactory.from_file(msg)
        key = KeyFactory.new(args.e2e_key)
        output_decrypted: bytearray = db.decrypt(key, msg.read())
        z_obj = zlib.decompressobj()
        output_file = z_obj.decompress(output_decrypted)
        args.msgstore = 'msgstore.db'
        open(args.msgstore, 'wb').write(output_file)

    print('Connecting to ' + args.msgstore)
    conn = sqlite3.connect(args.msgstore)
    cursor = conn.cursor()

    print('Executing db query')
    cursor.execute("""
    SELECT message._id, message.timestamp, message_media.file_path, message_media.mime_type,
           message_media.chat_row_id,  chat.subject, ifnull(jid2.user, jid.user) as Sender, message.text_data
    FROM message_media
    LEFT JOIN chat ON message_media.chat_row_id = chat._id
    LEFT JOIN message on message_media.message_row_id = message._id
    LEFT JOIN jid on jid._id = message.sender_jid_row_id
    --sometimes real id is stored in jid_map...
	LEFT JOIN jid_map on jid_map.lid_row_id = message.sender_jid_row_id
	LEFT JOIN jid as jid2 on jid2._id = jid_map.jid_row_id
    WHERE  (message_media.file_path like 'Media/WhatsApp Images/%' or message_media.file_path like 'Media/WhatsApp Video/%') and chat.subject is not NULL
    union all
    --chat with contacts
    SELECT message._id, message.timestamp, message_media.file_path, message_media.mime_type,
           message_media.chat_row_id,  null, jid.user as Sender, message.text_data
    FROM message_media
    LEFT JOIN chat ON message_media.chat_row_id = chat._id
    LEFT JOIN message on message_media.message_row_id = message._id
    LEFT JOIN jid on jid._id = chat.jid_row_id
    WHERE  (message_media.file_path like 'Media/WhatsApp Images/%' or message_media.file_path like 'Media/WhatsApp Video/%') and chat.subject is NULL
    """)

    res = cursor.fetchall()
    print('Returned {0} rows'.format(len(res)))

    if args.contacts:
        print('Reading ' + args.contacts)
        for name, number in re.findall("display_name=([^,]+), data1=([^@]+)", open(args.contacts, 'r').read()):
            contacts[number] = name
        print('Loaded {0} contacts'.format(len(contacts)))

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'x-api-key': args.api_key
    }
    im_tags = requests.request("GET", args.immich + '/api/tags', headers=headers).json()

    # non-concurrent version for debug purposes
    #for _, timestamp, file_path, _, _, chat_name, sender, text in cursor.fetchall():
    #    job(headers, args.immich, im_tags, timestamp, file_path, chat_name, sender_name, text)

    jobs = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for _, timestamp, file_path, _, _, chat_name, sender, text in res:
            if not chat_name: #if null it's a single person chat, its name is the contact name
                chat_name = contacts.get(sender, sender)
            sender = contacts.get(sender, sender)
            jobs.append(executor.submit(job, headers, args.immich, im_tags, timestamp, file_path, chat_name, sender, text))
        conn.close()

        not_found = 0
        tagged = 0
        skipped = 0
        for future in as_completed(jobs):
            res = future.result()
            if res is None:
                not_found += 1
            elif res:
                tagged += 1
            else:
                skipped += 1
            print('Tagged: {0} - Skipped: {1} - Not found: {2}'.format(tagged, skipped, not_found), end='\r')
    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='Wa_Immich_Tagger.py',
        description='Connect to WhatsApp database, extract info about its media (chats name, sender, timestamp and description) and push that to Immich',
        epilog='You need root access for now, or an undecrypted backup')
    parser.add_argument('-mode', '--mode',  help='adb=pulls e2e backup and contacts from adb, termux=you are running this script directly on your phone using termux')
    parser.add_argument('-msg', '--msgstore',  default='msgstore.db', help='msgstore.db[.crypt15] location, defaults to current folder')
    parser.add_argument('-e2e', '--e2e_key', help='If you have encrypted msgstore.db with e2e encryption, insert the key here')
    parser.add_argument('-c', '--contacts', help='contacts adb export location, not needed using modes')
    parser.add_argument('-i', '--immich', help='Immich server url (with http(s) and port)', required=True)
    parser.add_argument('-k', '--api_key', help='Immich api key', required=True)
    parser.add_argument('-w', '--workers', default=50, help='Number of maximum threads')
    args = parser.parse_args()

    main(args)