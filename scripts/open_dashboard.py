"""Open a private Edge window pinned to the verified local server certificate."""
import base64
import hashlib
import os
import ssl
import subprocess
from pathlib import Path
from urllib.request import ProxyHandler, HTTPSHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]


def spki_pin(pem):
    """Extract DER SubjectPublicKeyInfo; hashing uses the standard library."""
    data = ssl.PEM_cert_to_DER_cert(pem)
    def field(offset):
        if offset+2 > len(data): raise ValueError("truncated certificate")
        tag, size, start = data[offset], data[offset+1], offset+2
        if size & 128:
            count = size & 127
            if not 1 <= count <= 4 or start+count > len(data): raise ValueError("invalid DER length")
            size = int.from_bytes(data[start:start+count],"big")
            start += count
        end = start+size
        if end > len(data): raise ValueError("truncated DER field")
        return tag,start,end
    tag,certificate_start,certificate_end = field(0)
    if tag != 48 or certificate_end != len(data): raise ValueError("invalid certificate sequence")
    tag,offset,tbs_end = field(certificate_start)
    if tag != 48: raise ValueError("invalid certificate body")
    if data[offset] == 160: offset = field(offset)[2]
    for _ in range(5): offset = field(offset)[2]
    tag,_,end = field(offset)
    if tag != 48 or end > tbs_end: raise ValueError("invalid public key sequence")
    return base64.b64encode(hashlib.sha256(data[offset:end]).digest()).decode()


def main():
    certificate = ROOT/".secrets/server-cert.pem"
    context = ssl.create_default_context(cafile=str(certificate))
    opener = build_opener(ProxyHandler({}),HTTPSHandler(context=context))
    with opener.open("https://127.0.0.1:8765/health/live",timeout=10) as response:
        if response.status != 200: raise RuntimeError("service unavailable")
    pin = spki_pin(certificate.read_text())
    candidates = [Path(os.environ.get(name,"C:/Program Files"))/"Microsoft/Edge/Application/msedge.exe"
                  for name in ("ProgramFiles(x86)","ProgramFiles")]
    browser = next((p for p in candidates if p.is_file()),None)
    if browser is None: raise RuntimeError("Microsoft Edge not found; open the localhost dashboard with the configured certificate trusted")
    profile = ROOT/".secrets/dashboard-browser"
    profile.mkdir(mode=0o700,exist_ok=True)
    url = "https://localhost:8765/api/v1/dashboard"
    subprocess.Popen([str(browser),"--user-data-dir="+str(profile),"--ignore-certificate-errors-spki-list="+pin,
                      "--no-first-run","--app="+url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print("Live dashboard:",url)
    print("Private browser window opened. Sign in with the operator token from .secrets/alice.token.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError,ValueError,RuntimeError):
        print("Dashboard could not open. Check service readiness, the local certificate and Edge installation.")
        raise SystemExit(1)
