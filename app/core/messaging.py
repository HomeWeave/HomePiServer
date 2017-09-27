import json
import logging
import socket

from retask import Task


logger = logging.getLogger(__name__)


class MessagingException(Exception):
    def err_msg(self):
        return self.__class__.__name__

    def to_msg(self):
        msg = Message("result")
        msg.headers["RES"] = self.err_msg()
        return msg


class InvalidMessageStructure(MessagingException):
    pass


class BadOperation(MessagingException):
    pass


class RequiredFieldsMissing(MessagingException):
    pass


class WaitTimeoutError(MessagingException):
    pass


class QueueNotFound(MessagingException):
    pass


class SchemaValidationFailed(MessagingException):
    pass


def parse_message(lines):
    required_fields = {"OP"}
    fields = {}
    for line in lines:
        line_parts = line.split(" ", 1)
        if len(line_parts) != 2:
            raise InvalidMessageStructure
        fields[line_parts[0]] = line_parts[1]

    if required_fields - set(fields.keys()):
        raise RequiredFieldsMissing

    if "MSG" in fields:
        try:
            obj = json.loads(fields["MSG"])
        except json.decoder.JSONDecodeError:
            raise SchemaValidationFailed
        task = Task(obj)
        del fields["MSG"]
    else:
        task = None
    msg = Message(fields.pop("OP"), task)
    msg.headers = fields
    return msg


def serialize_message(msg):
    msg_lines = [
        "OP " + msg.op,
    ]

    for key, value in msg.headers.items():
        msg_lines.append(key + " " + str(value))

    if msg.task is not None:
        msg_lines.append("MSG " + json.dumps(msg.task.data))
    msg_lines.append("")  # Last newline before blank line.
    return "\n".join(msg_lines)


def read_message(conn):
    # Reading group of lines
    lines = []
    while True:
        line = conn.readline()
        stripped_line = line.strip()
        if not line:
            # If we have read a line at least, raise InvalidMessageStructure,
            # else IOError because mostly the socket was closed.
            if lines:
                raise InvalidMessageStructure
            else:
                raise IOError
        if not stripped_line:
            break
        lines.append(stripped_line.decode("UTF-8"))
    return parse_message(lines)


def write_message(conn, msg):
    conn.write((serialize_message(msg) + "\n").encode())
    conn.flush()


def raise_message_exception(err):
    known_exceptions = {
        InvalidMessageStructure, BadOperation, RequiredFieldsMissing,
        QueueNotFound, SchemaValidationFailed
    }
    responses = {c().err_msg(): c for c in known_exceptions}
    responses["OK"] = None

    ex = responses.get(err, Exception)
    if ex:
        raise ex(err)


def ensure_ok_message(msg):
    if msg.op != "result" or "RES" not in msg.headers:
        raise MessagingException("Invalid acknowledgement message.")
    raise_message_exception(msg.headers["RES"])


class Message(object):
    def __init__(self, op, msg=None):
        self.op = op
        self.headers = {}
        self.json = msg

    @property
    def operation(self):
        return self.op

    @property
    def task(self):
        return self.json


class Sender(object):
    PORT = 11023
    READ_BUF_SIZE = -1
    WRITE_BUF_SIZE = 10240

    def __init__(self, queue, host="localhost"):
        self.queue = queue
        self.host = host
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self):
        self.sock.connect((self.host, self.PORT))
        self.rfile = self.sock.makefile('rb', self.READ_BUF_SIZE)
        self.wfile = self.sock.makefile('wb', self.WRITE_BUF_SIZE)

    def send(self, obj):
        if isinstance(obj, Message):
            msg = obj
        else:
            msg = Message("enqueue", obj)
            msg.headers["Q"] = self.queue

        write_message(self.wfile, msg)
        msg = read_message(self.rfile)
        ensure_ok_message(msg)

    def close(self):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()


class Receiver(object):
    PORT = 11023
    READ_BUF_SIZE = -1
    WRITE_BUF_SIZE = 10240

    def __init__(self, queue, host="localhost"):
        self.queue = queue
        self.host = host
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.active = False

    def start(self):
        self.sock.connect((self.host, self.PORT))
        self.rfile = self.sock.makefile('rb', self.READ_BUF_SIZE)
        self.wfile = self.sock.makefile('wb', self.WRITE_BUF_SIZE)

    def run(self):
        self.active = True

        while self.active:
            try:
                msg = self.receive()
            except IOError:
                if self.active:
                    raise
            if msg.task is not None:
                self.on_message(msg.task.data)
            else:
                logger.warning("Dropping message without data.")
                continue

            # TODO: ACK the server.

    def receive(self):
        dequeue_msg = Message("dequeue")
        dequeue_msg.headers["Q"] = self.queue
        write_message(self.wfile, dequeue_msg)
        msg = read_message(self.rfile)
        if msg.op == "inform":
            return msg
        if "RES" not in msg.headers:
            raise MessagingException("RES header absent. Not an inform msg.")
        raise_message_exception(msg.headers["RES"])

    def stop(self):
        self.active = False
        self.rfile.close()
        self.wfile.close()
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()

    def on_message(self, msg):
        pass
