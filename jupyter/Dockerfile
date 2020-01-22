FROM pytorch/pytorch:latest
RUN /opt/conda/bin/conda install tornado==5.1.1 && \
    /opt/conda/bin/conda install -y nodejs Cython tensorflow pandas scikit-learn matplotlib seaborn jupyter jupyterlab && \
    /opt/conda/bin/conda clean -ya
ENV PY_FILE=
ENV JUPYTER_PWD=
ENV JUPYTER_STATUS=Ready
EXPOSE 8888
COPY entrypoint.sh /
RUN chmod 777 /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
