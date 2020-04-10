from kubernetes import client, config
from kubernetes.stream import stream
from kubernetes.client.rest import ApiException
import socket
import sqlalchemy as db
import logging


def create_job(batch_api_instance, core_api_instance, id, USER, PY_FILE, PWD, settings):
    """
    Input: Needs an instance of the BatchV1Api and the CoreV1Api
           id           - id of task
           USER         - User/Owner of the task (so the executable files can be reached)
           PY_FILE, PWD - the ENV variables to be set for Jupyter to work as intended
           settings = (CPU_SHARE, MEM_SHARE, _) - how much CPU and RAM to use at most
    -----
    Create a Job from a Notebook-Container and add it to the cluster.
    The job is similarly structured like this YAML:
    ----------
    labels: id:<id>
    containers:
      - name: notebook-site
      - image: notebookserver:1.0
      - env:
          - name: PY_FILE
            value: <PY_FILE>
          - name: JUPYTER_PWD
            value: <PWD>
      - resources:
          limits:
            cpu: <CPU_SHARE>
            memory: <MEM_SHARE>
      - volumeMounts:
        - mountPath: "/data"
          subPath: "data"
          name: vol
        - mountPath: "/scripts"
          subPath: "internal/<USER>/<id>"
          name: vol
    volumes:
      - name: vol
      - persistentVolumeClaim:
        - claimName: <VOLUME_NAME>
    ----------
    """
    JOB_NAME = "notebook-%02d" % id
    VOLUME_NAME = "hostclaim"
    CPU_SHARE, MEM_SHARE, _ = settings

    # The place to mount the datasets
    data_mount = client.V1VolumeMount(
        mount_path="/data",
        sub_path="data",
        name="vol")
    # The place to mount the scripts
    script_mount = client.V1VolumeMount(
        mount_path="/scripts",
        sub_path="internal/%s/%d" % (USER, id),
        name="vol")
    # volume for datasets/scripts
    volume = client.V1Volume(
        name="vol",
        persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
            claim_name=VOLUME_NAME))
    # env-Variables
    file_env = client.V1EnvVar(name='PY_FILE', value=PY_FILE)
    pwd_env = client.V1EnvVar(name='JUPYTER_PWD', value=PWD)
    # Resources
    resources = client.V1ResourceRequirements(
        limits={"cpu": CPU_SHARE, "memory": MEM_SHARE},
        requests={"cpu": "0", "memory": "0"}
    )
    # Container
    container = client.V1Container(
        name="notebook-site",
        image="notebookserver:1.0",
        env=[file_env, pwd_env],
        resources=resources,
        volume_mounts=[data_mount, script_mount])
    # Pod-Spec
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"id": str(id)}),
        spec=client.V1PodSpec(
            restart_policy="Never",
            volumes=[volume],
            containers=[container]))
    # Job-Spec
    spec = client.V1JobSpec(
        template=template,
        backoff_limit=4)
    # Job-Object
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=JOB_NAME),
        spec=spec)

    # Add Job to Cluster
    try:
        api_response = batch_api_instance.create_namespaced_job(
            body=job, namespace="default")
        logging.info("Job created. status='%s'" % str(api_response.status))
    except ApiException as e:
        logging.warning("Exception when calling CoreV1Api->create_namespaced_job: %s\n" % e)

    # Create the service so the notebook becomes accessible
    create_service(core_api_instance, id)


def create_service(api_instance, id):
    """
    Input: Needs an instance of the CoreV1Api
    -----
    Create a Service for the Notebook-Job.
    The service is similarly structured like this YAML:
    -----
    apiVersion: v1
    kind: Service
    metadata:
      name: <SERVICE_NAME>
      namespace: default
    spec:
      type: NodePort
      selector:
        id: <id>
      ports:
      - port: 8888
        targetPort: 8888
        nodePort: <NODE_PORT>
    -----
    """
    SERVICE_NAME = "nb-entrypoint-%02d" % id
    NODE_PORT = 31000 + id

    # Port
    port = client.V1ServicePort(
        port=8888,
        target_port=8888,
        node_port=NODE_PORT)
    # Job-Spec
    spec = client.V1ServiceSpec(
        selector={"id": str(id)},
        type='NodePort',
        ports=[port])
    # Service-Objekt
    service = client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(
            name=SERVICE_NAME,
            labels={"sid": str(id)}),
        spec=spec)

    # Add Service to Cluster
    try:
        api_response = api_instance.create_namespaced_service(
            namespace='default', body=service)
        logging.info("Service created. status='%s'" % str(api_response.status))
    except ApiException as e:
        logging.warning("Exception when calling CoreV1Api->create_namespaced_service: %s\n" % e)


