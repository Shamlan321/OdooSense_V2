import imaplib
import email
from email.header import decode_header
import time
import os

# ----------- Configuration -----------
IMAP_SERVER = "imap.hostinger.com"     # e.g., imap.gmail.com
EMAIL_ACCOUNT = "support@mocxha.com"
EMAIL_PASSWORD = "@Mocxha123"
CHECK_INTERVAL = 10  # seconds between checks

# Folder to save attachments
ATTACHMENT_DIR = "attachments"
os.makedirs(ATTACHMENT_DIR, exist_ok=True)

# ----------- Email Processing -----------

def process_email(msg):
    subject, encoding = decode_header(msg["Subject"])[0]
    if isinstance(subject, bytes):
        subject = subject.decode(encoding or "utf-8", errors="ignore")
    print(f"📥 New Email: {subject}")

    # Print From
    from_ = msg.get("From")
    print(f"👤 From: {from_}")

    # Download attachments
    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        if part.get_content_maintype() == 'multipart':
            continue
        if "attachment" in content_disposition:
            filename = part.get_filename()
            if filename:
                decoded_filename, enc = decode_header(filename)[0]
                if isinstance(decoded_filename, bytes):
                    decoded_filename = decoded_filename.decode(enc or "utf-8", errors="ignore")
                filepath = os.path.join(ATTACHMENT_DIR, decoded_filename)
                with open(filepath, "wb") as f:
                    f.write(part.get_payload(decode=True))
                print(f"📎 Attachment saved: {filepath}")
    print("-" * 50)

# ----------- Email Watcher -----------

def monitor_inbox():
    print("🔍 Starting email watcher...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
    mail.select("inbox")

    seen_uids = set()

    while True:
        result, data = mail.search(None, "UNSEEN")
        if result != "OK":
            print("❌ Error searching inbox.")
            time.sleep(CHECK_INTERVAL)
            continue

        uid_bytes = data[0]
        if not uid_bytes:
            time.sleep(CHECK_INTERVAL)
            continue

        uids = uid_bytes.split()
        new_uids = [uid for uid in uids if uid not in seen_uids]

        for uid in new_uids:
            uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
            if not uid_str.strip().isdigit():
                continue

            result, msg_data = mail.fetch(uid_str, "(RFC822)")
            if result != "OK" or not msg_data or not msg_data[0]:
                print(f"❌ Failed to fetch UID {uid_str}")
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            process_email(msg)
            seen_uids.add(uid)

        time.sleep(CHECK_INTERVAL)

# ----------- Run -----------

if __name__ == "__main__":
    monitor_inbox()
