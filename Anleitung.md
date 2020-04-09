# Server-Computing
Eine Program mit Web-Interface für den GPU-Server, welches es ermöglicht Python Code und Module mit
Jupyter Notebooks auf dem Server über Kubernetes containerisiert laufen zu lassen.

##Installation:
Damit Kubernetes und das serverseitige Program installiert werden können, muss der Inhalt dieses Repositories
heruntergeladen werden und die `install.sh` ausgeführt werden.
Es wird dann ein Kubernetes-Cluster auf dem Rechner erstellt und der Server hochgefahren.
Er kann standardmäßig unter: `127.0.0.1:30001` erreicht werden.

Einfacher geht es, direkt mit `git` herunterzuladen, falls dieses bereits installiert ist, z.B.:

```
cd ~
git clone https://github.com/Jukamala/Server-Computing.git
./install.sh
```

##Konfiguration:
Der Server kann an vielen Stellen angepasst werden.

Generell gilt, dass nach einer Änderung die `Docker-Images` geupdatet
und der Server in Kubernetes neugestartet müssen, z.B. mittels:

```
# Update Images
sudo docker image build -t flask:1.0 flask/
sudo docker image build -t scheduler:1.0 Scheduler/
sudo docker image build -t notebookserver:1.0 jupyter/

# Restart Server
kubectl delete -f frontend.yaml
kubectl apply -f frontend.yaml
```

Hier die Konfigurationsmöglichkeiten in aufsteigender Komplexität:

#### Ressourcen
Jeder Task wird als `Kubernetes Job` ausgeführt. Die Ressourceneinstellungen befinden sich in `/Scheduler/settings`.
Es können immer so viele `Jobs` gleichzeitig laufen, wie in `parallel` angegeben.
Jeder laufenden `Jobs` wird insgesamt so viel CPU und RAM zur Verfügung gestellt, wie in `cpu` und `mem` angegeben -
Hier können also die Kapazitäten des Rechners eingestellt werden, die dem Server zur Verfügung stehen.

Insgesamt benötigt der Server also maximal `cpu * parallel` CPU und `mem * parallel` RAM.
Genaueres zu den Einheiten dieser Ressourcen unter:
https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/#meaning-of-cpu

Beendete `Jobs` sind hier natürlich nicht eingerechnet, benötgen aber nur minimale Ressourcen.

Wie viel Speicher dem Server zur Verfügung steht hängt stark vom verwendeten Volume ab (s.u.),
wird der standardmäßige Festplattenspeicher verwendet kann man unter `Kubernetes/hostpv.yaml`
den Wert von `storage` (Z.20) anpassen, um den maximal zu verwendeten Speicher zu erhöhen.
Zusätzlich müssen die Änderungen aktiviert werden:

```
# Update Volumes
kubectl delete -f hostpv.yaml
kubectl delete -f hostclaim.yaml
kubectl apply -f hostpv.yaml
kubectl apply -f hostclaim.yaml
```

####Ports
Von außen kann das Cluster über einen sogenanntes `NodePort` erreicht werden.
Dieser Port wird auf jedem Konten des Clusters freigegeben.
Standardmäßig ist der Port auf `30001` eingestellt, er kann geändert werden, indem in `Kubernetes/frontend.yaml`
das Attribut `nodePort` in der letzten Zeile geändert wird.

####Pakete
Standardmäßig haben die `Kubernetes-Jobs`, auf denen Jupyter läuft, nur eine begrenzte Anzahl von Paketen installiert.
Soll ein Programm laufen, dass andere Pakete verwendet, so kann man die Liste der Pakete unter
`jupyter/requirements.txt` anpassen. Nur der erste Eintrag `tornado==5.1.1` ist wichtig,
da die aktuelle Version von `tornado`, welche Jupyter mitliefert zum Zeitpunkt der Erstellung des Codes
zu Kompatibilitätsproblemen geführt hat.
Ansonsten kann die Liste beliebig ergänzt werden. 

####Ordnerstruktur und Volumes

Die Datensätze und die internen Daten (Die Warteschlange, laufender Code, Passwörter)
werden standardmäßig auf der Festplatte des Rechners abgelegt.
Spätestens wenn aus dem einzelnen Server ein Cluster mit mehreren Rechnern wird,
ist es nötig, alle Daten anders zu verwalten.

Standardmäßig wird als Ordner `mnt/sharedfolder/data` und `mnt/sharedfolder/internal` verwendet,
der Ordner kann unter `Kubernetes/hostpv.yaml` mit dem Wert von `path` in der letzten Zeile geändert werden.

Kubernetes bietet zudem mit `Volumes` die Möglichkeit eine beliebige Art der Datenverwaltung zu verwenden, z.B `NFS`.
Es muss lediglich ein anderes `Perstisten Volume (PV)` und ein `Persistent Volume Claim (PVC)` erstellt werden.
Damit der Server es verwenden kann muss das alte PV und PVC ersetzt werden:

```
# Change Volumes
kubectl delete -f hostpv.yaml
kubectl delete -f hostclaim.yaml
kubectl apply -f new_pv.yaml
kubectl apply -f new_claim.yaml
```
und anschließend in `Kubernetes/frontend.yaml (Z.20)` der Wert von `claimName`,
sowie in `Scheduler/schedule.py (Z. 47)` der Wert von `VOLUME_NAME` angepasst werden.

Falls NFS verwendet wird, kann man als Startpunkt unter `Kubernetes/Unused` ein PV und PVC finden.
Sonst empfiehlt sich: https://kubernetes.io/docs/concepts/storage/volumes/#types-of-volumes

####Sonstiges

Die Refreshrate der Startseite lässt sich in `flask/temp/index.html (Z.7)` auf die Sekunde einstellen.
Standardmäßiges wird alle 30 Sekunden aktualisiert.

Die Einstellungen der Dropzone für das Hochladen von Python Code finden sich in `flask/temp/addtask.html`.
Vor allem die maximale Größe einer Datei könnte hier evtl. zu Fehlern führen.

Der Server kann beschleunigt werden, wenn nach jeder Nachricht an den Scheduler nicht auf desen Antwort gewartet wird.
Dies kann man in `flask/app.py (Z.88 und Z.255)` ändern. Die höhere Geschwindigkeit geht zu Lasten der Fehleranfälligkeit.

Für eigene Änderungen am Code der Webseite sollte der Debug Modus von Flask angeschaltet werden.
Dies geht in `flask/app.py` ganz unten.


## Funktionsweise

## Passwörter

##Containerisierung: