#!/usr/bin/env python3
"""Create Gouda phone-access certificates and token without changing host networking."""
import argparse, ipaddress, json, os, re, secrets, shutil, subprocess, tempfile
from pathlib import Path
PORT=8443
def die(m): raise SystemExit("setup_phone_access: "+m)
def dns(v):
 try:v=v.encode("idna").decode("ascii").lower().rstrip(".")
 except UnicodeError:die("invalid DNS hostname")
 if len(v)>253 or not v or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",x) for x in v.split(".")):die("invalid DNS hostname; wildcards are not accepted")
 return v
def run(a):subprocess.run(a,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
def default_dir():return Path(os.environ.get("GOUDA_WORKSPACE",Path.home()/"gouda_ws")).expanduser()/"bags/gouda/phone-access"
def check_network():
 for title,c in (("Interfaces and addresses",["ip","-brief","address"]),("Routes",["ip","route"]),("NetworkManager devices",["nmcli","-f","DEVICE,TYPE,STATE,CONNECTION","device","status"])):
  print("\n"+title+":")
  if not shutil.which(c[0]):print("  unavailable ("+c[0]+" is not installed)");continue
  r=subprocess.run(c,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  print(r.stdout.rstrip() if r.returncode==0 else "  unavailable ("+(r.stderr.strip() or "command failed")+")")
 if shutil.which("nmcli"):
  r=subprocess.run(["nmcli","-t","-f","DEVICE,TYPE","device","status"],text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
  for row in r.stdout.splitlines():
   f=row.split(":")
   if len(f)>1 and f[1]=="wifi":
    q=subprocess.run(["nmcli","-f","WIFI-PROPERTIES.AP","device","show",f[0]],text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    print("\nWi-Fi AP capability for "+f[0]+" (read-only):\n"+(q.stdout.rstrip() if q.returncode==0 else "  unavailable"))
 print("\nNo network settings were changed.")
def key_matches(cert,key):
 c=subprocess.run(["openssl","x509","-in",str(cert),"-pubkey","-noout"],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 k=subprocess.run(["openssl","pkey","-in",str(key),"-pubout"],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 return c.returncode==0 and k.returncode==0 and c.stdout==k.stdout
def extend_sans(out,host,extra_ips):
 files={n:out/n for n in ("ca.crt","ca.key","tls.crt","tls.key","token","phone-access.json","manifest.json")}
 if not out.is_dir() or out.stat().st_mode&0o077:die("phone-access directory must be private (mode 0700)")
 try:old=json.loads(files["manifest.json"].read_text())
 except (OSError,ValueError):die("a complete phone-access bundle is required to extend SANs")
 ident=old.get("identity",{})
 if ident.get("hostname")!=host:die("hostname differs from existing CA bundle; refusing extension")
 old_ips=ident.get("ip_addresses")
 if not isinstance(old_ips,list) or any(not f.is_file() for f in files.values()):die("existing phone-access bundle is incomplete")
 if any(files[n].stat().st_mode&0o077 for n in ("ca.key","tls.key","token")):die("private key/token permissions are too broad")
 subprocess.run(["openssl","verify","-CAfile",str(files["ca.crt"]),str(files["tls.crt"])],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 if not key_matches(files["tls.crt"],files["tls.key"]) or not key_matches(files["ca.crt"],files["ca.key"]):die("existing certificate and private key do not match")
 subprocess.run(["openssl","x509","-in",str(files["tls.crt"]),"-checkhost",host,"-noout"],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 for ip in old_ips:subprocess.run(["openssl","x509","-in",str(files["tls.crt"]),"-checkip",ip,"-noout"],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 ips=list(old_ips)
 for ip in extra_ips:
  if ip not in ips:ips.append(ip)
 if ips==old_ips:
  print("All requested IP SANs already exist; no files changed");return
 stage=Path(tempfile.mkdtemp(prefix=".phone-access-extend-",dir=out))
 try:
  run(["openssl","genpkey","-algorithm","RSA","-pkeyopt","rsa_keygen_bits:3072","-out",str(stage/"tls.key")]);os.chmod(stage/"tls.key",0o600)
  run(["openssl","req","-new","-sha256","-key",str(stage/"tls.key"),"-out",str(stage/"tls.csr"),"-subj","/CN="+host])
  names=[f"DNS.1 = {host}"]+[f"IP.{i} = {ip}" for i,ip in enumerate(ips,1)]
  ext=stage/"server.ext";ext.write_text("[server]\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyAgreement\nextendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\nsubjectAltName=@server_alt_names\n[server_alt_names]\n"+"\n".join(names)+"\n",encoding="ascii")
  run(["openssl","x509","-req","-sha256","-days","397","-in",str(stage/"tls.csr"),"-CA",str(files["ca.crt"]),"-CAkey",str(files["ca.key"]),"-CAcreateserial","-out",str(stage/"tls.crt"),"-extfile",str(ext),"-extensions","server"])
  subprocess.run(["openssl","verify","-CAfile",str(files["ca.crt"]),str(stage/"tls.crt")],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  cfg=json.loads(files["phone-access.json"].read_text())
  cfg["url_ip_addresses"]=ips
  gateway_args=[
   "--remote-only","--remote-bind","0.0.0.0","--remote-port",str(PORT),
   "--tls-cert",str(files["tls.crt"]),"--tls-key",str(files["tls.key"]),
   "--remote-token-file",str(files["token"]),
  ]
  for name in [host]+ips:gateway_args.extend(["--allowed-host",name])
  cfg["gateway_arguments"]=gateway_args
  (stage/"phone-access.json").write_text(json.dumps(cfg,indent=2)+"\n");os.chmod(stage/"phone-access.json",0o600)
  (stage/"manifest.json").write_text(json.dumps({"identity":{"hostname":host,"ip_addresses":ips,"port":PORT}},indent=2)+"\n");os.chmod(stage/"manifest.json",0o600)
  os.replace(stage/"tls.key",files["tls.key"]);os.replace(stage/"tls.crt",files["tls.crt"])
  os.replace(stage/"phone-access.json",files["phone-access.json"]);os.replace(stage/"manifest.json",files["manifest.json"])
  print("Extended server certificate SANs; existing CA and access token were preserved")
 finally:shutil.rmtree(stage,ignore_errors=True)
def create(out,host,ips):
 if out.exists() and out.stat().st_mode&0o077:die("phone-access directory must be private (mode 0700): "+str(out))
 files={n:out/n for n in ("ca.crt","ca.key","tls.crt","tls.key","token","phone-access.json","manifest.json")}
 identity={"hostname":host,"ip_addresses":ips,"port":PORT}; mf=files["manifest.json"]
 if mf.exists():
  try:old=json.loads(mf.read_text())
  except (OSError,ValueError):die("existing manifest is unreadable")
  if old.get("identity")!=identity:die("existing identity differs; refusing to replace phone-access files")
  if any(not f.is_file() for f in files.values()):die("existing bundle is incomplete; refusing to replace files")
  if any(files[n].stat().st_mode&0o077 for n in ("ca.key","tls.key","token")):die("private key/token permissions are too broad")
  subprocess.run(["openssl","verify","-CAfile",str(files["ca.crt"]),str(files["tls.crt"])],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  subprocess.run(["openssl","x509","-in",str(files["tls.crt"]),"-checkhost",host,"-noout"],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  if not key_matches(files["tls.crt"],files["tls.key"]) or not key_matches(files["ca.crt"],files["ca.key"]):die("existing certificate and private key do not match")
  for ip in ips: subprocess.run(["openssl","x509","-in",str(files["tls.crt"]),"-checkip",ip,"-noout"],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  print("Reusing existing phone-access bundle: "+str(out));return
 if any(f.exists() for f in files.values()):die("phone-access files exist without a matching manifest; refusing to overwrite")
 existed=out.exists();out.mkdir(parents=True,exist_ok=True,mode=0o700)
 if existed and out.stat().st_mode&0o077:die("existing output directory must be private (mode 0700): "+str(out))
 stage=Path(tempfile.mkdtemp(prefix=".phone-access-",dir=out))
 try:
  run(["openssl","genpkey","-algorithm","RSA","-pkeyopt","rsa_keygen_bits:3072","-out",str(stage/"ca.key")]);os.chmod(stage/"ca.key",0o600)
  run(["openssl","req","-x509","-new","-sha256","-days","3650","-key",str(stage/"ca.key"),"-out",str(stage/"ca.crt"),"-subj","/CN=Gouda Phone Access Local CA","-addext","basicConstraints=critical,CA:TRUE,pathlen:0","-addext","keyUsage=critical,keyCertSign,cRLSign","-addext","subjectKeyIdentifier=hash"])
  run(["openssl","genpkey","-algorithm","RSA","-pkeyopt","rsa_keygen_bits:3072","-out",str(stage/"tls.key")]);os.chmod(stage/"tls.key",0o600)
  run(["openssl","req","-new","-sha256","-key",str(stage/"tls.key"),"-out",str(stage/"tls.csr"),"-subj","/CN="+host])
  names=[f"DNS.1 = {host}"]+[f"IP.{i} = {ip}" for i,ip in enumerate(ips,1)]
  ext=stage/"server.ext";ext.write_text("[server]\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyAgreement\nextendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\nsubjectAltName=@server_alt_names\n[server_alt_names]\n"+"\n".join(names)+"\n",encoding="ascii")
  run(["openssl","x509","-req","-sha256","-days","397","-in",str(stage/"tls.csr"),"-CA",str(stage/"ca.crt"),"-CAkey",str(stage/"ca.key"),"-CAcreateserial","-out",str(stage/"tls.crt"),"-extfile",str(ext),"-extensions","server"])
  (stage/"token").write_text(secrets.token_urlsafe(48)+"\n",encoding="ascii");os.chmod(stage/"token",0o600)
  gateway_args=[
   "--remote-only","--remote-bind","0.0.0.0","--remote-port",str(PORT),
   "--tls-cert",str(files["tls.crt"]),"--tls-key",str(files["tls.key"]),
   "--remote-token-file",str(files["token"]),
  ]
  for name in [host]+ips:gateway_args.extend(["--allowed-host",name])
  cfg={
   "remote_only":True,"remote_bind":"0.0.0.0","remote_port":PORT,
   "tls_cert":str(files["tls.crt"]),"tls_key":str(files["tls.key"]),
   "remote_token_file":str(files["token"]),"ca_cert":str(files["ca.crt"]),
   "url_hostname":host,"url_ip_addresses":ips,"gateway_arguments":gateway_args,
  }
  (stage/"phone-access.json").write_text(json.dumps(cfg,indent=2)+"\n");os.chmod(stage/"phone-access.json",0o600)
  (stage/"manifest.json").write_text(json.dumps({"identity":identity},indent=2)+"\n");os.chmod(stage/"manifest.json",0o600)
  subprocess.run(["openssl","verify","-CAfile",str(stage/"ca.crt"),str(stage/"tls.crt")],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  for n in files:
   os.link(stage/n,out/n);(stage/n).unlink()
  print("Created phone-access bundle: "+str(out))
 except FileExistsError:die("a phone-access file appeared during creation; no existing file was overwritten")
 finally:shutil.rmtree(stage,ignore_errors=True)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--hostname");p.add_argument("--ip-address",action="append",default=[]);p.add_argument("--extend-existing",action="store_true",help="explicitly add supplied IP SANs to an existing bundle, reusing its CA and token");p.add_argument("--output-dir",type=Path,default=default_dir());p.add_argument("--check-network",action="store_true")
 a=p.parse_args()
 if a.check_network:
  if a.hostname or a.ip_address:p.error("--check-network cannot be combined with certificate identity options")
  check_network();return
 if not a.hostname:p.error("--hostname is required unless --check-network is used")
 if a.extend_existing and not a.ip_address:p.error("--extend-existing requires at least one --ip-address")
 host=dns(a.hostname);ips=[]
 for value in a.ip_address:
  try:ip=str(ipaddress.ip_address(value))
  except ValueError:p.error("invalid IP address: "+value)
  if ip not in ips:ips.append(ip)
 if not shutil.which("openssl"):die("openssl is required")
 out=a.output_dir.expanduser().resolve()
 if a.extend_existing:extend_sans(out,host,ips)
 else:create(out,host,ips)
 print("Gateway: remote-only HTTPS, bind 0.0.0.0, port 8443")
 print("Config: "+str(out/"phone-access.json"))
 print("Public CA for iPhone import: "+str(out/"ca.crt"))
 print("Private keys and token remain protected; network settings were not changed.")
if __name__=="__main__":main()
