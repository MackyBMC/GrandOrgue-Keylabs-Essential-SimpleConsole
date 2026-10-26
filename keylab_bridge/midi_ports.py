"""MIDI port lifecycle and optional KeyLab MAIN-port relay."""

import queue
import threading
import time

from .midi_protocol import CC_SUSTAIN, DEFAULT_PAD_CCS
from .preset_store import find_matching_port

RELAY_QUEUE_LIMIT = 4096
RELAY_DRAIN_BATCH = 256
PORT_QUEUE_LIMIT = 4096
INPUT_QUEUE_LIMIT = 4096
PORT_POLL_INTERVAL_S = 0.01


class _PortWorker:
    def __init__(self, owner, key):
        self.owner = owner
        self.key = key
        self.input_port = key in ("go_in", "kl_in", "main_in")
        self.output_queue = queue.Queue(maxsize=PORT_QUEUE_LIMIT)
        self.input_queue = queue.Queue(maxsize=INPUT_QUEUE_LIMIT)
        self.condition = threading.Condition()
        self.pending_action = None
        self.lifecycle_busy = False
        self.shutdown_requested = False
        self.connected = False
        self.port = None
        self.dropped_output = 0
        self.dropped_input = 0
        self.thread = threading.Thread(target=self.run, name=f"midi-port-{key}", daemon=True)
        self.thread.start()

    def request_action(self, action, shutdown=False):
        with self.condition:
            if self.shutdown_requested:
                return
            if self.lifecycle_busy:
                self.pending_action = "close" if shutdown else action
                if shutdown:
                    self.shutdown_requested = True
                self.connected = False
                self.condition.notify()
                clear_output = action == "close" and not shutdown
            else:
                self.pending_action = action
                self.shutdown_requested = shutdown
                self.connected = False
                self.condition.notify()
                clear_output = action == "close" and not shutdown
        if clear_output:
            self.clear_output()

    def send(self, messages):
        with self.condition:
            if not self.connected or self.pending_action is not None or self.shutdown_requested:
                return False
            try:
                self.output_queue.put_nowait(tuple(messages))
            except queue.Full:
                self.dropped_output += len(messages)
                return False
            self.condition.notify()
            return True

    def clear_output(self):
        while True:
            try:
                self.output_queue.get_nowait()
            except queue.Empty:
                return

    def drain_input(self, limit):
        messages = []
        for _ in range(limit):
            try:
                messages.append(self.input_queue.get_nowait())
            except queue.Empty:
                break
        return messages

    def _close_current(self):
        port, self.port = self.port, None
        if port is not None:
            try:
                port.close()
            except Exception as exc:
                self.owner.report_error(self.key, exc)
        self.owner.set_port_state(self.key, None)

    def _lifecycle(self, action):
        try:
            self._close_current()
            if action == "open":
                wanted = self.owner.wanted(self.key)
                if not wanted:
                    raise ValueError("port name is empty")
                if self.input_port:
                    name = self.owner.find_input_port(wanted)
                    callback = (self.owner.on_main_message
                                if self.key == "main_in" and self.owner.args.relay_main else None)
                    port = (self.owner.backend.open_input(name, callback=callback)
                            if callback else self.owner.backend.open_input(name))
                else:
                    name = self.owner.find_output_port(wanted)
                    port = self.owner.backend.open_output(name)
                self.port = port
                self.owner.set_port_state(self.key, name)
                self.owner.clear_error(self.key)
        except Exception as exc:
            self.owner.report_error(self.key, exc)
            self.owner.set_port_state(self.key, None)
        finally:
            with self.condition:
                self.lifecycle_busy = False

    def run(self):
        while True:
            with self.condition:
                action = self.pending_action
                try:
                    queued_output = not self.output_queue.empty()
                except Exception:
                    queued_output = False
                if action is not None and not (queued_output and self.port is not None):
                    self.pending_action = None
                    self.lifecycle_busy = True
                elif self.shutdown_requested and not queued_output:
                    return
                else:
                    action = None
            if action is not None:
                self._lifecycle(action)
                if self.shutdown_requested and self.pending_action is None:
                    return
                continue

            if not self.input_port and self.port is not None:
                try:
                    messages = self.output_queue.get_nowait()
                except queue.Empty:
                    messages = None
                if messages is not None:
                    try:
                        for message in messages:
                            self.port.send(message)
                        self.owner.record_sent(self.key, len(messages))
                    except Exception as exc:
                        self.owner.report_error(self.key, exc)
                        self.request_action("close")
                    continue
            elif self.input_port and self.port is not None and not (
                    self.key == "main_in" and self.owner.args.relay_main):
                try:
                    for message in self.port.iter_pending():
                        try:
                            self.input_queue.put_nowait(message)
                        except queue.Full:
                            self.dropped_input += 1
                except Exception as exc:
                    self.owner.report_error(self.key, exc)
                    self.request_action("close")
                    continue

            with self.condition:
                self.condition.wait(PORT_POLL_INTERVAL_S)


