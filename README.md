# Night Tech Hub

The shop's home base for **Night Tech Solutions**: customers, tickets, devices, a chain-of-custody log,
a file library and a wiki. It prints your Certificate of Data Wipe, the Computer Drop-Off and Donation
Release, drop-off and pick-up receipts, and ticket labels with barcodes, already filled in from the ticket.

It runs on your own computer. Your data stays with you.

## What you need
- A Windows, Mac or Linux computer that stays on during shop hours
- Python 3.10 or newer (free). On Windows, download it from https://www.python.org/downloads/ and tick **Add Python to PATH**

## Windows installer (recommended for the shop PC)

`NightTechHub-Setup.exe` installs the Hub like a normal Windows program. The PC doesn't need Python.

**Build the installer (once per version, on any Windows PC):**
1. Install Python 3.10+ from https://www.python.org/downloads/ (tick **Add Python to PATH**).
2. Install Inno Setup 6 from https://jrsoftware.org/isdl.php (or run `winget install JRSoftware.InnoSetup`).
3. In this folder, right-click `build.ps1` and choose **Run with PowerShell**, or run:
   `powershell -ExecutionPolicy Bypass -File .\build.ps1`
4. The installer appears in `installer\Output\NightTechHub-Setup.exe`, with a SHA-256 checksum file next to it.

**What the installer does:**
- Installs for the current Windows user. No admin rights needed.
- Adds **Night Tech Hub** to the Start Menu (plus a desktop shortcut if you tick the box), and a shortcut to the data folder.
- Opening the shortcut starts the Hub and opens it in your browser. If it's already running, it just opens the browser.
- Keeps your data in `%LOCALAPPDATA%\Night Tech Hub\data`, outside the program folder. Updating or uninstalling never deletes it.

**Updating:** change `AppVersion` in `installer\NightTechHub.iss`, run `build.ps1` again, and run the new installer over the old one.

