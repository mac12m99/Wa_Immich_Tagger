import argparse
import json
import os.path
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import requests

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
    # Connessione ai database WhatsApp
    print('Connecting to ' + args.msgstore)
    conn = sqlite3.connect(args.msgstore)
    cursor = conn.cursor()
    cursor.execute("ATTACH DATABASE '{0}' AS wa".format(args.wa))
    print('Connecting to ' + args.wa)

    print('Executing db query')
    cursor.execute("""
	SELECT message._id, message.timestamp, message_media.file_path, message_media.mime_type, message_media.chat_row_id, 
		COALESCE(chat.subject, chat_contact.display_name, chat_jid.user, chat_jid.raw_string) AS chat_name, jid.user, jid.raw_string AS sender_raw, wa.wa_contacts.display_name AS sender_name, message.text_data
	FROM message_media
	LEFT JOIN chat ON message_media.chat_row_id = chat._id
	LEFT JOIN message ON message_media.message_row_id = message._id
	LEFT JOIN jid ON jid._id = message.sender_jid_row_id
	LEFT JOIN jid_map ON jid_map.lid_row_id = message.sender_jid_row_id
	LEFT JOIN jid AS jid2 ON jid2._id = jid_map.jid_row_id
	LEFT JOIN wa.wa_contacts ON (wa.wa_contacts.jid = jid.raw_string OR wa.wa_contacts.jid = jid2.raw_string)
	LEFT JOIN jid AS chat_jidm ON chat_jid._id = chat.jid_row_id
	LEFT JOIN wa.wa_contacts AS chat_contact ON chat_contact.jid = chat_jid.raw_string
	WHERE
	(
	message_media.file_path LIKE 'Media/WhatsApp Images/%'
	OR message_media.file_path LIKE 'Media/WhatsApp Video/%'
	OR message_media.file_path LIKE 'Media/WhatsApp Business Images/%'
	OR message_media.file_path LIKE 'Media/WhatsApp Business Video/%'
	)
    """)

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'x-api-key': args.api_key
    }
    im_tags = requests.request("GET", args.immich + '/api/tags', headers=headers).json()

    # non-concurrent version for debug purposes
    #for _, timestamp, file_path, _, _, chat_name, _, _, sender_name, text in cursor.fetchall():
    #    job(headers, args.immich, im_tags, timestamp, file_path, chat_name, sender_name, text)

    jobs = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        res = cursor.fetchall()
        print('Returned {0} rows'.format(len(res)))
        for _, timestamp, file_path, _, _, chat_name, _, _, sender_name, text in res:
            jobs.append(executor.submit(job, headers, args.immich, im_tags, timestamp, file_path, chat_name, sender_name, text))
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
    parser.add_argument('-msg', '--msgstore',  default='msgstore.db', help='msgstore.db location, defaults to current folder')
    parser.add_argument('-wa', '--wa', default='wa.db', help='wa.db location, defaults to current folder')
    parser.add_argument('-i', '--immich', help='Immich server url (with http(s) and port)', required=True)
    parser.add_argument('-k', '--api_key', help='Immich api key', required=True)
    parser.add_argument('-w', '--workers', default=50, help='Number of maximum threads')
    args = parser.parse_args()

    main(args)
