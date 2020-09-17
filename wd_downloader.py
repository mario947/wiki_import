#!/bin/python3

import argparse
import sys
import json
import os
import sys
from datetime import date
from datetime import timedelta

from subprocess import call
from urllib.request import urlopen
from urllib.error import URLError

THIS_DIR = os.path.abspath(os.path.dirname(__file__))
if not THIS_DIR: THIS_DIR = './'
if not THIS_DIR.endswith('/'): THIS_DIR = THIS_DIR + '/'
sys.path.append(THIS_DIR)

import wd_updater as Updater

MAXREVID = '/maxrevid.txt'

BASE_URL = 'https://dumps.wikimedia.org/other/incr/wikidatawiki/'
STATUS_URL = BASE_URL + '%s/status.txt'
MAXREVID_URL = BASE_URL + '%s/maxrevid.txt'
DUMP_URL = BASE_URL + '%s/wikidatawiki-%s-pages-meta-hist-incr.xml.bz2'

MAXREVID_FILE = '/wikidatawiki-%s-maxrevid.txt'
DUMP_FILE = '/wikidatawiki-%s-pages-meta-hist-incr.xml.bz2'

STATUS_DONE = 'done:all'

def read_url_resource(url):
    result = ''
    try:
        response = urlopen(url)
        response_content = response.read()
        result = response_content.decode('utf-8')
    except URLError as err:
        pass
    except UnicodeEncodeError as err:
        print(url, '- ERROR', err, file=sys.stderr)
    return result


def download(version, dump_path):
    # save revision id for the future in case dump have to be reloaded
    file_path = dump_path + MAXREVID_FILE % version
    if not os.path.isfile(file_path):
        params = ['wget', '-c', '-O', file_path, MAXREVID_URL % version]
        call(params)
    else:
        print('File %s already exists, skip downloading' % file_path)

    file_path = dump_path + DUMP_FILE % version
    if not os.path.isfile(file_path):
        params = ['wget', '-c', '-O', file_path, DUMP_URL % (version, version)]
        call(params)
    else:
        print('File %s already exists, skip downloading' % file_path)


def update(version, dump_path, conn_str, schema):
    if not conn_str or len(conn_str) == 0:
        return

    file_path = dump_path + DUMP_FILE % version
    conn, cursor = Updater.setup_db(conn_str)
    Updater.parse(file_path, dump_path, conn, cursor, schema)
    conn.commit()


def main(max_days, max_rev_id, dump_path, conn_str, schema):
    print('Loading dumps for', max_days, 'days', max_rev_id, dump_path)

    day = timedelta(days=1)
    start_date = date.today() - timedelta(days=max_days)
    today = date.today()
    while start_date <= today:
        # check dump status (if it exists and is ready)
        date_str = start_date.strftime('%Y%m%d')

        status = read_url_resource(STATUS_URL % date_str)
        if status.strip() == STATUS_DONE:
            # check if this dump has any updates
            rev_id = int(read_url_resource(MAXREVID_URL % date_str))
            if rev_id > max_rev_id:
                # download dump
                download(date_str, dump_path)

                # parse and load dump into DB
                update(date_str, dump_path, conn_str, schema)

                max_rev_id = rev_id
            else:
                print('Skip %s dump as DB already contains that revision' % date_str)

        start_date += day

    return max_rev_id



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download wikidata incremental dump into specfied location')
    parser.add_argument('max_days', type=int, help='Max days to load dumps for. Usually not more than 15 are available')
    parser.add_argument('dump_path', type=str, help='Location where to save BZipped wikipedia dumps')
    parser.add_argument('postgres', type=str, help='postgres connection string')
    parser.add_argument('schema', type=str, help='DB schema containing wikidata tables')

    args = parser.parse_args()

    max_rev_id = 0
    if os.path.isfile(args.dump_path + MAXREVID):
        with open(args.dump_path + MAXREVID, 'r') as f:
            max_rev_id = int(f.read())


    max_rev_id = main(args.max_days, max_rev_id, args.dump_path, args.postgres, args.schema)

    with open(args.dump_path + MAXREVID, 'w') as f:
        f.write(str(max_rev_id))



