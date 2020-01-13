from kubernetes import client, config
from kubernetes.client.rest import ApiException
import socket
import sqlalchemy as db
import pprint
import logging


def create_job(batch_api_instance, core_api_instance, id, USER, PY_FILE):
    """
    Input: Needs an instance of the BatchV1Api and the CoreV1Api
    -----
    Create a Job from the Notebook-Container:
    ----------
    labels: id:<id>
    containers:
      - name: notebook-site
      - image: notebookserver:1.0
      - env:
          - name: PY_FILE
            value: <PY_FILE>
      - volumeMounts:
        - mountPath: "/data"
          subPath: "data"
          name: vol
        - mountPath: "/scripts"
          subPath: "internal/USER"
          name: vol
    volumes:
      - name: vol
      - persistentVolumeClaim:
        - claimName: <VOLUME_NAME>
    ----------
    """
    JOB_NAME = "notebook-%02d" % id
    VOLUME_NAME = "hostclaim"
    
    # The place to mount the datasets
    data_mount = client.V1VolumeMount(
            mount_path="/data",
            sub_path="data",
            name="vol")
    # The place to mount the scripts
    script_mount = client.V1VolumeMount(
            mount_path="/scripts",
            sub_path="internal/" + USER,
            name="vol")
    # volume for Datasets/scripts
    volume = client.V1Volume(
            name="vol",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                    claim_name=VOLUME_NAME))
    # env-Variables
    env = client.V1EnvVar(name='PY_FILE', value=PY_FILE)
    # Container
    container = client.V1Container(
            name="notebook-site",
            image="notebookserver:1.0",
            env=[env],
            volume_mounts=[data_mount, script_mount])
    # Labels
    # selector = client.V1LabelSelector(match_labels={"app":APP_NAME})
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
    
    # Creat the service
    create_service(core_api_instance, id)


def create_service(api_instance, id):
    """
    Input: Needs an instance of the CoreV1Api
    -----
    Create a Service for the Notebook-Job:
    -----
    apiVersion: v1
    kind: Service
    metadata:
      name: SERVICE_NAME
      namespace: default
    spec:
      type: NodePort
      selector:
        id: <id>
      ports:
      - port: 8888
        targetPort: 8888
        nodePort: NODE_PORT
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
                namespace='default', body= service)
        logging.info("Service created. status='%s'" % str(api_response.status))
    except ApiException as e:
        logging.warning("Exception when calling CoreV1Api->create_namespaced_service: %s\n" % e)
    
    
def update(batch_api_instance, core_api_instance, checkServices=False):
    """
    Input: Needs an instance of the BatchV1Api and the CoreV1Api
    -----
    check for changes in db and create job+service for new entries
    also delete job+service for deleted entries
    if checkServices is True check if existing jobs have their service
    -----
    (Copy Python Files directly from host, doesn't scale.
     Later use of NFS etc is advised.)
    """
    # Connect to DB
    engine = db.create_engine('sqlite:////mnt/internal/queue.db', convert_unicode=True)
    connection = engine.connect()
    metadata = db.MetaData()
    tasks = db.Table('tasks', metadata, autoload=True, autoload_with=engine)
    
    # Get all existing ids
    query = db.select([tasks])
    result_proxy = connection.execute(query)
    result_set = result_proxy.fetchall()
    ids_db = {x[0] for x in result_set}
    py_files = {x[0]: x[4] for x in result_set}
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
    ids_to_add = ids_db - ids_kube
    ids_to_delete = ids_kube - ids_db
    logging.info("ids found: %s | ids needed: %s\ncreating ids: %s\ndeleting ids: %s" %
                 (ids_kube, ids_db, ids_to_add, ids_to_delete))
    
    # Create new notebooks
    for id in ids_to_add:
        create_job(batch_api_instance, core_api_instance, id, users[id], py_files[id])
    
    # Delete old notebooks
    for id in ids_to_delete:
        delete_job(batch_api_instance, core_api_instance, id)
        
    if checkServices:
        update_services(core_api_instance, ids_db)


def update_services(api_instance, ids_db):
    """
    Input: Needs an instance of the CoreV1Api
    -----
    Create Service if there is none
    
    Because Services are created only when notebooks are created,
    this should never add something
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
    for id in ids_to_add:
        create_service(api_instance, id)

 
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
            id = int(job.metadata.labels['id'])
            # Delete from Kubernetes
            logging.info("Notebook finished, id = %d" % id)
            delete_job(batch_api_instance, core_api_instance, id)
            # Delete from db
            delete = tasks.delete().where(tasks.c.id == id)
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
    Thy can be reached at 127.0.0.1:31000+<id>
    Updates when it recieves message 'update' from frontend
    """
    # Init api + logger
    config.load_incluster_config()
    batch_api_instance = client.BatchV1Api()
    core_api_instance = client.CoreV1Api()
    logging.basicConfig(level=logging.INFO)
    logging.info('Started Scheduler')
    
    # Check if db and kubernetes line up (also check the if services are running)
    update(batch_api_instance, core_api_instance, checkServices=True)
    
    HOST = '127.0.0.1'  # localhost
    PORT = 65432        # Port to listen on

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        
        # Listen for Connection:
        while True:
            s.listen()
            conn, addr = s.accept()
            with conn:
                logging.info('Connected by %s' % str(addr))
                while True:
                    # Listen for messages
                    data = conn.recv(1024).decode("utf-8")
                    # Connection lost
                    if not data:
                        break
                    if data == 'update':
                        update(batch_api_instance, core_api_instance)
                    conn.sendall(b'Done')


if __name__ == '__main__':
    main()
