set -e
cp -r /src /app && cd /app && mkdir -p daten
pulseaudio -D --exit-idle-time=-1 --system=false 2>/dev/null || true
python3 main.py >/tmp/station.log 2>&1 &
for i in $(seq 40); do curl -sf localhost:5000/api/status >/dev/null && break; sleep 0.5; done
printf 'Montag: Linsensuppe 3,50\nDienstag: Gemüsecurry 5,90\nMittwoch: Schnitzel mit Pommes 7,90\nDonnerstag: Pasta Arrabiata 6,20\nFreitag: Fischfilet 8,40\n' > daten/plan.txt
python3 - <<'PY'
import json,urllib.request as u
def req(m,p,d=None):
    r=u.Request('http://localhost:5000'+p,data=json.dumps(d).encode() if d else None,method=m,headers={'Content-Type':'application/json'})
    return json.load(u.urlopen(r))
st=req('GET','/api/layouts'); lid=list(st['layouts'])[0] if isinstance(st.get('layouts'),dict) else None
print('layouts:',list(st.get('layouts',{}))[:5], 'keys', list(st)[:6])
for lid in st['layouts']:
  L=st['layouts'][lid]
  L['regionen']=[{"id":"r1","name":"Speiseplan","x":0,"y":0,"w":100,"h":100,"z":0,"typ":"widget","ton":False,
  "widget":{"typ":"speiseplan","datei":"plan.txt","ansicht":"woche","titel":"Speiseplan KW 45"}}]
  try: print(req('PUT','/api/layouts/'+lid,L).get('ok'))
  except Exception as e: print('PUT',e, e.read()[:300] if hasattr(e,'read') else '')
PY
curl -s -XPOST localhost:5000/api/multicast/start -H 'Content-Type: application/json' -d '{"name":"BGHM"}'; echo
sleep 8
curl -s localhost:5000/api/multicast/status; echo
ffmpeg -v quiet -y -i 'rtp://239.10.10.211:1000' -frames:v 1 -update 1 /out/frame.png || true
ffprobe -v quiet -show_entries stream=codec_name,width,height -of csv=p=0 'rtp://239.10.10.211:1000' 2>&1 | head -4
curl -s -XPOST localhost:5000/api/multicast/stop; echo
grep -iE "error|traceback" /tmp/station.log | head -5
