# Server-Computing
Eine Program mit Web-Interface für den GPU-Server, welches es ermöglicht Python Code und Module mit
Jupyter Notebooks auf dem Server über Kubernetes containerisiert laufen zu lassen.

Hier finden sich einige wichtigen Infos zu:
- Installation
- Konfiguration
- Abhängigkeiten
- Funktionsweise
- Passwörter
- Containerisierung

##Installation:
Damit Kubernetes und das serverseitige Program installiert werden können, muss der Inhalt dieses Repositories
heruntergeladen werden und die `install.sh` ausgeführt werden.
Es wird dann ein Kubernetes-Cluster auf dem Rechner erstellt und der Server hochgefahren.
Er kann standardmäßig unter: `127.0.0.1:30001` erreicht werden.

Einfacher geht es, direkt mit `git` herunterzuladen, falls dieses bereits installiert ist, z.B.:

```sh
cd ~
git clone https://github.com/Jukamala/Server-Computing.git
./install.sh
```

##Konfiguration:
Der Server kann an vielen Stellen angepasst werden.

Generell gilt, dass nach einer Änderung die `Docker-Images` geupdatet
und der Server in Kubernetes neugestartet müssen, z.B. mittels:

```sh
# Update Images
sudo docker image build -t flask:1.0 flask/
sudo docker image build -t scheduler:1.0 Scheduler/
sudo docker image build -t notebookserver:1.0 jupyter/

# Restart Server
kubectl delete -f Kubernetes/frontend.yaml
kubectl apply -f Kubernetes/frontend.yaml
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

```sh
# Update Volumes
kubectl delete -f hostpv.yaml
kubectl delete -f hostclaim.yaml
kubectl apply -f hostpv.yaml
kubectl apply -f hostclaim.yaml
```

####Ports
Von außen kann das Cluster über einen sogenanntes `NodePort` erreicht werden.
Dieser Port wird auf jedem Knoten des Clusters freigegeben.
Standardmäßig ist der Port auf `30001` eingestellt, er kann geändert werden, indem in `Kubernetes/frontend.yaml`
das Attribut `nodePort` in der letzten Zeile geändert wird.

####Pakete
Standardmäßig haben die `Kubernetes-Jobs`, auf denen Jupyter läuft, nur eine begrenzte Anzahl von Paketen installiert.
(z.B. PyTorch, Scikit-learn, etc.)
Soll ein Programm laufen, dass andere Pakete verwendet, so kann man die Liste der Pakete unter
`jupyter/requirements.txt` anpassen. Nur der erste Eintrag `tornado==5.1.1` ist wichtig,
da die aktuellste Version von `tornado`, welche `Jupyter` mitliefert zum Zeitpunkt der Erstellung des Codes
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
Standardmäßig wird alle 30 Sekunden aktualisiert.

Ist kein Web-Interface im Browser geöffnet und zwingt den `Scheduler` zu einem Updateschritt,
so macht dieser standardmäßig alle 5 Minuten ein manuelles Update, um zu schauen,
ob ein `Job` fertig wurde. Diese Refreshrate lässt sich in `Scheduler/schedule.py (Z.400)` ändern.

Die Einstellungen der Dropzone für das Hochladen von Python Code finden sich in `flask/temp/addtask.html`.
Vor allem die maximale Größe einer Datei könnte hier evtl. zu Problemen führen.

Diw Webseite kann beschleunigt werden, wenn nach jeder Nachricht an den `Scheduler` nicht auf desen Antwort gewartet wird.
Dies kann man in `flask/app.py (Z.95 und Z.262)` ändern. Die höhere Geschwindigkeit geht zu Lasten der Fehleranfälligkeit.

Für eigene Änderungen am Code der Webseite sollte der Debug Modus von Flask angeschaltet werden.
Dies geht in `flask/app.py` ganz unten.

## Abhängigkeiten
Damit der Server funktionieren kann wird `Docker` und `Kubernetes` benötigt,
beide werden in ihrer aktuellsten Version installiert. Alle anderen Programme wie Python, Jupyter,
etc. werden nur innerhalb von Containern verwendet und müssen deshalb nicht installiert werden.
Welche Pakete in welchen Versionen die Container intern verwenden, kann in allen Unterordnern
in einer `requirements.txt` nachgeschaut werden.
Es wird bei einer Installation immer die neuste Version von Python in den `Docker Images` installiert und verwendet.

Damit Kubernetes laufen kann, muss jeder `SWAP` Arbeitsspeicher permanent ausgeschalten werden.
Dies wird bei der Installation automatisch erledigt.

## Funktionsweise
Nach der abgeschlossener Installation ist das Web-Interface über den eingestellten Port (standardmäßig `30001`)
des Servers zu finden.

Die Startseite zeigt alle aktuellen Tasks an.
Neben der optionalen Angabe von geschätzter Dauer und Ersteller wird zu jedem Task der aktuelle Status angezeigt:
- ***Ready:*** Ein Task ist bereit und wartet darauf gestartet zu werden
- ***Running:*** Ein Task wird gerade in einem Container ausgeführt
- ***Finished:*** Die Ausführung eines Tasks ist beendet und es kann auf die Ergebnisse der Ausführung
                  in Jupyter zugegriffen werden, bzw. mit dem Notebook interagiert werden.
                  
Ein Task kann beendet werden, indem man nach der Ausführung das `Jupyter Notebook` öffnet
und es dort unter `Quit` schließt. Man kann dann wieder auf die Startseite zurückkehren.

Es findet Sich außerdem Zugang zu den folgenden Funktionen:

#### Task hinzufügen
Ein Task ist entweder:
- Ein leeres `jupyter notebook`
- Ein existierendes `jupyter notebook`, dass ausgeführt werden soll
- `Python Code` (einzelne Datei oder Modul), das ausgeführt werden soll

Entsprechendes muss ausgewählt werden und aller nötiger Code in der Dropzone
entweder über Drag und Drop oder über den Dateiexplorer hochgeladen werden.

Mehrere Dateien können einfach über das Reinziehen eines Ordners hochgeladen werden.
Die Ordnersruktur wird auf der Serverseite wieder hergestellt, ohne den Ordner, in denen die Dateien hochgeladen wurden
(der gemeinsame Pfadprefix der Dateien wird entfernt).

Es sollte in diesem Fall auch der Name der Methode, die gestartet werden soll (mit oder ohne Endung) angegeben werden,
bei einzelnen Dateien ist dies natürlich nicht nötig.

Eckdaten wie Ersteller und geschätzte Dauer können optional angegeben werden.
Wird kein Ersteller angegeben, so wird der Standardnutzer `dfki` mit unveränderlichem Passwort `dfki` verwendet

####Datensätze hochladen
Man kann hier (auch große) Datensätze hochladen und erhält ein visuelles Feedback über den Fortschritt des Uploads.
Die hier hochgeladenen Datensätze können innerhalb des Containers eines jeden Tasks
über den absouluten Pfad `/data` erreicht werden.

Es ist zu beachten, dass dem Server nur so viel Speicher zur Verfügung steht, wie für ihn konfiguriert wurde.
(siehe Konfiguration)

#### Passwort ändern
Hier kann man das Passwort zu einem Nutzer ändern, wenn man das alte Passwort weiß.

Jeder Task ist mit einem Passwort geschützt, jedem Nutzernamen ist ein Passwort zugeordnet,
das automatisch verwendet wird, wenn diser Name als der Ersteller beim Erstellen eines Tasks eingetragen wurde.

Um ein Passwort zu generieren muss ein Task mit dem Nutzernamen als Ersteller erstellt werden.
Das Standardpasswort ist gleichlautend zum Nutzernamen und sollte sofort geändert werden.

Bsp: `Justus_DFKI` erstellt sein ersten Task. Sein Passwort ist `Justus_DFKI`

Die Passwortübertragung ist nicht sicher, also sollte am besten kein Passwort verwendet werden,
dass in anderen Accounts bereits verwendet wird. Näheres unten.

## Passwörter

Alle Passwörter werden in gehashter Form auf dem Volume des Servers (standardmäßig die Festplatte des Rechners)
gespeichert. Die Verschlüsselung geschieht erst auf der Seite des Servers, deshalb wird das Passwort ungeschützt
im Netzwerk übertragen und kann theoretisch abgefangen werden.
Der Passwortschutz dient nur als rudimentärer Schutz der eigenen Tasks.

##Containerisierung:
Intern ist der Server folgendermaßen strukturiert:

`Kubernetes` arbeitet mit sogenannten `Pods`, die grob gesprochen, eine zusammenhängende ausführbare Einheit 
mit begrenzter Lebensdauer darstellen.

Jeder `Pod` enthält mindestens einen `Container` der in diesem Fall aus einem `Docker Image` erstellt wird.
Diese Images geben an, welche Pakete im `Container` installiert werden und was für Programme darin laufen.

Der Server verwendet drei Images:
- den `Flask Server`, er stellt das Web-Interface zur Verfügung und ruft falls nötig den `Scheduler` auf.
- den `Scheduler`, er ist die Schnittstelle zur Kubernetes API, er erstellt `Jobs` und überprüft deren Status.
- der `Jupyter Notebook Server`, er führt Python Code aus und stellt ihn danach als `Jupyter Notebook` zur Verfügung

der `Flask Server` und der `Scheduler` befinden sich in einem gemeinsamen `Pod`,
der außerdem noch eine `SQL` Datenbank mit allen wartenden und abgeschlossenen Tasks verwaltet und aktualisiert.
In Kubernetes wird dieser `Pod` über  ein `Deployment` gesteuert, das immer eine Instanz zur Verfügung steht
und im Fall eines Absturz eine neue Kopie hochfährt.

Jeder Task der erstellt wird, wird über ein `Job` gesteuert, der dafür sorgt das mindestens ein `Pod` des
`Jupyter Notebook Servers` bis zur Beendigung läuft. Die Erstellung dieser `Jobs` ist Aufgabe des Schedulers.

####Ablauf der Durchführung eines Tasks
Nachdem ein Task über das Web-Interface hinzugefügt wird, wird er vom `Flask Server` in die Datenbank eingetragen.
Danach wird der `Scheduler` aufgerufen. Dieser führt ein Updateschritt durch und erkennt dabei,
dass ein neuer Eintrag der Datenbank vorliegt. Er erstellt einen `Job`. Falls gerade Kapazität frei ist übergibt er
`Kubernetes` den `Job`, ansonsten wird der Task nur in der Warteliste (Datenbank) vermerkt.

In regelmäßigen Zeitabschnitten führt der `Scheduler` einen Updateschritt durch. Er überprüft auch, ob sich der Status
der laufenden `Jobs` geändert hat. Wird ein `Job` fertig, kann der nächste `Job` an `Kubernetes` übergeben werden.
Der Status des Tasks wird zudem in der Datenbank geändert. Da für jeden fertigen `Job` auch ein `Service`
erstellt wird, der den Zugriff auf den jeweiligen `Jupyter Notebook Server` bereitstellt, kann der `Flask Server` nun erfolgreich
auf das fertige `Jupyer Notebook` verlinken.


