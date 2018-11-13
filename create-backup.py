"""Create an encrypted .tar.gz archive,
   which can be burned to a cd/dvd or moved somewhere else."""

# TODO Backup Pi?
# TODO Option to restore backup
# TODO Handle missing file errors
# TODO Create MD5sum for unencrypted archive
# TODO Add argument to backup directories, bypass ones defined in config

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

def create_filename(name):
    """Return a filename from input name.
       Use a default if no input is given."""
    if not name:
        date = datetime.datetime.today().strftime('%Y-%m-%d')
        return '/tmp/backup-{}.tar.gz.gpg'.format(date)
    else:
        if os.path.isdir(name):
            date = datetime.datetime.today().strftime('%Y-%m-%d')
            name = name.rstrip('/')
            return '{}/backup-{}.tar.gz.gpg'.format(name, date)
        else:
            return name

def create_config():
    """Create a config file which the user can fill in."""
    config = configparser.ConfigParser()
    config['SETTINGS'] = {}
    config['SETTINGS']['recipients'] = '["user@email.com"]'
    config['SETTINGS']['gnupghome'] = '"/home/user/.gnupg"'
    config['CRITICAL'] = {}
    config['CRITICAL']['directories'] = (
        '[\n'
        '"/home/user/.password-store",\n'
        '"/home/user/.gnupg"\n'
        ']')
    config['IMPORTANT'] = {}
    config['IMPORTANT']['directories'] = (
        '[\n'
        '"/home/user/Pictures",\n'
        '"/home/user/Documents"\n'
        ']')
    config['NON_ESSENTIAL'] = {}
    config['NON_ESSENTIAL']['directories'] = (
        '[\n'
        '"/mnt/hdd/large-files",\n'
        '"/mnt/hdd/movies"\n'
        ']')

    with open('config.cfg', 'w') as f:
        config.write(f)

def read_config(critical, important, nonessential):
    """Read the config file. Return the config values."""
    try:
        config = configparser.ConfigParser()
        config.read('config.cfg')

        directories = []

        if critical:
            directories.extend(json.loads(config.get('CRITICAL',
                                                     'directories')))

        if important:
            directories.extend(json.loads(config.get('IMPORTANT',
                                                     'directories')))

        if nonessential:
            directories.extend(json.loads(config.get('NON_ESSENTIAL',
                                                     'directories')))

        recipients = json.loads(config.get('SETTINGS', 'recipients'))

        gnupghome = json.loads(config.get('SETTINGS', 'gnupghome'))
        if not isinstance(gnupghome, str):
            print('error: gnupghome not set')
            exit(1)

        return directories, recipients, gnupghome
    except json.decoder.JSONDecodeError:
        print('error: config has wrong json format')
        exit(1)
    except configparser.ParsingError:
        print('error: config parsing error')
        exit(1)

def ask_passphrase():
    while True:
        passphrase = getpass.getpass('Passphrase to use: ')
        confirm = getpass.getpass('Re-type your passphrase: ')

        if passphrase == confirm:
            print('Passphrases match.')
            return passphrase
        else:
            print('Passphrases do not match.')

def get_non_existing_directories(directories):
    """Check if list of directories exists. Return directories that
       do not exist."""
    non_existing = []
    for directory in directories:
        if not os.path.exists(directory):
            non_existing.append(directory)

    return non_existing

def get_longest_dir_length(directories):
    longest_dir_length = 0
    for directory in directories:
        if len(directory) > longest_dir_length:
            longest_dir_length = len(directory)

    return longest_dir_length

def check_free_size(filename):
    """Determine if enough space is available for both the unencrypted and
       the encrypted archive. Multiply dir size by 2.5 to
       account for encrypted file with armor."""
    directory = os.path.dirname(os.path.realpath(filename))
    statvfs = os.statvfs(directory)
    if total_size * 2.5 > statvfs.f_frsize * statvfs.f_bavail:
        print('error: not enough free space')
        exit(1)

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
    parser.add_argument(
        '-y', '--yes',
        help="Answer yes to every question",
        action='store_true'
    )
    parser.add_argument(
        '-o', '--output',
        help='Filename to use for the archive.'
             'Default = /tmp/backup-<date>.tar.gz.gpg',
        type=str
    )
    args = parser.parse_args(argv)
    log.basicConfig(format='%(asctime)s %(message)s', level=log.INFO)
    
    filename = create_filename(args.output)

    if not os.path.exists('config.cfg'):
        create_config()
        print("error: No configuration file found. "
              "An example 'config.cfg' has been created.\n"
              "Please fill it with your configuration "
              "settings and then run the script again.")
        exit(0)

    directories, recipients, gnupghome = read_config(args.critical,
                                                     args.important,
                                                     args.nonessential)

    non_existing = get_non_existing_directories(directories)
    if non_existing != []:
        print('error: the following directories do not exist:\n' +
              '\n'.join(non_existing))
        exit(1)

    if os.path.exists(filename) and not args.yes:
        cont = input("File '{}' exists. Overwrite? (y/N) ".format(filename))
        if cont.lower() != 'y':
            print('Aborting.')
            exit(1)

    log.info("Using filename '{}'.".format(filename))

    if args.symmetric:
        passphrase = ask_passphrase()

    total_size = 0
    for directory in directories:
        total_size = total_size + get_size(directory)

    check_free_size(filename)

    log.info('Archiving {} directories with total size of {}.'
             .format(len(directories), sizeof_fmt(total_size)))

    longest_dir_length = get_longest_dir_length(directories)

    with tarfile.open(filename + '.tmp', 'w:gz') as tar:
        for directory in enumerate(directories):
            padding = ' ' * (longest_dir_length - len(directory[1]))
            update_progress_bar(directory[0], len(directories),
                                directory[1] + padding)
            tar.add(directory[1], arcname=os.path.basename(directory[1]))

    update_progress_bar(len(directories), len(directories),
                        ' ' * longest_dir_length)

    archived_size = sizeof_fmt(os.path.getsize(filename + '.tmp'))
    log.info('Archiving complete. Resulting filesize: {}.'
             .format(archived_size))

    gpg = gnupg.GPG(gnupghome=gnupghome)

    log.info('Encrypting archive.')

    with open(filename + '.tmp', 'rb') as f:
        gpg_args = {'recipients': recipients, 'output': filename,
                    'armor': False, 'symmetric': args.symmetric}
        if args.symmetric:
            gpg_args['passphrase'] = passphrase
        
        status = gpg.encrypt_file(f, **gpg_args)

        log.debug('ok:', status.ok)
        log.debug('status:', status.status)
        log.debug('stderr:', status.stderr)

    log.info("Deleting temporary file {}.".format(filename + '.tmp'))
    os.remove(filename + '.tmp')

    encrypted_size = sizeof_fmt(os.path.getsize(filename))
    log.info('Encryption complete. Resulting filesize: {}.'.format(encrypted_size))
    log.info("Backup '{}' complete.".format(filename))

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        print('Interrupted by user.')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0) # pylint: disable=protected-access
