#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Diffs raw crash files taking into account fields that will definitely vary.
#
# Usage: ./bin/diff_raw_crash.py [SOURCEDIR] [DESTDIR] [FILE]

import argparse
import json
import sys


def get_type(filename):
    if 'raw_crash' in filename:
        return 'raw_crash'
    if 'dump_names' in filename:
        return 'dump_names'
    return 'dump'


def is_same(src_filename, dest_filename):
    file_type = get_type(src_filename)

    with open(src_filename, 'rb') as fp:
        src = fp.read()

    with open(dest_filename, 'rb') as fp:
        dest = fp.read()

    if file_type == 'raw_crash':
        src_dict = json.loads(src)
        dest_dict = json.loads(dest)

        # Remove any fields we want to ignore
        for field in ['timestamp', 'submitted_timestamp']:
            if field in src_dict:
                del src_dict[field]
            if field in dest_dict:
                del dest_dict[field]

        if src_dict != dest_dict:
            print('< %s' % src)
            print('---')
            print('> %s' % dest)
            return False

        return True

    if src != dest:
        print('< %s' % src)
        print('---')
        print('> %s' % dest)
        return False
    return True


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('src')
    parser.add_argument('dest')
    args = parser.parse_args(argv)

    if is_same(args.src, args.dest):
        return 0

    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
