"""Create an encrypted .tar.gz archive,
   which can be burned to a cd/dvd or moved somewhere else."""

# TODO Backup Pi?
# TODO Option to restore backup
# TODO Improve input and output, use logging for messages?
# TODO Read directories from .cfg file
# TODO Set recipients in .cfg file
# TODO Set gnupg home in .cfg
# TODO Set output as argument
# TODO Handle missing file errors

import argparse
import sys
import os
import tarfile
import datetime
import gnupg
import getpass
import logging as log
import configparser
import json

def update_progress_bar(current, total, msg=''):
    """Display a progress bar."""
    bar_length = 10
    progress = current / total
    blocks = int(round(bar_length * progress))
    text = '\rProgress: {} {}/{} {:.1f}% {}'\
            .format('▇' * blocks + '-' * (bar_length - blocks),
                    current, total, progress * 100, msg)
    if progress == 1:
        text += '\n'

    sys.stdout.write(text)
    sys.stdout.flush()

def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return '%3.1f %s%s' % (num, unit, suffix)
        num /= 1024.0
    return '%.1f %s%s' % (num, 'Yi', suffix)

def get_size(start_path = '.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size

def main(argv):
    parser = argparse.ArgumentParser(
        description="""Create a backup."""
    )
    parser.add_argument(
        '-c', '--critical',
        help="Create archive containing critical directories",
        action='store_true'
    )
    parser.add_argument(
        '-i', '--important',
        help="Create archive containing important directories",
        action='store_true'
    )
    parser.add_argument(
        '-n', '--nonessential',
        help="Create archive containing non-essential directories",
        action='store_true'
    )
    parser.add_argument(
        '-s', '--symmetric',
        help="Use symmetric encryption",
        action='store_true'
    )
    args = parser.parse_args(argv)
    directories = []
    log.basicConfig(format='%(asctime)s %(message)s', level=log.INFO)
    
    config = configparser.ConfigParser()
    config.read('config.cfg')
    
    if args.critical:
        directories.extend(json.loads(config.get('CRITICAL',
                                                 'directories')))

    if args.important:
        directories.extend(json.loads(config.get('IMPORTANT',
                                                 'directories')))

    if args.nonessential:
        directories.extend(json.loads(config.get('NON_ESSENTIAL',
                                                 'directories')))

    recipients = json.loads(config.get('SETTINGS', 'recipients'))

    gnupghome = json.loads(config.get('SETTINGS', 'gnupghome'))
    if not isinstance(gnupghome, str):
        print('error: gnupghome not set')
        exit(1)

    passphrase = ''
    if args.symmetric:
        valid = False
        while not valid:
            passphrase = getpass.getpass('Passphrase to use: ')
            confirm = getpass.getpass('Re-type your passphrase: ')

            if passphrase == confirm:
                valid = True
                print('Passphrases match.')
            else:
                print('Passphrases do not match.')

    date = datetime.datetime.today().strftime('%Y-%m-%d')
    filename = '/tmp/backup-{}.tar.gz'.format(date)
    longest_dir_length = 0
    total_size = 0
    for directory in directories:
        total_size = total_size + get_size(directory)
        if len(directory) > longest_dir_length:
            longest_dir_length = len(directory)

    print('Archiving {} directories with total size of {}.'
          .format(len(directories), sizeof_fmt(total_size)))

    with tarfile.open(filename, 'w:gz') as tar:
        for directory in enumerate(directories):
            padding = ' ' * (longest_dir_length - len(directory[1]))
            update_progress_bar(directory[0], len(directories),
                                directory[1] + padding)
            tar.add(directory[1], arcname=os.path.basename(directory[1]))

    update_progress_bar(len(directories), len(directories),
                        ' ' * longest_dir_length)

    archived_size = sizeof_fmt(os.path.getsize(filename))
    log.info('Archiving complete. Resulting filesize: {}.'
             .format(archived_size))

    gpg = gnupg.GPG(gnupghome=gnupghome)

    log.info('Encrypting archive.')

    with open(filename, 'rb') as f:
        filename = filename + '.gpg'
        status = gpg.encrypt_file(f, recipients=recipients, output=filename, armor=False, symmetric=args.symmetric, passphrase=passphrase)

    # TODO Handle errors

    print('ok:', status.ok)
    print('status:', status.status)
    print('stderr:', status.stderr)

    encrypted_size = sizeof_fmt(os.path.getsize(filename))
    log.info('Encryption complete. Resulting filesize: {}.'.format(encrypted_size))
    print("Backup '{}' complete.".format(filename))

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        print('Interrupted by user.')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0) # pylint: disable=protected-access
