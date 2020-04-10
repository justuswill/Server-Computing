# Update Images
sudo docker image build -t flask:1.0 flask/
sudo docker image build -t scheduler:1.0 Scheduler/
sudo docker image build -t notebookserver:1.0 jupyter/

# Restart Server
kubectl delete -f Kubernetes/frontend.yaml
kubectl apply -f Kubernetes/frontend.yaml