def update(batch_api_instance, core_api_instance, settings, check_services=False):
    """
    Input: Needs an instance of the BatchV1Api and the CoreV1Api
           settings = (_, _, parallel) - how many tasks to run at once
    -----
    check for changes in db and create job+service for new entries
    also delete job+service for deleted entries
    if checkServices is True check if existing jobs have their service
    """
    # Connect to DB
    engine = db.create_engine('sqlite:////mnt/internal/queue.db', convert_unicode=True)
    connection = engine.connect()
    metadata = db.MetaData()
    tasks = db.Table('tasks', metadata, autoload=True, autoload_with=engine)

    # Get all existing ids (and other data)
    query = db.select([tasks])
    result_proxy = connection.execute(query)
    result_set = result_proxy.fetchall()
    ids_db = {x[0] for x in result_set}
    py_files = {x[0]: x[4] for x in result_set}
    pwds = {x[0]: x[6] for x in result_set}
    users = {x[0]: x[1] for x in result_set}
    logging.info(result_set)

    delete_completed_jobs(batch_api_instance, core_api_instance, connection, tasks)

    # Get all running job ids
    try:
        jobs = batch_api_instance.list_job_for_all_namespaces()
    # logging.info(pprint.pformat(api_response))
    except ApiException as e:
        print("Exception when calling BatchV1Api->list_job_for_all_namespaces: %s\n" % e)
        return
    ids_kube = {int(job.metadata.labels['id']) for job in jobs.items if job.metadata.name.startswith('notebook-')}
    ids_to_add = sorted(list(ids_db - ids_kube))
    ids_to_delete = list(ids_kube - ids_db)
    logging.info("ids found: %s | ids needed: %s | queued ids: %s | deleting ids: %s" %
                 (ids_kube, ids_db, list(ids_to_add), list(ids_to_delete)))

    # Delete old notebooks
    for _id in ids_to_delete:
        delete_job(batch_api_instance, core_api_instance, _id)

    # There can be <parallel> task at once
    parallel = settings[2]
    new_jobs = parallel - update_status(core_api_instance, connection, tasks)

    # Create new notebooks until there are running <parallel> many
    while new_jobs > 0 and len(ids_to_add) > 0:
        _id = ids_to_add.pop(0)
        create_job(batch_api_instance, core_api_instance, _id, users[_id], py_files[_id], pwds[_id], settings)
        new_jobs -= 1

    if check_services:
        update_services(core_api_instance, ids_db)


def update_status(core_api_instance, connection, tasks):
    """
    Checks for updates in the status of notebooks and changes db accordingly
    returns how many jobs can be started
    """
    stream_api_instance = client.CoreV1Api()

    # Get all existing statuses
    query = db.select([tasks])
    result_proxy = connection.execute(query)
    result_set = result_proxy.fetchall()
    status_by_id = {x[0]: x[5] for x in result_set}

    # Get pods that are relevant
    try:
        pods = core_api_instance.list_namespaced_pod(namespace='default')
    except ApiException as e:
        print("Exception when calling BatchV1Api->list_job_for_all_namespaces: %s\n" % e)
        return
    for pod_name in [p.metadata.name for p in pods.items if p.metadata.name.startswith("notebook-")]:
        pod_id = int(pod_name.split('-')[1])
        if pod_id not in status_by_id.keys():
            continue
        try:
            resp = stream(stream_api_instance.connect_get_namespaced_pod_exec,
                          pod_name,
                          'default',
                          command=['/bin/bash'],
                          stderr=True, stdin=True,
                          stdout=True, tty=True,
                          _preload_content=False)
        except ApiException:
            # Just started pods cant exec yet
            logging.info("not able to scan pod %s" % pod_name)
            continue

        resp.write_stdin('echo $JUPYTER_STATUS\n')
        status = resp.readline_stdout(timeout=3)
        # Wait for the right response
        while status is not None:
            status = status[:-1]
            if status in ['Ready', 'Running', 'Finished']:
                status_by_id[pod_id] = status
            status = resp.readline_stdout(timeout=3)

    # commit changes to db
    for _id, st in status_by_id.items():
        upd = db.update(tasks).where(tasks.c.id == _id).values(status=st)
        connection.execute(upd)

    # Change Resources
    return list(status_by_id.keys()).count("Running")


