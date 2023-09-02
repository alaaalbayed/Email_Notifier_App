import tkinter as tk
from tkinter import filedialog, messagebox
import imaplib
import email as ems
import threading
import sqlite3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class EmailNotifierApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Email Notifier App")
        self.root.configure(bg='black')
        self.root.geometry("400x400")

        self.email_list = []
        self.running = False
        self.emails = []

        self.smtp_server = None
        self.smtp_port = None

        self.label = tk.Label(root, text="Upload a file containing email addresses and passwords:", bg='black', fg='green')
        self.label.pack(pady=10)

        self.upload_button = tk.Button(root, text="Upload File", command=self.upload_file, bg='black', fg='green')
        self.upload_button.pack()

        self.trace_button = tk.Button(root, text="Trace Emails", command=self.toggle_tracing, bg='black', fg='green')
        self.trace_button.pack(pady=10)

        self.view_button = tk.Button(root, text="View Emails", command=self.view_emails, bg='black', fg='green')
        self.view_button.pack(pady=10)

        self.log_text = tk.Text(root, height=20, width=40, bg='black', fg='green')
        self.log_text.pack(pady=10)

        scrollbar = tk.Scrollbar(root, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

        self.check_email_interval = 10000  # milliseconds (10 seconds)
        self.check_emails_after_interval()

        # Initialize SQLite database
        self.db_file = "emails.db"

    def create_database(self):
        db_connection = sqlite3.connect(self.db_file)
        cursor = db_connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY,
                sender TEXT,
                recipient TEXT,
                subject TEXT,
                body TEXT
            )
        """)
        db_connection.commit()
        db_connection.close()

    def upload_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.email_list.clear()  # Clear the old email list
        with open(file_path, 'r') as file:
            self.email_list.extend([line.strip() for line in file.readlines()])  # Add new email addresses
        self.log_text.delete(1.0, tk.END)  # Clear the log text widget
        self.log_text.insert(tk.END, f"File uploaded: {len(self.email_list)} email accounts\n")

    def check_emails(self, email_data):
        email, password = email_data.split('|')
        domain = email.split('@')[1]

        if "gmail" in domain:
            self.smtp_server = 'smtp.gmail.com'
            self.smtp_port = 587  # Gmail SMTP port
            imap_server = 'imap.gmail.com'
        elif "hotmail" in domain or "outlook" in domain:
            self.smtp_server = 'smtp.office365.com'
            self.smtp_port = 587  # Hotmail/Outlook SMTP port
            imap_server = 'outlook.office365.com'
        else:
            self.log_text.insert(tk.END, f"Unsupported email provider for {email}\n")
            return

        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email, password)
        mail.select('inbox')

        _, data = mail.search(None, 'UNSEEN')
        email_ids = data[0].split()

        for email_id in email_ids:
            _, msg_data = mail.fetch(email_id, '(RFC822)')
            msg = ems.message_from_bytes(msg_data[0][1])
            sender_email = msg["From"]
            recipient_email = email  # Use the provided email as the recipient
            subject = msg["Subject"]

            # Check if the payload is not None before attempting to decode
            if msg.is_multipart():
                body = ""
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()  # Retrieve email body
                        break  # Stop after the first valid body part
            else:
                body = msg.get_payload(decode=True).decode() if msg.get_payload() is not None else ""

            self.log_text.insert(tk.END, f"New mail from: {sender_email} to: {recipient_email}\n")

            # Store the email in the database
            self.store_email(sender_email, recipient_email, subject, body)

        mail.logout()

    def check_emails_after_interval(self):
        if self.running:
            for email_data in self.email_list:
                threading.Thread(target=self.check_emails, args=(email_data,), daemon=True).start()
        self.root.after(self.check_email_interval, self.check_emails_after_interval)

    def toggle_tracing(self):
        if not self.running:
            self.running = True
            self.trace_button.config(text="Stop Tracing", bg='red')
            self.log_text.insert(tk.END, "Tracing emails...\n")
        else:
            self.running = False
            self.trace_button.config(text="Trace Emails", bg='black')
            self.log_text.insert(tk.END, "Stopped tracing.\n")

    def view_emails(self):
        view_window = tk.Toplevel(self.root)
        view_window.title("View Emails")
        view_window.geometry("400x400")

        email_listbox = tk.Listbox(view_window, bg="black", fg='green', font=('Courier', 10))
        emails = self.get_emails_from_database()
        for i, email in enumerate(emails):
            sender_email, recipient, subject, _ = email
            email_listbox.insert(tk.END, f"{i + 1}. From: {sender_email}, To: {recipient}, Subject: {subject}")
            email_listbox.bind("<ButtonRelease-1>", self.view_email_details)

        email_listbox.pack(fill=tk.BOTH, expand=True)

    def view_email_details(self, event):
        selected_index = event.widget.nearest(event.y)
        emails = self.get_emails_from_database()
        
        if 0 <= selected_index < len(emails):
            email = emails[selected_index]
            sender_email, recipient_email, subject, body = email

        reply_window = tk.Toplevel(self.root)
        reply_window.title("Email Details")
        reply_window.configure(bg='black')
        reply_window.geometry("400x400")

        from_label = tk.Label(reply_window, text=f"From: {sender_email}", bg="black", fg='green')
        from_label.pack()

        to_label = tk.Label(reply_window, text=f"To: {recipient_email}", bg="black", fg='green')
        to_label.pack()

        subject_label = tk.Label(reply_window, text=f"Subject: {subject}", bg="black", fg='green')
        subject_label.pack(pady=2)

        body_label = tk.Label(reply_window, text="Body:", bg="black", fg='green')
        body_label.pack(pady=2)

        body_text = tk.Text(reply_window, height=15, width=40, bg="black", fg='green')
        body_text.pack(pady=3)

        body_text.insert(tk.END, body)

        reply_button = tk.Button(reply_window, text="Reply", command=lambda: self.open_reply_window(sender_email, recipient_email, subject))
        reply_button.pack()

    def open_reply_window(self, recipient, sender, subject):
        if "<" in recipient and ">" in recipient:
            recipient_email = recipient.split("<")[1].split(">")[0]
        else:
            recipient_email = recipient

        user_email, user_password = self.get_user_credentials(sender)

        def send_and_update_label():
            try:
                self.send_email(
                    user_email,
                    user_password,
                    recipient_email,
                    f"Re: {subject}",
                    body_text.get("1.0", tk.END),
                    self.smtp_server,
                    self.smtp_port
                )
                send_status_label.config(text="Email sent successfully.", fg='green')
            except Exception as e:
                send_status_label.config(text=f"Error sending email: {str(e)}", fg='red')

        if user_email and user_password:
            reply_window = tk.Toplevel(self.root)
            reply_window.title("Reply Email")
            reply_window.configure(bg='black')
            reply_window.geometry("400x400")

            to_label = tk.Label(reply_window, text=f"To: {recipient_email}", bg="black", fg='green')
            to_label.pack()

            subject_label = tk.Label(reply_window, text=f"Subject: Re: {subject}", bg="black", fg='green')
            subject_label.pack(pady=2)

            body_label = tk.Label(reply_window, text="Body:", bg="black", fg='green')
            body_label.pack(pady=2)

            body_text = tk.Text(reply_window, height=15, width=40, bg="black", fg='green')
            body_text.pack(pady=3)

            send_button = tk.Button(reply_window, text="Send", command=send_and_update_label)
            send_button.pack(pady=3)

            send_status_label = tk.Label(reply_window, text="", bg='black')
            send_status_label.pack()
        else:
            messagebox.showerror("Error", "Recipient's email not found in the list.")

    def get_user_credentials(self, sender):
        for email_data in self.email_list:
            email, password = email_data.split('|')
            if email == sender:
                return email, password

    def send_email(self, sender_email, sender_password, recipient, subject, body, smtp_server, smtp_port):
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        try:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient, msg.as_string())
            print("Email sent successfully.")
        except Exception as e:
            print("Error sending email:", str(e))

    def store_email(self, sender, recipient, subject, body):
        db_connection = sqlite3.connect(self.db_file)
        cursor = db_connection.cursor()
        cursor.execute("INSERT INTO emails (sender, recipient, subject, body) VALUES (?, ?, ?, ?)",
                       (sender, recipient, subject, body))
        db_connection.commit()
        db_connection.close()

    def get_emails_from_database(self):
        db_connection = sqlite3.connect(self.db_file)
        cursor = db_connection.cursor()
        cursor.execute("SELECT sender, recipient, subject, body FROM emails")
        emails = cursor.fetchall()
        db_connection.close()
        return emails

if __name__ == "__main__":
    root = tk.Tk()
    app = EmailNotifierApp(root)
    app.create_database()  # Create the database if it doesn't exist
    root.mainloop()
