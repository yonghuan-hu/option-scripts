
from datetime import datetime
from typing import Optional, TextIO


class Logger:

    file: Optional[TextIO] = None
    time: datetime = datetime.fromtimestamp(0)

    def info(self, message: str):
        print(f"[{self.time}] {message}", file=self.file)

    def error(self, message: str):
        print(f"[{self.time}] [ERROR] {message}", file=self.file)

    def settime(self, time: datetime):
        self.time = time

    def open(self, path: str):
        if self.file:
            self.file.close()
        self.file = open(path, "w")

    def close(self):
        if self.file:
            self.file.close()
            self.file = None


logger = Logger()
