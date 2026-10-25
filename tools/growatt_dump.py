#!/usr/bin/env python3
"""Liest Holding-Register des Growatt SPH (nur lesen!) und schreibt sie in register_dump.txt.
Aufruf: python3 tools/growatt_dump.py [IP]"""
import socket, struct, sys, time, os, datetime
IP = sys.argv[1] if len(sys.argv) > 1 else "192.168.178.210"
BLOCKS = [(0, 40), (40, 40), (80, 45), (1000, 50), (1050, 50), (1100, 25)]

def read(addr, n, tid):
    s = socket.create_connection((IP, 502), timeout=6)
    try:
        s.sendall(struct.pack(">HHHBBHH", tid, 0, 6, 1, 3, addr, n))
        d = b""
        while len(d) < 9:
            c = s.recv(512)
            if not c: raise IOError("Verbindung geschlossen")
            d += c
        if d[7] & 0x80: return "Fehlercode %d" % d[8]
        while len(d) < 9 + d[8]: d += s.recv(512)
        return list(struct.unpack(">%dH" % n, d[9:9 + 2 * n]))
    finally:
        s.close()

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "register_dump.txt")
lines = ["Dump %s von %s" % (datetime.datetime.now().isoformat(timespec="seconds"), IP)]
for i, (a, n) in enumerate(BLOCKS):
    for t in range(4):
        try:
            v = read(a, n, i + 1)
            if isinstance(v, str): lines.append("%d: %s" % (a, v))
            else:
                for k, x in enumerate(v): lines.append("H%d=%d" % (a + k, x))
            break
        except Exception as e:
            if t == 3: lines.append("%d: fehlgeschlagen (%s)" % (a, e))
            time.sleep(1.5)
    time.sleep(0.5)
open(out, "w").write("\n".join(lines) + "\n")
ok = sum(1 for l in lines if l.startswith("H"))
print("Fertig: %d Register gelesen -> %s" % (ok, os.path.abspath(out)))
