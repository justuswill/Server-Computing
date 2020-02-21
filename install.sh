sudo apt-get upgrade -y
sudo apt install docker.io curl -y
sudo systemctl enable docker
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add
sudo apt-add-repository "deb http://apt.kubernetes.io/ kubernetes-xenial main"
sudo apt install kubeadm -y
sudo sed -i.bak '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
sudo swapoff -a
sudo kubeadm init --pod-network-cidr=10.244.0.0/16
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
sudo mkdir -p /mnt/sharedfolder/data
sudo mkdir -p /mnt/sharedfolder/internal
sudo cp -i flask/queue.db /mnt/sharedfolder/internal
sudo docker image build -t flask:1.0 flask/
sudo docker image build -t scheduler:1.0 Scheduler/
sudo docker image build -t notebookserver:1.0 jupyter/
cd Kubernetes/
kubectl apply -f kube-flannel.yaml
kubectl taint node --all node-role.kubernetes.io/master:NoSchedule-
kubectl apply -f role.yaml
kubectl apply -f hostpv.yaml
kubectl apply -f hostclaim.yaml
kubectl apply -f frontend.yaml