**Already used the Hub with start.bat?** Close the Hub, then copy everything inside your old `data` folder into
`%LOCALAPPDATA%\Night Tech Hub\data` (paste that path into File Explorer's address bar) before starting the installed version.

**Windows warnings:** the installer isn't code-signed yet, so Windows SmartScreen may say "Windows protected your PC."
Click **More info, then Run anyway**. Code signing (for example Azure Trusted Signing) removes this later.

## Start it (without the installer)
- **Windows:** double-click `start.bat`
- **Mac or Linux:** run `./start.sh`

The first start takes a minute (it installs three small helper packages). Then your browser opens at
http://127.0.0.1:5000. Leave the black window open while you work. Close it to stop the Hub.

## First time
1. Create the owner account (use a long password you don't use anywhere else).
2. Open **Team** (in the menu, owners only) and **Add a person** to give Carin her own login. Use "Suggest a strong password", write it down for her, and ask her to change it in Settings after she signs in. Staff can use tickets, customers, files, forms and the wiki. Only owners see Team, backups, exports and shop settings.
3. Read the **Wiki > Start here** page. The procedure pages are templates. Fill in the blanks (especially
   the wipe methods you really use and your recycler's details).

## Forms and receipts
The **Forms** page prints every form blank, or filled in automatically from a ticket:
- **Drop-Off Receipt** (customer copy and shop copy, or customer copy only to text or email)
- **Pick-Up Receipt** (signed when the customer collects their items)
- **Computer Drop-Off and Donation Release**
- **Certificate of Data Wipe**

The same buttons are at the top of every ticket. Each print is added to the ticket's chain-of-custody log.
For porch drop-offs, create the ticket when you collect the device and send the customer their **customer copy**.

## A normal job
1. **+ New ticket**: pick or add the customer, the service, and add every device. Don't type passcodes.
2. Open the ticket. **Print label** and put it on the device. Record where it's stored.
3. Change the status as you go. Add notes, parts, time and photos.
4. Old-computer drop-offs: **Drop-off release** prints the form for the customer to sign. Set each computer's
   outcome (Refurbish, Parts, Drive removed, Recycled) on the ticket.
5. Wipes: fill in the **Wipe record**, then **Wipe certificate** prints one page per device.
6. Take payment in **Square** (the Hub keeps your Square invoice link and quote on the ticket).

Everything that changes on a ticket is added to the **Chain of custody** log. It can't be edited.

## Mailing list
Website signups (the "Tech Tips & Deals" form) arrive in your business email from Formspree. Keep one clean list here:
- **Mailing list** (button on the Customers page, and a link on the dashboard): add one person, paste several at once, or (owner) import a CSV with an Email column.
- Each subscriber has **topics** (Deals and discounts, Tech news and tips, Monthly newsletter), so you can send deals only to people who asked for deals. Website signups tell you which boxes they ticked. Anyone added without a choice gets all three.
- Every person is saved with **how and when they agreed**. Nobody can be added without confirming consent.
- **Unsubscribe** the moment someone asks. Unsubscribed people stay on file so imports and pastes never add them back by accident. Only the owner can re-subscribe someone, and only at their request.
- **Export active subscribers (CSV)** (owner) gives you a file to upload to an email service such as MailerLite, Mailchimp or Buttondown, which also handle the unsubscribe link and your postal address in each email.
- On a customer's page, **Add to mailing list** opens the form filled in (it still needs the consent box).

## Settings (owner)
- **Shop details:** name, phone, email, website, service area and hours. These print on every receipt, certificate, release and label.
- **Services and storage locations:** edit the service dropdown and the list of shelves and bins. Old tickets are never changed.
- **Receipt wording:** the notes at the bottom of the drop-off receipt. Use `{phone}` to insert your phone number.
- **Backups and exports**, and **your password**.

## Backups (please do this)
Settings > **Download backup** saves the database and every file in one zip. Do it weekly and keep a copy
somewhere that isn't this computer (a USB drive or a private cloud folder). Turn on disk encryption
(BitLocker on Windows, FileVault on Mac) because this computer will hold customer information.

## Using it from your phone or Carin's computer
By default the Hub only answers on the computer it runs on. That is the safest setting.
To reach it from other devices, use a private network such as **Tailscale** (free for small use), then start with:
- Windows: `set NTHUB_HOST=0.0.0.0` then `python run.py` (inside the `.venv`)
- Mac/Linux: `NTHUB_HOST=0.0.0.0 ./start.sh`

**Never open the Hub to the public internet.** If you ever run it behind HTTPS, set `NTHUB_SECURE_COOKIES=1`.

## Security built in
Passwords are stored hashed. Accounts lock for 15 minutes after 5 wrong tries. Forms are protected against
forged requests. Uploads allow only safe file types and are checked. Pages can't run outside scripts. Only the
owner can download backups, export data, delete files or manage people.

## What it does not do (on purpose)
- **Take payments.** Square does that safely.
- **Send texts or emails.** Use Google Voice and Gmail. The Hub shows who is OK to text.
- **Store passwords or passcodes.** Use a password manager. Never put them in notes.

## Where things are
- `data/hub.db` the database, `data/uploads/` your files, `data/secret.key` the session key. All three are in the backup (the key isn't needed to restore).
- `db.py` holds your shop details, service list, statuses and the starter wiki pages. Edit it to change them.
- `static/style.css` holds the brand colors.

## Updating or moving
- **Moving to a new computer:** copy the whole `nighttech-hub` folder (including `data`) and start it there.
- **Installing a newer version:** replace the program files with the new ones but **keep your `data` folder**. Your customers, tickets and settings carry over automatically.

## GitHub builds and releases

Every push to `main` runs the smoke tests (`python -m unittest discover -s tests -v`) and builds
`NightTechHub-Setup.exe` on GitHub's Windows machines (Actions tab, download the artifact).
Publishing a Release on GitHub (Releases, Draft a new release, tag such as `v1.0.1`) builds the installer and attaches it with its SHA-256 file. From the command line:

```
gh release create v1.0.1 --title "Night Tech Hub 1.0.1" --notes "What changed"
```

Keep this repository **private**: it's the shop's own software. Customer data is never in the repository
(the `data` folder is ignored).
