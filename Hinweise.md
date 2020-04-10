# Hinweise zur Weiterentwicklung

Hier sind einige heikle Stellen angegeben, die besonders viele Probleme bereitet haben und deshalb
evtl besonderer Erklärung bedürfen, warum sie so und nicht anders umgesetzt wurden.

## Upload von Python Code mit JS

Der Upload von Python Code ist eine komplizierte Sache gewesen und vor allem die Möglichkeit Ordner hochzuladen
war viel kleine Fummelarbeit:

#### Upload

Der Upload läuft über eine `JS Dropzone` (https://www.dropzonejs.com), die mit eigenem JS Code angepasst werden musste.
Die Endpunkte finden sich in `flask/app.py`.

Da die Dropzone in einem `Flask Form` integriert ist und zusammen mit den Eckdaten am Server ankommen soll,
läuft der Vorgang so ab:

Wird der Button für das Erstellen eines Tasks gedrückt so sorgt JS in `flask/temp/addtask.html` dafür, dass
das Abschicken des Formulars gestoppt wird. Danach werden alle Dateien, die in der Dropzone angelegt wurden
an den Endpoint `/dropzone` geschickt und dort verareitet.
Da das Formular mit den Eckdaten nicht an den selben Endpunkt gesendet werden kann werden alle Dateien ins
Volume im Ordner `internal` zwischengespeichert. In einer Session wird gespeichert welche Dateien das sind
(über deren Namen) und wie man die Ordnerstruktur wieder herstellen kann.

Ist der Upload fertig sorgt das JS in `addtask.html` dafür, dass das Formular an den Endpunkt `/addtask` gesendet
wird. Hier wird die Session ausgelesen und der Rest erledigt:

#### Struktur wiederherstellen
Damit Module mit Unterordnern als Ganzes funktionieren, muss die Struktur wieder hergestellt werden, die auch
auf dem Rechner des Clienten vorlag. Hierfür wird vor dem Versand an `/dropzone` im Header für jede Datei
noch der komplette relative Path (`"fullPath"`) hinzugefügt.

In `/addtask` wird jede Datei aus der Zwischenablage in `internal` an seinen richtigen Platz in 
`internal/<USER>/<TASK ID>` verschoben. Damit es übersichtlicher bleibt wird das gemeinsame prefix aller `fullPath`
Attribute entfernt, also im Standardfall, landet eine eventuelle `main.py`,
falls Sie im höchsten Level der Ordnerstruktur liegt, dirket in `internal/<USER>/<TASK ID>/` statt in
`internal/<USER>/<TASK ID>/<MODULE FOLDER>/`, dass macht den Zugriff auf Datensätze intuitiver.

Verwaltet ein Nutzer seine lokalen Datensätze und Module in zwei Unterordnern des selben Ordners muss er nämlich so nichts
an seinem Code ändern, damit er auf dem Server laufen kann.

## interne Ordnerstruktur
Wie schon oben und in der Anleitung erwähnt gibt es auf dem Volume die Ordner `data` für Datensätze
und `internal` für Python Code, etc. Jeder Nutzer hat dort wiederrum einen Ordner mit seinem Nutzernamen,
der wiedrrum einen Unterordner für jeden Task hat der gerade aktiv ist (der Name ist die TASK ID).
So kommen sich zwei laufende Programme nicht in die Quere.

Gehashte Passwörter liegen ebenfalls im Nutzerordner.

## Ressourcen fertiger Jobs
Ich habe lange nach der Möglichkeit gesucht während der Laufzeit die Ressourcen von `Jobs` zu ändern,
aber auch außerhalb von `Jobs` gibt es dazu keine Möglichkeiten in `Kubernetes`.
`Docker Compose` hat diese Möglichkeit, aber hinkt sonst in vielen anderen Punkten.

Das hat dazu geführt, dass Jobs erst auf das Cluster kommen, wenn auch Ressourcen frei werden, und beendete Jobs
immernoch die gleichen Obergrenzen für Ressourcen haben, wie aktive Jobs.
Zwar ist ihr Bedarf nur minimal, trotzdem sollte deshalb darauf geachtet werden,
niemals zu viele davon auf einmal zu haben und nicht mehr gebrauchte Tasks konsequent zu löschen.

## Kommunikation zwischen Pods
Ein Großteil der Kommunikation läuft über die gemeinsame Datenbank ab.

Es gibt eine Außnahme und das ist, wenn der `Flask Server` die Startseite neu lädt oder wenn auf dem `Flask Server`
ein Task hinzugefügt wurde. Da der `Flask Server` und der `Scheduler` im selben Pod liegen teilen Sie Sich dank
Kubernetes den selben `localhost (127.0.0.1)`. Die Nachricht wird über den von mir zufällig gewählten `Port 65432`
geschickt.

Momentan wartet der `Flask Server` noch auf die Antwort des `Schedulers`, da die Anfragen an die `Kubernetes API`
aber sehr lange dauern, sorgt das dafür, dass die Seite beim Neuladen viel Zeit benötigt.
Meiner Meinung nach ist das So besser, als das die Möglichkeit besteht eine neue Anfrage an den `Scheduler`
zu senden obwohl dieser noch nicht bereit ist.

In diesem Fall würde der `Flask Server` einen Error werfen.
Warten und nach kurzer Zeit neu Laden behebt das Problem, das ist aber evtl. nicht jedem Nutzer klar, wenn er die
Fehlermeldung bekommt. 

## Flask und gleichzeitige Zugriff auf das Web-Interface

Es wird geraten niemals den Flask Server alleine in Production zu verwenden um eine Seite bereit zu stellen.
Ich hab überlegt ob ich Programme wie `Gunicorn` etc verwenden soll um auch mit mehreren Anfragen klar zu kommen,
bin aber zu der Entscheidung gekommen, das `Kubernetes` hier ausreicht. Besonders da wahrscheinlich selten mehr
als eine Person mit den Server über `POSTS` interagiert. Einfache `GETS` der Startseite werden nacheinander
bearbeitet und sollten keine Probeleme machen.
Falls hier doch mehr gemacht werden muss könnte man auch in die `LoadBalancer` von `Kubernetes` reinschauen.
Ich bin aber kein Experte was dieses Thema angeht,
also sollte man sich hier nicht blind auf diese Entscheiung verlassen.

## Cluster mit mehr als einem Rechner

In Zukunft könnte die Möglichkeit bestehen mehr als einen Rechner
für die Abarbeitung von Tasks zur Verfügung zu stellen.
Man sollte dann bei dem Installationsvorgang genau aufpassen, in der Konsole wird nach Initialisierung von Kubernetes
ein individueller Code/Link ausgegeben, den man braucht um einen weiteren Knoten in das Cluster einzufügen.