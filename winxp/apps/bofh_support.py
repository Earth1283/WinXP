"""MacroHard Technical Support -- a chat window that never actually helps.

The "support agent" replies to every message with a canned deflection,
regardless of what was typed. In the grand tradition of technical support
that exists purely to make the problem someone else's.
"""
from __future__ import annotations

import random

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget

from .. import theme
from ..xp_dialog import DIALOG_BUTTON_QSS, build_dialog_frame

GREETING = (
    "Connecting you to MacroHard Technical Support...\n"
    "You are caller number 4,827 in the queue.\n\n"
    "Support Agent: Yes? What do you want."
)

EXCUSES = [
    "That's a hardware problem. We only do software.",
    "Have you tried turning off the entire building and turning it back on?",
    "I see the issue -- you're using the computer. Please stop doing that.",
    "That's actually a feature. We're closing this ticket as 'working as intended.'",
    "Our AI diagnostic system says the problem is you.",
    "This falls under Tier 12 support. Unfortunately we only go up to Tier 4.",
    "Let me transfer you to someone who can help. [You are placed on hold indefinitely.]",
    "I'm going to need you to fill out Form 27B/6 in triplicate before we proceed.",
    "That error is cosmetic. Your document is fine. Reality is the problem.",
    "We've identified the root cause: sunspots.",
    "Unfortunately your support contract expired four seconds ago. Would you like to renew?",
    "That's not a bug, that's an undocumented feature we're very proud of.",
    "Can you replicate the issue while I watch? ...No, over video, from an unusual angle.",
    "I've escalated this to our engineering team, who has confirmed they are also confused.",
    "Please restart your document, your computer, and possibly your career.",
    "According to my script, I now say 'Have you tried Google?'",
    "The bug you're experiencing was fixed in a version we haven't released yet.",
    "This is a known issue. It is also an unknown issue. Schrodinger's bug.",
    "I'm not saying it's your fault, but it's also not not your fault.",
    "Our servers are located in a facility that, legally, I cannot describe.",
    "Try clicking somewhere else. Anywhere else. Just not there.",
    "That feature was deprecated in a meeting you weren't invited to.",
    "I'll need your firstborn's signature to authorize this fix.",
    "We take your feedback very seriously, right up until this call ends.",
    "Sounds like a 'you' problem, not a 'MacroHard' problem.",
    "The fix is simple: buy MacroHard Word Professional Ultra Deluxe Edition.",
    "I can't help with that, but I can interest you in an extended warranty.",
    "Our support philosophy is 'if it's still broken tomorrow, it probably fixed itself.'",
    "That's above my pay grade. Actually, everything is above my pay grade.",
    "The issue you're describing does not appear in our documentation, so it does not exist.",
    "We rolled back the fix for that because it fixed too many things.",
    "Please hold. Your call is important to us, which is why nobody is answering it.",
    "I've created a ticket. It joins 4,000 other tickets in a folder marked 'Someday.'",
    "Are you sure you didn't cause this by opening the application?",
    "Let's try uninstalling and reinstalling your operating system's operating system.",
    "That's actually intentional. It builds character.",
    "We appreciate your patience. We do not, however, promise a resolution.",
    "I've consulted the manual. The manual has also given up.",
    "Support for that feature ended the moment you needed it.",
    "Per company policy, I am legally required to ask if you've tried Clippy.",
]


class SupportChatDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(False)
        self.resize(460, 420)

        inner = build_dialog_frame(self, "MacroHard Technical Support")

        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS}")
        root = QVBoxLayout(body)
        root.setContentsMargins(10, 10, 10, 10)

        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setStyleSheet("background: white;")
        self.transcript.append(GREETING)
        root.addWidget(self.transcript, 1)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Describe your issue...")
        self.input.returnPressed.connect(self._send)
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self._send)
        row.addWidget(self.input, 1)
        row.addWidget(send_btn)
        root.addLayout(row)

        inner.addWidget(body)
        self.input.setFocus()

    def respond_to(self, message: str) -> str:
        return random.choice(EXCUSES)

    def _send(self):
        text = self.input.text().strip()
        if not text:
            return
        self.transcript.append(f"\nYou: {text}")
        self.transcript.append(f"Support Agent: {self.respond_to(text)}")
        self.input.clear()
