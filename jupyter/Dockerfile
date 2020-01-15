FROM pytorch/pytorch:latest
ENV PY_FILE=
ENV JUPYTER_STATUS=Ready
RUN /opt/conda/bin/conda install tornado==5.1.1 && \
    /opt/conda/bin/conda install -y nodejs Cython tensorflow pandas scikit-learn matplotlib seaborn jupyter jupyterlab && \
    /opt/conda/bin/conda clean -ya

EXPOSE 8888
RUN jupyter notebook --generate-config && \
    cd /root/.jupyter/ && \
    echo "c.NotebookApp.password = u'sha1:dc571ce166f1:044688aec2655ac0ac729343cf209304586139e6'" >> jupyter_notebook_config.py
COPY entrypoint.sh /
RUN chmod 777 /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
