#!/bin/bash
jupyter notebook --generate-config && \
cd /root/.jupyter/ && \
echo "c.NotebookApp.password = u'${JUPYTER_PWD}'" >> jupyter_notebook_config.py
echo 'JUPYTER_STATUS=Running' >> ~/.bashrc
jupyter nbconvert --to=notebook --allow-errors --inplace --execute /scripts/${PY_FILE}
echo 'JUPYTER_STATUS=Finished' >> ~/.bashrc
cd /scripts
jupyter notebook --port=8888 --no-browser --ip=0.0.0.0 --allow-root
