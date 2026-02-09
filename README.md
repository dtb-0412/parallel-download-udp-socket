# Parallel UDP socket download
Client download files in parellel chunks from server using UDP socket

### Features
- **Admin** privilege for remote and complete **server** control.
- Supports file permissions. Directories and files on **server** side can be categorized into Whitelist and Blacklist.
- Faster download time. Files are downloaded in parallel threads into 4 separate chunks, which are concatenated into 1 complete file when finished.
- Detailed console log. **Client** automatically retrieves and displays a list of permitted files after connecting to **server**. There is also progress bar to keep track of each file download.

### Setup
1. Install Python 3.x on both machines.
2. Make sure **server** and **client** can communicate with each other on the network (Virtual machine, LAN, VPN, public IP, ...).
3. Configure file permissions on **server** side using the *[Whitelist]* and *[Blacklist]* markdowns in `permissions.txt`.
    -  The markdowns **ARE NOT** case-sensitive. As long as they are put in between `[]`, they will be recognized.
    - The directory and file paths **ARE** case-sensitive, and they must be **RELATIVE** paths from the root data folder on the **server** side (not containing the root folder itself).
        - Example: If all data are put in the *"C:\data\\"* directory, then the `permission.txt` file should be like this:
        ```
        [whitelist]
            Documents
            Videos
        [blacklist]
            Documents\secret_document.pdf
            Videos\Premium
        ```
        
        - With this, all files inside *"C:\data\Documents"* and *"C:\data\Videos"* will be permitted for download, **except** for the file *"secret_document.pdf"* and all files inside *"C:\data\Videos\Premium"*.

4. Run `server.py` on the **server** side.
5. Configure download queue on **client** side in `input.txt`.
6. Run `client.py` on the **client** side.

### Admin
1. Make sure **admin** and **server** can communicate with each other on the network.
2. Run `admin.py` on the **admin** side.

### Admin commands
- `scan`: Server reload file permissions and update file list.
- `log`: Log file permissions and file list on **server** side.
- `term`/`terminate`: Shutdown server.
- `quit`/`exit`: Shutdown admin client.