def update_services(api_instance, ids_db):
    """
    Input: Needs an instance of the CoreV1Api
    -----
    Creates a service for every job that doesn't have one.
    -----
    Because Services are created only when notebooks are created,
    unless something goes wrong this should never do something.
    It is for fail-proofing and stability and is not necessary in a setting with no complications/error.
    """
    # Get all running services
    try:
        api_response = api_instance.list_service_for_all_namespaces()
    # logging.info(pprint.pformat(api_response.items))
    except ApiException as e:
        logging.warning("Exception when calling BatchV1Api->list_service_for_all_namespaces: %s\n" % e)
        return
    ids_kube = {int(service.metadata.labels['sid']) for service in api_response.items
                if service.metadata.name.startswith("nb-entrypoint-")}
    ids_to_add = ids_db - ids_kube
    if len(ids_to_add) > 0:
        logging.warning("Can't find services for ids %s. They will be created" % ids_to_add)

    # Create new services
    for _id in ids_to_add:
        create_service(api_instance, _id)


def delete_completed_jobs(batch_api_instance, core_api_instance, connection, tasks):
    """
    Input: Needs an instance of the BatchV1Api and the CoreV1Api
           and the connection to the db and the table tasks
    -----
    When a Job is completed (i.e notebook is quit) it will be deleted
    Its Entry is then deleted from the db
    """
    # Get all running jobs
    try:
        jobs = batch_api_instance.list_job_for_all_namespaces()
    # logging.info(pprint.pformat(api_response))
    except ApiException as e:
        print("Exception when calling BatchV1Api->list_job_for_all_namespaces: %s\n" % e)
        return

    for job in jobs.items:
        if job.metadata.name.startswith('notebook-') and job.status.succeeded == 1:
            _id = int(job.metadata.labels['id'])
            # Delete from Kubernetes
            logging.info("Notebook finished, id = %d" % _id)
            delete_job(batch_api_instance, core_api_instance, _id)
            # Delete from db
            delete = tasks.delete().where(tasks.c.id == _id)
            connection.execute(delete)


def delete_job(batch_api_instance, core_api_instance, id):
    """
    Input: Needs an instance of the BatchV1Api and the CoreV1Api
    -----
    Delete a Notebook Job+Service that was deleted from the db
    """
    JOB_NAME = "notebook-%02d" % id
    SERVICE_NAME = "nb-entrypoint-%02d" % id

    # Delete Job
    try:
        api_response = batch_api_instance.delete_namespaced_job(
            name=JOB_NAME,
            namespace="default",
            body=client.V1DeleteOptions(
                propagation_policy='Foreground',
                grace_period_seconds=5))
    except ApiException as e:
        print("Exception when calling BatchV1Api->delete_namespaced_job: %s\n" % e)
        return
    logging.info("Job deleted. status='%s'" % str(api_response.status))

    # Delete Service
    try:
        api_response = core_api_instance.delete_namespaced_service(
            name=SERVICE_NAME,
            namespace="default",
            body=client.V1DeleteOptions(
                propagation_policy='Foreground',
                grace_period_seconds=5))
    except ApiException as e:
        print("Exception when calling BatchV1Api->delete_namespaced_job: %s\n" % e)
        return
    logging.info("Service deleted. status='%s'" % str(api_response.status))


def main():
    """
    Creates and Deletes Jobs+Services for the Notebook images.
    They can be reached at 127.0.0.1:31000+<id>
    Updates when it receives message 'update' from frontend.
    See method 'update' for more info
    """

    # Init api + logger
    config.load_incluster_config()
    c = client.Configuration()
    c.assert_hostname = False
    client.Configuration.set_default(c)
    batch_api_instance = client.BatchV1Api()
    core_api_instance = client.CoreV1Api()
    logging.basicConfig(level=logging.INFO)
    logging.info('Started Scheduler')

    # init configuration
    try:
        with open('settings', 'r') as c:
            settings = [line.replace('\n', '').split('=')[1] for line in c.readlines()]
            settings[2] = int(settings[2])
    except FileNotFoundError:
        logging.warning('Configuration file not found using standard configuration')
        settings = ["1.5", "5000Mi", 2]

    # Check if db and kubernetes line up (also check if the services are running)
    update(batch_api_instance, core_api_instance, settings, check_services=True)

    HOST = '127.0.0.1'  # localhost
    PORT = 65432  # Port to listen on

    # If there is no connection still update every <update_rate> seconds
    update_rate = 300
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))

        # Listen for Connection:
        while True:
            s.settimeout(update_rate)
            s.listen()
            try:
                conn, addr = s.accept()
            except socket.timeout:
                # Manual Update
                update(batch_api_instance, core_api_instance, settings)
            with conn:
                logging.info('Connected by %s' % str(addr))
                while True:
                    # Listen for messages
                    data = conn.recv(1024).decode("utf-8")
                    # Connection lost
                    if not data:
                        break
                    if data == 'update':
                        update(batch_api_instance, core_api_instance, settings)
                    conn.sendall(b'Done')


if __name__ == '__main__':
    main()
