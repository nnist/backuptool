# backuptool
Create encrypted .tar.gz archives.

## Requirements
- Python 3.5+
- python-gnupg

## Functionality
- Create .tar.gz archives encrypted with GPG.
- Use symmetric or asymmetric encryption.
- Backup directories defined in a config file.

## Usage
1. Clone the repository.
2. Run `python create-backup.py` to create a new config file:
    ```cfg
    [SETTINGS]
    recipients = ["user@email.com"]
    gnupghome = "/home/user/.gnupg"
    
    [CRITICAL]
    directories = [
    	"/home/user/.password-store",
    	"/home/user/.gnupg"
    	]
    
    [IMPORTANT]
    directories = [
    	"/home/user/Pictures",
    	"/home/user/Documents"
    	]
    
    [NON_ESSENTIAL]
    directories = [
    	"/mnt/hdd/large-files",
    	"/mnt/hdd/movies"
    	]
    ```
3. Edit the values for your own use.

    Put your GPG email in the recipients field.

    There are three levels, critical, important and non-essential.
    - Critical is meant for files that absolutely cannot be missed,
      such as passwords. Mostly small files.
    - Important is for non-critical but still important and irreplaceable files,
      such as documents, pictures, etc.
    - Non-essential is meant for things that can be retrieved in some way,
      like movies, music, books, and downloads. Mostly large files.

4. Run `python create-backup.py` and supply the arguments you need.
    Example:
    - `python create-backup.py -c` would create backup file
      `/tmp/backup-<date>.tar.gz.gpg`, containing only critical files.
    - `python create-backup.py -c -i -n` would create a backup file containing
      critical, important and non-essential files.
    - `python create-backup.py -c --symmetric` creates a backup file using
      symmetric encryption. You will be asked to choose a password.
