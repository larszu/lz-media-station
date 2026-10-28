cp -r /src /app && cd /app
pulseaudio -D 2>/dev/null
python3 main.py >/tmp/s1.log 2>&1 & P=$!
for i in $(seq 40); do curl -sf localhost:5000/api/status >/dev/null && break; sleep 0.5; done
echo "falsch: $(curl -s -XPOST localhost:5000/api/config -H 'Content-Type: application/json' -d '{"multicast":{"gruppe":"10.0.0.1"}}')"
echo "speichern: $(curl -s -XPOST localhost:5000/api/config -H 'Content-Type: application/json' -d '{"multicast":{"aktiv":true,"name":"Foyer","breite":1280,"hoehe":720,"fps":25,"bitrate_k":4000}}' | head -c 60)"
kill $P; sleep 2
python3 main.py >/tmp/s2.log 2>&1 &
sleep 16
echo "nach Neustart: $(curl -s localhost:5000/api/multicast/status)"
grep Multicast /tmp/s2.log
ffprobe -v quiet -show_entries stream=codec_name,width,height -of csv=p=0 'rtp://239.10.10.211:1000' | head -2