class MidiPorts:
    def __init__(self, backend, args, stats, recent_times, pad_ccs=None):
        self.backend = backend
        self.args = args
        self.stats = stats
        self.recent_times = recent_times
        self.pad_ccs = set(pad_ccs or DEFAULT_PAD_CCS)
        self.lock = threading.Lock()
        self.errors = {}
        self.actual = {}
        self.error_events = queue.Queue(maxsize=64)
        self.relay_queue = queue.Queue(maxsize=RELAY_QUEUE_LIMIT)
        self.relay_overflows = 0
        self.workers = {key: _PortWorker(self, key) for key in
                ("go_in", "go_out", "kl_in", "kl_out", "main_in", "relay_out")}

    def wanted(self, key):
        if key == "go_in":
            return self.args.go
        if key == "go_out":
            return self.args.go_out or self.args.go
        if key == "kl_in":
            return self.args.kl_in
        if key == "kl_out":
            return self.args.kl_out
        if key == "main_in":
            return self.args.relay_main_in or self.args.kl_main
        if key == "relay_out":
            return self.args.relay_main
        return None

    def open_all(self):
        with self.lock:
            self.errors.clear()
        keys = ["go_in", "go_out", "kl_in", "kl_out"]
        if self.args.relay_main:
            keys += ["relay_out", "main_in"]
        elif self.args.kl_main:
            keys += ["main_in"]
        for key in keys:
            self.workers[key].request_action("open")

    def find_input_port(self, wanted):
        return find_matching_port(self.backend.get_input_names(), wanted)

    def find_output_port(self, wanted):
        return find_matching_port(self.backend.get_output_names(), wanted)

    def set_port_state(self, key, name):
        worker = self.workers[key]
        with worker.condition:
            worker.connected = name is not None and worker.pending_action is None and not worker.shutdown_requested
        with self.lock:
            if name is None:
                self.actual.pop(key, None)
            else:
                self.actual[key] = name

    def clear_error(self, key):
        with self.lock:
            self.errors.pop(key, None)

    def report_error(self, key, exc):
        error = str(exc)
        with self.lock:
            self.errors[key] = error
            self.stats["errors"] += 1
        try:
            self.error_events.put_nowait((key, error))
        except queue.Full:
            pass

    def take_error_events(self):
        events = []
        while True:
            try:
                events.append(self.error_events.get_nowait())
            except queue.Empty:
                return events

    def close(self):
        for worker in self.workers.values():
            worker.request_action("close", shutdown=True)
        # Wait for each port thread to close its native MIDI port before the process exits; exiting with a
        # live rtmidi port and a running daemon thread is what crashed the GUI on F10.
        deadline = time.time() + 3.0               # one shared limit, so a stuck port cannot stall exit for long
        for worker in self.workers.values():
            if worker.thread.is_alive() and worker.thread is not threading.current_thread():
                worker.thread.join(timeout=max(0.0, deadline - time.time()))
        self.clear_relay_queue()

    def mark_failed(self, key, exc):
        self.report_error(key, exc)
        self.workers[key].request_action("close")

    def on_main_message(self, msg):
        with self.lock:
            self.stats["main_in"] += 1
            self.recent_times["main_in"] = time.time()
        try:
            self.relay_queue.put_nowait(msg)
        except queue.Full:
            with self.lock:
                self.relay_overflows += 1

    def drain_relay_queue(self, limit=RELAY_DRAIN_BATCH):
        messages = []
        for _ in range(limit):
            try:
                messages.append(self.relay_queue.get_nowait())
            except queue.Empty:
                break
        return messages

    def send_relay_message(self, message):
        return self.send("relay_out", message)

    def send(self, key, message):
        return self.send_batch(key, (message,))

    def send_batch(self, key, messages):
        return self.workers[key].send(messages)

    def drain_input(self, key, limit=RELAY_DRAIN_BATCH):
        return self.workers[key].drain_input(limit)

    def record_sent(self, key, count):
        with self.lock:
            self.stats[key] += count

    def take_relay_overflows(self):
        with self.lock:
            count, self.relay_overflows = self.relay_overflows, 0
        return count

    def clear_relay_queue(self):
        while True:
            try:
                self.relay_queue.get_nowait()
            except queue.Empty:
                break

    def connected(self, key):
        return self.workers[key].connected

    def required(self):
        keys = ["go_in", "go_out", "kl_in", "kl_out"]
        if self.args.relay_main:
            keys += ["relay_out", "main_in"]
        elif self.args.kl_main:
            keys.append("main_in")
        return keys

    def degraded(self):
        return any(not self.connected(key) for key in self.required())

    def needs_reconnect(self):
        return self.degraded()

